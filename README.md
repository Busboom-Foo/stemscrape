# stemscrape

Mirror the [San Diego STEM Ecosystem website](https://www.sdstemecosystem.org/) as a
static site stored in this repository and served via **GitHub Pages**.

.
---

## How it works

1. **Sitemap discovery** – `robots.txt` is checked for `Sitemap:` directives and
   several well-known sitemap paths (`/sitemap.xml`, `/sitemap_index.xml`, …) are
   probed.  Every URL found is seeded into the crawl queue.
2. **Link-following crawl** – `href`, `src`, and `srcset` attributes are extracted
   from every HTML page encountered.  New internal URLs are added to the queue.
3. **Link rewriting** – Internal absolute URLs are rewritten to
   *relative paths* so the mirrored site works correctly under any hostname
   (GitHub Pages, local file-system, or a custom domain).
4. **CSS rewriting** – `url(…)` references inside CSS files are rewritten the
   same way.
5. **Static output** – Every page and asset is saved inside `docs/` with a
   directory structure that matches the original URL path.  GitHub Pages is
   configured to serve from `docs/`.

---

## Quick start

```bash
# 1. Clone the repo
git clone https://github.com/Busboom-Foo/stemscrape.git
cd stemscrape

# 2. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
# (optional: install the package itself in editable mode)
pip install -e .

# 4. Run the scraper
python scrape.py

# Or equivalently:
python -m stemscrape
```

The mirrored site is written into `docs/`.  Commit `docs/` and push;
the **Deploy mirror to GitHub Pages** workflow will publish it automatically.

---

## CLI options

```
usage: stemscrape [-h] [--output-dir DIR] [--delay SECS] [--timeout SECS] [-v]

options:
  --output-dir DIR   Directory to write mirrored content into (default: docs)
  --delay SECS       Pause between requests in seconds (default: 0.5)
  --timeout SECS     Per-request timeout in seconds (default: 30)
  -v, --verbose      Enable verbose (DEBUG) logging
```

---

## Project structure

```
stemscrape/
├── .github/
│   └── workflows/
│       └── pages.yml        # Deploys docs/ to GitHub Pages on push to main
├── docs/                    # Generated mirror (committed to repo)
│   └── .nojekyll            # Prevents Jekyll processing
├── stemscrape/
│   ├── __init__.py
│   ├── __main__.py          # CLI entry-point (python -m stemscrape)
│   ├── crawler.py           # SDSTEMCrawler – core crawl/download logic
│   ├── sitemap.py           # Sitemap discovery via advertools + robots.txt
│   └── rewriter.py          # Internal link rewriter (HTML + CSS)
├── scrape.py                # Convenience wrapper (python scrape.py)
├── requirements.txt
└── pyproject.toml
```

---

## Dependencies

| Library | Purpose |
|---|---|
| `requests` | HTTP client with session management and redirect handling |
| `beautifulsoup4` + `lxml` | HTML parsing and DOM traversal |
| `advertools` | Sitemap discovery and parsing (handles nested sitemap indexes) |
| `tenacity` | Automatic retry with exponential back-off on transient errors |
| `tqdm` | Progress bar during crawl |

---

## GitHub Pages setup

After pushing, go to **Settings → Pages** in the repository and choose:
- **Source**: `Deploy from a branch`  
- **Branch**: `main` / `docs`

Or use the included `pages.yml` workflow (set **Source** to *GitHub Actions*).
