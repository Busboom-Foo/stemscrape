"""Entry-point when running ``python -m stemscrape`` or ``stemscrape`` CLI."""

from __future__ import annotations

import argparse
import logging
import sys

from .crawler import SDSTEMCrawler


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="stemscrape",
        description="Mirror https://www.sdstemecosystem.org/ for GitHub Pages.",
    )
    parser.add_argument(
        "--output-dir",
        default="docs",
        metavar="DIR",
        help="Directory to write mirrored content into (default: docs).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        metavar="SECS",
        help="Pause between requests in seconds (default: 0.5).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        metavar="SECS",
        help="Per-request timeout in seconds (default: 30).",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose (DEBUG) logging.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-scrape pages even if they already exist locally.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    crawler = SDSTEMCrawler(
        output_dir=args.output_dir,
        delay=args.delay,
        timeout=args.timeout,
        force=args.force,
    )
    crawler.run()
    return 0 if not crawler.failed else 1


if __name__ == "__main__":
    sys.exit(main())
