"""Sitemap discovery and parsing using advertools."""

from __future__ import annotations

import logging
from urllib.parse import urljoin

import requests

logger = logging.getLogger(__name__)

KNOWN_SITEMAP_PATHS = [
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/sitemap-index.xml",
    "/sitemaps/sitemap.xml",
    "/sitemap/sitemap.xml",
]


def _try_advertools(sitemap_url: str) -> list[str]:
    """Parse sitemap(s) with advertools, which handles nested sitemap indexes."""
    try:
        import advertools as adv

        df = adv.sitemap_to_df(sitemap_url)
        if df is not None and not df.empty and "loc" in df.columns:
            urls = df["loc"].dropna().tolist()
            logger.info("advertools found %d URL(s) in sitemap %s", len(urls), sitemap_url)
            return urls
    except Exception as exc:
        logger.warning("advertools failed for %s: %s", sitemap_url, exc)
    return []


def _try_robots(base_url: str, session: requests.Session) -> list[str]:
    """Look for Sitemap: directives inside robots.txt."""
    robots_url = urljoin(base_url, "/robots.txt")
    sitemap_urls: list[str] = []
    try:
        resp = session.get(robots_url, timeout=15)
        if resp.ok:
            for line in resp.text.splitlines():
                if line.lower().startswith("sitemap:"):
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        url = parts[1].strip()
                        if url:
                            sitemap_urls.append(url)
    except Exception as exc:
        logger.debug("Could not fetch robots.txt: %s", exc)
    return sitemap_urls


def discover_sitemap_urls(base_url: str, session: requests.Session) -> list[str]:
    """Return every page URL found across all sitemaps for *base_url*.

    Strategy
    --------
    1. Check ``robots.txt`` for ``Sitemap:`` directives.
    2. Try each of the well-known sitemap paths until one responds 200.
    3. Parse every discovered sitemap with ``advertools``, which transparently
       handles sitemap indexes (nested sitemaps).
    """
    candidate_sitemap_urls: list[str] = []

    # Step 1 – robots.txt
    candidate_sitemap_urls.extend(_try_robots(base_url, session))

    # Step 2 – well-known paths (add only those not already found)
    found_paths = {u for u in candidate_sitemap_urls}
    for path in KNOWN_SITEMAP_PATHS:
        url = urljoin(base_url, path)
        if url in found_paths:
            continue
        try:
            resp = session.head(url, timeout=10, allow_redirects=True)
            if resp.ok:
                candidate_sitemap_urls.append(url)
                found_paths.add(url)
                logger.debug("Found sitemap at %s", url)
        except Exception:
            pass

    # Step 3 – parse each sitemap
    all_page_urls: list[str] = []
    seen: set[str] = set()
    for sitemap_url in candidate_sitemap_urls:
        for page_url in _try_advertools(sitemap_url):
            if page_url not in seen:
                seen.add(page_url)
                all_page_urls.append(page_url)

    logger.info("Total sitemap URLs discovered: %d", len(all_page_urls))
    return all_page_urls
