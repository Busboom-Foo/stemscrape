"""Core web crawler for mirroring sdstemecosystem.org."""

from __future__ import annotations

import logging
import re
import time
from collections import deque
from pathlib import Path
from urllib.parse import urlparse, urljoin, urlunparse, parse_qs, urlencode

import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from tqdm import tqdm

from .sitemap import discover_sitemap_urls
from .rewriter import url_to_local_path, rewrite_html, rewrite_css

logger = logging.getLogger(__name__)

BASE_URL = "https://www.sdstemecosystem.org"
BASE_HOST = "www.sdstemecosystem.org"

# HTML content types that receive link-rewriting treatment
_HTML_TYPES = {"text/html", "application/xhtml+xml"}
# CSS content types that receive url() rewriting
_CSS_TYPES = {"text/css"}
_CSS_URL_RE = re.compile(r"""url\(\s*(['\"]?)([^'\"\)\s]+)\1\s*\)""", re.IGNORECASE)


def _to_remote_candidate(page_url: str, raw_url: str) -> str:
    """Convert a URL found in local rewritten HTML back into a crawlable remote URL."""
    absolute = urljoin(page_url, raw_url)
    parsed = urlparse(absolute)

    # Local rewrite emits directory pages as .../index.html; remote site often serves .../
    if parsed.path.endswith("/index.html"):
        new_path = parsed.path[: -len("/index.html")] or "/"
        if new_path == "":
            new_path = "/"
        parsed = parsed._replace(path=new_path)
        absolute = urlunparse(parsed)

    return absolute


def _normalize_url(url: str) -> str:
    """Strip fragment, normalize trailing slash for HTML pages."""
    parsed = urlparse(url)
    path = parsed.path

    # Drupal emits /partner-detail/<id> links on listing pages, but the
    # publicly reachable route is /partners/partner-detail/<id>.
    if path.startswith("/partner-detail/"):
        path = "/partners" + path

    # Convert /<section>?page=N to the clean path /<section>/N so each page is
    # treated as a distinct URL in the visited set and saved to its own directory.
    _PAGINATED_SECTIONS = {"/partners", "/references", "/stem-news"}
    if path.rstrip("/") in _PAGINATED_SECTIONS and parsed.query:
        qs = parse_qs(parsed.query)
        if "page" in qs:
            page = qs["page"][0]
            section = path.rstrip("/")
            remaining = {k: v for k, v in qs.items() if k != "page"}
            new_query = urlencode(remaining, doseq=True)
            path = f"{section}/{page}"
            cleaned = parsed._replace(path=path, query=new_query, fragment="")
            return urlunparse(cleaned)

    # Drop fragment (never a separate page)
    cleaned = parsed._replace(path=path, fragment="")
    return urlunparse(cleaned)


