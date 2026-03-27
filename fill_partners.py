#!/usr/bin/env python3
"""Fill in missing partner-detail pages.

Scans docs/partners/partner-detail/ for already-fetched IDs, then tries
every ID from 0-800 that is absent. Skips 404s silently; logs other errors.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from stemscrape.rewriter import url_to_local_path, rewrite_html

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BASE_URL = "https://www.sdstemecosystem.org"
BASE_HOST = "www.sdstemecosystem.org"
OUTPUT_DIR = Path("docs")
PARTNER_DETAIL_DIR = OUTPUT_DIR / "partners" / "partner-detail"
DELAY = 0.5
TIMEOUT = 30
MAX_ID = 800

session = requests.Session()
session.headers["User-Agent"] = "stemscrape/0.1 (+https://github.com/Busboom-Foo/stemscrape)"


def existing_ids() -> set[int]:
    if not PARTNER_DETAIL_DIR.exists():
        return set()
    return {int(p.name) for p in PARTNER_DETAIL_DIR.iterdir() if p.is_dir() and p.name.isdigit()}


def fetch_and_save(partner_id: int) -> bool:
    """Fetch /partners/partner-detail/<id>, save it, return True on success."""
    url = f"{BASE_URL}/partners/partner-detail/{partner_id}"
    try:
        resp = session.get(url, timeout=TIMEOUT, allow_redirects=True)
    except Exception as exc:
        logger.warning("Error fetching %s: %s", url, exc)
        return False

    if resp.status_code == 404:
        return False
    if not resp.ok:
        logger.warning("HTTP %s for %s", resp.status_code, url)
        return False

    final_url = resp.url
    local_path = url_to_local_path(final_url, OUTPUT_DIR)
    local_path.parent.mkdir(parents=True, exist_ok=True)

    soup = BeautifulSoup(resp.content, "lxml")
    rewrite_html(soup, final_url, OUTPUT_DIR, BASE_HOST)
    local_path.write_text(str(soup), encoding="utf-8")
    logger.info("Saved %s → %s", final_url, local_path)
    return True


def main() -> None:
    have = existing_ids()
    missing = sorted(set(range(0, MAX_ID + 1)) - have)
    logger.info("Have %d IDs already. Trying %d missing IDs (0–%d).", len(have), len(missing), MAX_ID)

    saved = 0
    skipped = 0
    for partner_id in missing:
        if fetch_and_save(partner_id):
            saved += 1
        else:
            skipped += 1
        time.sleep(DELAY)

    logger.info("Done. Saved: %d  Skipped/404: %d", saved, skipped)


if __name__ == "__main__":
    main()
