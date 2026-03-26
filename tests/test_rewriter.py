"""Unit tests for stemscrape.rewriter."""

from pathlib import Path

from bs4 import BeautifulSoup

from stemscrape.rewriter import url_to_local_path, rewrite_html, rewrite_css


DOCS = Path("docs")
HOST = "www.sdstemecosystem.org"


# ---------------------------------------------------------------------------
# url_to_local_path
# ---------------------------------------------------------------------------


def test_root_url():
    assert url_to_local_path("https://www.sdstemecosystem.org/", DOCS) == DOCS / "index.html"


def test_root_url_no_slash():
    assert url_to_local_path("https://www.sdstemecosystem.org", DOCS) == DOCS / "index.html"


def test_directory_url():
    result = url_to_local_path("https://www.sdstemecosystem.org/about/", DOCS)
    assert result == DOCS / "about" / "index.html"


def test_file_url():
    result = url_to_local_path("https://www.sdstemecosystem.org/assets/style.css", DOCS)
    assert result == DOCS / "assets" / "style.css"


def test_nested_directory():
    result = url_to_local_path("https://www.sdstemecosystem.org/programs/k12/", DOCS)
    assert result == DOCS / "programs" / "k12" / "index.html"


# ---------------------------------------------------------------------------
# rewrite_html
# ---------------------------------------------------------------------------


def _make_soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def test_rewrite_absolute_href():
    soup = _make_soup('<a href="https://www.sdstemecosystem.org/about/">About</a>')
    rewrite_html(soup, "https://www.sdstemecosystem.org/", DOCS, HOST)
    link = soup.find("a")
    # From docs/index.html → docs/about/index.html  ⟹  about/index.html
    assert link["href"] == "about/index.html"


def test_rewrite_root_relative_href():
    soup = _make_soup('<a href="/about/">About</a>')
    rewrite_html(soup, "https://www.sdstemecosystem.org/", DOCS, HOST)
    link = soup.find("a")
    assert link["href"] == "about/index.html"


def test_external_href_unchanged():
    soup = _make_soup('<a href="https://example.com/page">Ext</a>')
    rewrite_html(soup, "https://www.sdstemecosystem.org/", DOCS, HOST)
    link = soup.find("a")
    assert link["href"] == "https://example.com/page"


def test_anchor_href_unchanged():
    soup = _make_soup('<a href="#section1">Jump</a>')
    rewrite_html(soup, "https://www.sdstemecosystem.org/", DOCS, HOST)
    link = soup.find("a")
    assert link["href"] == "#section1"


def test_rewrite_img_src():
    soup = _make_soup('<img src="/images/logo.png">')
    rewrite_html(soup, "https://www.sdstemecosystem.org/", DOCS, HOST)
    img = soup.find("img")
    assert img["src"] == "images/logo.png"


def test_rewrite_from_sub_page():
    """Links from a sub-page should use relative paths going up."""
    soup = _make_soup('<a href="https://www.sdstemecosystem.org/about/">About</a>')
    rewrite_html(soup, "https://www.sdstemecosystem.org/programs/stem/", DOCS, HOST)
    link = soup.find("a")
    # From docs/programs/stem/index.html → docs/about/index.html
    assert link["href"] == "../../about/index.html"


def test_rewrite_srcset():
    soup = _make_soup('<img srcset="/img/sm.jpg 480w, /img/lg.jpg 1200w">')
    rewrite_html(soup, "https://www.sdstemecosystem.org/", DOCS, HOST)
    img = soup.find("img")
    assert "img/sm.jpg 480w" in img["srcset"]
    assert "img/lg.jpg 1200w" in img["srcset"]


# ---------------------------------------------------------------------------
# rewrite_css
# ---------------------------------------------------------------------------


def test_css_url_rewrite():
    css = "body { background: url('/images/bg.jpg'); }"
    result = rewrite_css(css, "https://www.sdstemecosystem.org/assets/style.css", DOCS, HOST)
    # docs/assets/style.css → relative to docs/assets/ for docs/images/bg.jpg
    # the absolute path "/images/bg.jpg" should become "../images/bg.jpg"
    assert "url(" in result
    assert "../images/bg.jpg" in result


def test_css_data_uri_unchanged():
    css = "body { background: url('data:image/png;base64,abc'); }"
    result = rewrite_css(css, "https://www.sdstemecosystem.org/assets/style.css", DOCS, HOST)
    assert "data:image/png;base64,abc" in result
