"""Rewrite internal absolute URLs to relative paths for GitHub Pages."""

from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import urlparse, urljoin, urlunparse

# CSS url() pattern – matches url("…"), url('…'), url(…)
_CSS_URL_RE = re.compile(
    r"""url\(\s*(['"]?)([^'"\)\s]+)\1\s*\)""",
    re.IGNORECASE,
)


def url_to_local_path(url: str, output_dir: Path) -> Path:
    """Map a fully-qualified page URL to a filesystem path inside *output_dir*.

    Examples
    --------
    ``https://example.com/``              → ``docs/index.html``
    ``https://example.com/about/``        → ``docs/about/index.html``
    ``https://example.com/assets/a.css``  → ``docs/assets/a.css``
    """
    parsed = urlparse(url)
    path = parsed.path or "/"

    # Trailing slash or no file extension → directory index
    last_segment = path.rstrip("/").split("/")[-1] if path.rstrip("/") else ""
    is_directory = path.endswith("/") or "." not in last_segment

    if is_directory:
        local = output_dir / path.lstrip("/") / "index.html"
    else:
        local = output_dir / path.lstrip("/")

    return local


def _is_internal(url: str, base_host: str) -> bool:
    parsed = urlparse(url)
    return parsed.netloc == "" or parsed.netloc == base_host


def _make_relative(target_path: Path, from_dir: Path) -> str:
    """Return a POSIX-style relative path from *from_dir* to *target_path*."""
    try:
        rel = os.path.relpath(target_path, from_dir)
        return Path(rel).as_posix()
    except ValueError:
        # Different drives on Windows – fall back to absolute path
        return target_path.as_posix()


def rewrite_html(soup, current_url: str, output_dir: Path, base_host: str) -> None:
    """Rewrite internal links inside a BeautifulSoup document in-place.

    Handles:
    * ``href`` (``<a>``, ``<link>``)
    * ``src`` (``<script>``, ``<img>``, ``<source>``, …)
    * ``srcset`` (``<img srcset>``, ``<source srcset>``)
    * ``action`` (``<form>``) — rewritten but forms won't submit statically
    * ``content`` meta-refresh URLs
    """
    current_local = url_to_local_path(current_url, output_dir)
    current_dir = current_local.parent

    def _rw(raw_url: str) -> str:
        """Rewrite a single URL string; return original if not rewritable."""
        if not raw_url:
            return raw_url
        stripped = raw_url.strip()
        if stripped.startswith(("#", "data:", "mailto:", "tel:", "javascript:")):
            return raw_url
        absolute = urljoin(current_url, stripped)
        if not _is_internal(absolute, base_host):
            return raw_url
        target = url_to_local_path(absolute, output_dir)
        rel = _make_relative(target, current_dir)
        # Re-attach query and fragment from the *original* absolute URL
        parsed = urlparse(absolute)
        if parsed.query:
            rel += "?" + parsed.query
        if parsed.fragment:
            rel += "#" + parsed.fragment
        return rel

    # Single-URL attributes
    for attr in ("href", "src", "action"):
        for tag in soup.find_all(**{attr: True}):
            tag[attr] = _rw(tag[attr])

    # srcset (comma-separated list of "url [descriptor]" tokens)
    for tag in soup.find_all(srcset=True):
        parts = []
        for token in tag["srcset"].split(","):
            token = token.strip()
            if not token:
                continue
            pieces = token.split(None, 1)
            pieces[0] = _rw(pieces[0])
            parts.append(" ".join(pieces))
        tag["srcset"] = ", ".join(parts)

    # <meta http-equiv="refresh" content="0; url=…">
    for meta in soup.find_all("meta", attrs={"http-equiv": re.compile(r"refresh", re.I)}):
        content = meta.get("content", "")
        match = re.search(r"url\s*=\s*(.+)", content, re.IGNORECASE)
        if match:
            old_url = match.group(1).strip().strip("'\"")
            new_url = _rw(old_url)
            meta["content"] = content[: match.start(1)] + new_url


def rewrite_css(css_text: str, current_url: str, output_dir: Path, base_host: str) -> str:
    """Rewrite ``url(…)`` references inside CSS text."""
    current_local = url_to_local_path(current_url, output_dir)
    current_dir = current_local.parent

    def _replace(match: re.Match) -> str:
        quote = match.group(1)
        raw = match.group(2)
        if raw.startswith(("data:", "#")):
            return match.group(0)
        absolute = urljoin(current_url, raw)
        if not _is_internal(absolute, base_host):
            return match.group(0)
        target = url_to_local_path(absolute, output_dir)
        rel = _make_relative(target, current_dir)
        return f"url({quote}{rel}{quote})"

    return _CSS_URL_RE.sub(_replace, css_text)
