#!/usr/bin/env python3
"""Extract structured opportunity data from scraped find-opportunities pages into JSON."""

from __future__ import annotations

import json
import re
from pathlib import Path

from bs4 import BeautifulSoup

OPPORTUNITIES_DIR = Path("docs/find-opportunities")
DATA_DIR = Path("data")
JSON_PATH = DATA_DIR / "opportunities.json"


def _text(soup, selector: str) -> str | None:
    tag = soup.select_one(selector)
    if tag is None:
        return None
    t = tag.get_text(" ", strip=True)
    return t or None


def _texts(soup, selector: str) -> list[str]:
    tags = soup.select(selector)
    return [t.get_text(" ", strip=True) for t in tags if t.get_text(strip=True)]


def _href(soup, selector: str) -> str | None:
    tag = soup.select_one(selector)
    if tag is None:
        return None
    href = tag.get("href", "")
    href = re.sub(r"^(tel:|mailto:)", "", href).strip()
    return href or None


def _src(soup, selector: str) -> str | None:
    tag = soup.select_one(selector)
    if tag is None:
        return None
    src = tag.get("src", "").strip()
    if not src or "blank.png" in src:
        return None
    return src


def parse_opportunity(html_path: Path) -> dict | None:
    slug = html_path.parent.name
    soup = BeautifulSoup(html_path.read_bytes(), "lxml")

    container = soup.select_one(".node--type-opportunity") or soup

    title = _text(container, ".field--name-node-title h1")
    if not title:
        return None

    # Partner link
    partner_tag = container.select_one(
        ".field--name-dynamic-token-fieldnode-partner-link a"
    )
    partner_name = partner_tag.get_text(strip=True) if partner_tag else None
    partner_url = partner_tag.get("href") if partner_tag else None

    # Description
    desc_field = container.select_one(".field--name-field-full-description")
    description = None
    if desc_field:
        paragraphs = [p.get_text(" ", strip=True) for p in desc_field.find_all("p")]
        text = " ".join(p for p in paragraphs if p)
        description = text or desc_field.get_text(" ", strip=True) or None

    # External link
    link = _href(container, ".field--name-field-link a")

    # Availability description
    availability = _text(
        container, ".field--name-field-recurrence-description .field--item"
    )

    # Date range
    dates = []
    for time_tag in container.select(
        ".field--name-field-date-range time"
    ):
        dt = time_tag.get("datetime")
        if dt:
            dates.append(dt)
    date_start = dates[0] if len(dates) > 0 else None
    date_end = dates[1] if len(dates) > 1 else None

    # Multi-value taxonomy fields
    age_grade = _texts(
        container, ".field--name-field-age-grade-level .field--item"
    )
    time_of_day = _texts(
        container, ".field--name-field-time-of-day .field--item"
    )
    areas_of_interest = _texts(
        container, ".field--name-field-area-of-interest .field--item"
    )
    specific_attention = _texts(
        container, ".field--name-field-specific-attention .field--item"
    )

    # Single-value fields
    cost_range = _text(
        container, ".field--name-field-cost-range .field--item"
    )
    opportunity_type = _text(
        container, ".field--name-field-opportunity-type .field--item"
    )
    financial_support = _text(
        container, ".field--name-field-financial-support-or-schol .field--item"
    )
    ngss_aligned = _text(
        container, ".field--name-field-ngss-aligned- .field--item"
    )

    # Right sidebar fields
    location = _text(container, ".field--name-field-geoaddress .field--item")
    contact_name = _text(container, ".field--name-field-contact-name .field--item")
    contact_email = _text(container, ".field--name-field-contact-email .field--item")
    contact_phone = (
        _href(container, ".field--name-field-contact-phone a")
        or _text(container, ".field--name-field-contact-phone .field--item")
    )

    # Geolocation
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

    # Logo
    logo_src = _src(container, ".view-id-opportunity_logo img")

    record = {
        "slug": slug,
        "title": title,
        "partner_name": partner_name,
        "partner_url": partner_url,
        "description": description,
        "link": link,
        "availability": availability,
        "date_start": date_start,
        "date_end": date_end,
        "age_grade_level": age_grade or None,
        "cost_range": cost_range,
        "time_of_day": time_of_day or None,
        "opportunity_type": opportunity_type,
        "areas_of_interest": areas_of_interest or None,
        "specific_attention": specific_attention or None,
        "financial_support": financial_support,
        "ngss_aligned": ngss_aligned,
        "location": location,
        "contact_name": contact_name,
        "contact_email": contact_email,
        "contact_phone": contact_phone,
        "latitude": lat,
        "longitude": lng,
        "logo_src": logo_src,
    }

    # Drop None values for compactness
    return {k: v for k, v in record.items() if v is not None}


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)

    pages = sorted(OPPORTUNITIES_DIR.glob("*/index.html"))
    print(f"Found {len(pages)} opportunity pages.")

    records: list[dict] = []
    for page in pages:
        try:
            rec = parse_opportunity(page)
            if rec and rec.get("title"):
                records.append(rec)
        except Exception as exc:
            print(f"  ERROR parsing {page}: {exc}")

    with JSON_PATH.open("w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    print(f"Wrote {len(records)} records → {JSON_PATH}")


if __name__ == "__main__":
    main()
