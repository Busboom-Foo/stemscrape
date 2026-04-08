#!/usr/bin/env python3
"""
Copy partner logos from docs/ to images/ with clean, descriptive names.
Produces data/partners_logos.csv with a new 'logo' column.
"""

import csv
import os
import re
import shutil
from collections import Counter


def slugify(name):
    """Convert an organization name to a clean lowercase slug."""
    # Remove common suffixes/noise
    name = name.lower()
    # Remove punctuation except spaces and alphanumeric
    name = re.sub(r"[^a-z0-9\s]", "", name)
    # Collapse whitespace
    name = re.sub(r"\s+", " ", name).strip()
    # Take meaningful words (skip very common ones for brevity)
    words = name.split()
    # Truncate to keep names reasonable
    if len(words) > 4:
        words = words[:4]
    return "_".join(words)


def main():
    input_csv = "data/partners_viable.csv"
    output_csv = "data/partners_logos.csv"
    images_dir = "images"

    os.makedirs(images_dir, exist_ok=True)

    with open(input_csv, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames

    # Add 'logo' to fieldnames if not present
    if "logo" not in fieldnames:
        fieldnames = list(fieldnames) + ["logo"]

    # Track used slugs to ensure uniqueness
    used_slugs = Counter()
    copied = 0
    skipped_no_src = 0
    skipped_not_found = 0

    for row in rows:
        logo_src = row.get("logo_src", "").strip()
        if not logo_src:
            row["logo"] = ""
            skipped_no_src += 1
            continue

        # Build the path in docs/ — keep %20 encoding as files on disk use it
        rel_path = logo_src.replace("../../../", "")
        full_path = os.path.join("docs", rel_path)

        if not os.path.exists(full_path):
            print(f"NOT FOUND: {full_path} ({row['name']})")
            row["logo"] = ""
            skipped_not_found += 1
            continue

        # Determine extension from the original file
        _, ext = os.path.splitext(full_path)
        ext = ext.lower()

        # Create a clean slug from the organization name
        slug = slugify(row["name"])

        # Ensure uniqueness
        used_slugs[slug] += 1
        if used_slugs[slug] > 1:
            slug = f"{slug}_{used_slugs[slug]}"

        new_filename = f"{slug}{ext}"
        dest_path = os.path.join(images_dir, new_filename)

        shutil.copy2(full_path, dest_path)
        row["logo"] = new_filename
        copied += 1

    # Write output CSV
    with open(output_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nDone! Copied: {copied}, No logo_src: {skipped_no_src}, Not found: {skipped_not_found}")
    print(f"Output CSV: {output_csv}")
    print(f"Images dir: {images_dir}/")


if __name__ == "__main__":
    main()
