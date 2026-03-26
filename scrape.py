#!/usr/bin/env python3
"""Convenience wrapper: python scrape.py [options]

Identical to: python -m stemscrape [options]
"""
from stemscrape.__main__ import main
import sys

if __name__ == "__main__":
    sys.exit(main())