class SDSTEMCrawler:
    """Crawl https://www.sdstemecosystem.org and save a GitHub-Pages-compatible
    mirror in *output_dir*.

    Parameters
    ----------
    output_dir:
        Destination directory for the mirrored content (default: ``docs``).
    delay:
        Seconds to pause between requests (be polite).
    timeout:
        Per-request timeout in seconds.
    max_retries:
        Number of HTTP retry attempts for transient errors.
    user_agent:
        ``User-Agent`` header sent with every request.
    """

    def __init__(
        self,
        output_dir: str | Path = "docs",
        delay: float = 0.5,
        timeout: int = 30,
        max_retries: int = 3,
        user_agent: str = "stemscrape/0.1 (+https://github.com/Busboom-Foo/stemscrape)",
        force: bool = False,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.delay = delay
        self.timeout = timeout
        self.max_retries = max_retries
        self.force = force

        self.session = requests.Session()
        self.session.headers["User-Agent"] = user_agent

        self._visited: set[str] = set()
        self._queue: deque[str] = deque()
        self.saved: list[str] = []
        self.failed: list[str] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Discover URLs via sitemap, then crawl all internal pages."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Write .nojekyll so GitHub Pages doesn't skip _* directories
        (self.output_dir / ".nojekyll").touch()

        # Seed queue: sitemap first, then homepage
        logger.info("Discovering sitemap URLs…")
        sitemap_urls = discover_sitemap_urls(BASE_URL, self.session)
        for url in sitemap_urls:
            self._enqueue(url)

        # Always include the homepage
        self._enqueue(BASE_URL + "/")

        # Seed all paginated listing pages (?page=0 is the base page;
        # subsequent pages are distinct and must be explicitly enqueued).
        for _page in range(1, 26):
            self._enqueue(f"{BASE_URL}/partners?page={_page}")
        for _page in range(1, 4):
            self._enqueue(f"{BASE_URL}/references?page={_page}")
        for _page in range(1, 3):
            self._enqueue(f"{BASE_URL}/stem-news?page={_page}")

        total_estimate = max(len(sitemap_urls), 1)
        with tqdm(desc="Scraping", unit="page", dynamic_ncols=True) as pbar:
            while self._queue:
                url = self._queue.popleft()
                if url in self._visited:
                    pbar.update(0)
                    continue
                self._visited.add(url)
                self._process(url)
                pbar.update(1)
                time.sleep(self.delay)

        logger.info(
            "Done. Saved: %d  Failed: %d  Total visited: %d",
            len(self.saved),
            len(self.failed),
            len(self._visited),
        )
        if self.failed:
            logger.warning("Failed URLs:\n  %s", "\n  ".join(self.failed))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _enqueue(self, url: str) -> None:
        """Add URL to queue after normalizing it."""
        if not url:
            return
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return
        if parsed.netloc and parsed.netloc != BASE_HOST:
            return
        norm = _normalize_url(url)
        if norm not in self._visited:
            self._queue.append(norm)

    @retry(
        retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def _fetch(self, url: str) -> requests.Response:
        return self.session.get(url, timeout=self.timeout, allow_redirects=True)

    def _process(self, url: str) -> None:
        """Download *url* and save it, rewriting links as needed."""
        if not self.force:
            local_path = url_to_local_path(url, self.output_dir)
            if local_path.exists():
                # For HTML/CSS files: still extract links so referenced assets are discovered.
                if local_path.suffix == ".html":
                    self._extract_links_from_local(local_path, url)
                elif local_path.suffix == ".css":
                    self._extract_assets_from_local_css(local_path, url)
                else:
                    logger.debug("Skipping already-saved %s", url)
                self.saved.append(url)
                return

        # Clean paginated paths (/<section>/N) must be fetched as query URLs
        fetch_url = url
        _parsed_url = urlparse(url)
        _m = re.match(r"^/(partners|references|stem-news)/(\d+)$", _parsed_url.path)
        if _m:
            section, page = _m.group(1), _m.group(2)
            fetch_url = urlunparse(
                _parsed_url._replace(path=f"/{section}", query=f"page={page}")
            )

        try:
            resp = self._fetch(fetch_url)
        except Exception as exc:
            logger.error("Fetch failed %s: %s", url, exc)
            self.failed.append(url)
            return

        if not resp.ok:
            logger.warning("HTTP %s for %s", resp.status_code, url)
            self.failed.append(url)
            return

        requested_local_path = url_to_local_path(url, self.output_dir)

        # Use the final URL after any redirects
        final_url = resp.url
        content_type = resp.headers.get("content-type", "").split(";")[0].strip().lower()

        # Keep non-HTML assets at the originally requested path so rewritten links
        # continue to resolve even if the origin redirects the asset URL.
        if content_type in _HTML_TYPES:
            local_path = url_to_local_path(final_url, self.output_dir)
        else:
            local_path = requested_local_path
        local_path.parent.mkdir(parents=True, exist_ok=True)

        if content_type in _HTML_TYPES:
            self._save_html(resp, final_url, local_path)
        elif content_type in _CSS_TYPES:
            self._save_css(resp, final_url, local_path)
        else:
            self._save_binary(resp, local_path)

        self.saved.append(final_url)
        logger.debug("Saved %s → %s", final_url, local_path)

    def _save_html(
        self, resp: requests.Response, url: str, local_path: Path
    ) -> None:
        soup = BeautifulSoup(resp.content, "lxml")

        # Discover and enqueue new internal links *before* rewriting
        for tag in soup.find_all(href=True):
            self._enqueue(urljoin(url, tag["href"]))
        for tag in soup.find_all(src=True):
            self._enqueue(urljoin(url, tag["src"]))
        for tag in soup.find_all(srcset=True):
            for token in tag["srcset"].split(","):
                parts = token.strip().split()
                if parts:
                    self._enqueue(urljoin(url, parts[0]))

        # Rewrite links for local / GitHub Pages serving
        rewrite_html(soup, url, self.output_dir, BASE_HOST)

        local_path.write_text(str(soup), encoding="utf-8")

    def _save_css(
        self, resp: requests.Response, url: str, local_path: Path
    ) -> None:
        css_text = resp.text
        for match in _CSS_URL_RE.finditer(css_text):
            self._enqueue(urljoin(url, match.group(2)))
        css_text = rewrite_css(css_text, url, self.output_dir, BASE_HOST)
        local_path.write_text(css_text, encoding="utf-8")

    def _save_binary(self, resp: requests.Response, local_path: Path) -> None:
        local_path.write_bytes(resp.content)

    def _extract_links_from_local(self, local_path: Path, url: str) -> None:
        """Parse an already-saved (rewritten) HTML file and enqueue any linked assets."""
        try:
            soup = BeautifulSoup(local_path.read_bytes(), "lxml")
        except Exception as exc:
            logger.debug("Could not parse local HTML %s: %s", local_path, exc)
            return
        for tag in soup.find_all(href=True):
            self._enqueue(_to_remote_candidate(url, tag["href"]))
        for tag in soup.find_all(src=True):
            self._enqueue(_to_remote_candidate(url, tag["src"]))
        for tag in soup.find_all(srcset=True):
            for token in tag["srcset"].split(","):
                parts = token.strip().split()
                if parts:
                    self._enqueue(_to_remote_candidate(url, parts[0]))

    def _extract_assets_from_local_css(self, local_path: Path, url: str) -> None:
        """Parse an already-saved CSS file and enqueue any referenced assets."""
        try:
            css_text = local_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:
            logger.debug("Could not parse local CSS %s: %s", local_path, exc)
            return
        for match in _CSS_URL_RE.finditer(css_text):
            self._enqueue(_to_remote_candidate(url, match.group(2)))
