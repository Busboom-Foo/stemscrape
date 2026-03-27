#!/usr/bin/env python3
"""Extract partner data from scraped partner-detail pages into JSONL + CSV."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from bs4 import BeautifulSoup

PARTNER_DETAIL_DIR = Path("docs/partners/partner-detail")
DATA_DIR = Path("data")
JSONL_PATH = DATA_DIR / "partners.jsonl"
CSV_PATH = DATA_DIR / "partners.csv"

# Ordered list of all possible fields (used for CSV column order)
FIELDS = [
    "id",
    "name",
    "organization_type",
    "description",
    "location",
    "latitude",
    "longitude",
    "website",
    "phone",
    "email",
    "twitter",
    "facebook",
    "linkedin",
    "instagram",
    "logo_src",
]


def _text(soup, selector: str) -> str | None:
    tag = soup.select_one(selector)
    if tag is None:
        return None
    t = tag.get_text(" ", strip=True)
    return t or None


def _href(soup, selector: str) -> str | None:
    tag = soup.select_one(selector)
    if tag is None:
        return None
    href = tag.get("href", "")
    # Strip tel: / mailto: prefixes
    href = re.sub(r"^(tel:|mailto:)", "", href).strip()
    return href or None


def _src(soup, selector: str) -> str | None:
    tag = soup.select_one(selector)
    if tag is None:
        return None
    src = tag.get("src", "").strip()
    # Ignore blank placeholder images
    if not src or "blank.png" in src:
        return None
    return src


def parse_partner(html_path: Path) -> dict:
    partner_id = int(html_path.parent.name)
    soup = BeautifulSoup(html_path.read_bytes(), "lxml")

    # Restrict to the main partner-detail view to avoid nav/footer noise
    container = soup.select_one(".view-id-partner_detail") or soup

    # Description: join all <p> text in the description field
    desc_field = container.select_one(".field--name-field-description-full-")
    description = None
    if desc_field:
        paragraphs = [p.get_text(" ", strip=True) for p in desc_field.find_all("p")]
        text = " ".join(p for p in paragraphs if p)
        description = text or desc_field.get_text(" ", strip=True) or None

    # Geolocation: prefer data attributes, fall back to <meta> tags
    lat = lng = None
    geo = container.select_one(".geolocation-location")
    if geo:
        lat = geo.get("data-lat") or None
        lng = geo.get("data-lng") or None
    if not lat:
        meta_lat = container.select_one("meta[property='latitude']")
        if meta_lat:
            lat = meta_lat.get("content") or None
    if not lng:
        meta_lng = container.select_one("meta[property='longitude']")
        if meta_lng:
            lng = meta_lng.get("content") or None

    record = {
        "id": partner_id,
        "name": _text(container, ".field--name-field-organization-name h1")
                or _text(container, ".field--name-field-organization-name"),
        "organization_type": _text(container, ".field--name-field-organization-type .field--item")
                             or _text(container, ".field--name-field-organization-type"),
        "description": description,
        "location": _text(container, ".field--name-field-geoaddress .field--item"),
        "latitude": lat,
        "longitude": lng,
        "website": _href(container, ".field--name-field-social-media-website-url a"),
        "phone": _href(container, ".field--name-field-contact-phone a")
                 or _text(container, ".field--name-field-contact-phone .field--item"),
        "email": _href(container, ".field--name-field-email a")
                 or _text(container, ".field--name-field-email .field--item"),
        "twitter": _href(container, ".field--name-field-social-media-twitter-url a"),
        "facebook": _href(container, ".field--name-field-social-media-facebook-url a"),
        "linkedin": _href(container, ".field--name-field-social-media-linkedin-url a"),
        "instagram": _href(container, ".field--name-field-social-media-instagram a"),
        "logo_src": _src(container, ".field--name-field-logo img"),
    }

    # Drop None values so the JSONL stays compact; CSV writer handles missing keys
    return {k: v for k, v in record.items() if v is not None}


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)

    pages = sorted(
        PARTNER_DETAIL_DIR.glob("*/index.html"),
        key=lambda p: int(p.parent.name),
    )
    print(f"Found {len(pages)} partner detail pages.")

    records: list[dict] = []
    for page in pages:
        try:
            rec = parse_partner(page)
            if rec.get("name"):  # skip pages that parsed as empty / 404 shells
                records.append(rec)
        except Exception as exc:
            print(f"  ERROR parsing {page}: {exc}")

    # Write JSONL
    with JSONL_PATH.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"Wrote {len(records)} records → {JSONL_PATH}")

    # Write CSV
    with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        for rec in records:
            writer.writerow(rec)
    print(f"Wrote CSV → {CSV_PATH}")


if __name__ == "__main__":
    main()
