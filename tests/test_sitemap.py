"""Unit tests for stemscrape.sitemap (network-mocked)."""

from unittest.mock import MagicMock, patch

from stemscrape.sitemap import _try_robots, discover_sitemap_urls


def _make_session(text: str = "", status: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.ok = status < 400
    resp.text = text
    resp.status_code = status
    session = MagicMock()
    session.get.return_value = resp
    session.head.return_value = resp
    return session


def test_try_robots_finds_sitemap_directive():
    robots_txt = "User-agent: *\nDisallow: /private/\nSitemap: https://www.sdstemecosystem.org/sitemap.xml\n"
    session = _make_session(robots_txt)
    result = _try_robots("https://www.sdstemecosystem.org", session)
    assert "https://www.sdstemecosystem.org/sitemap.xml" in result


def test_try_robots_no_sitemap_directive():
    robots_txt = "User-agent: *\nDisallow: /private/\n"
    session = _make_session(robots_txt)
    result = _try_robots("https://www.sdstemecosystem.org", session)
    assert result == []


def test_try_robots_request_failure():
    session = MagicMock()
    session.get.side_effect = Exception("timeout")
    result = _try_robots("https://www.sdstemecosystem.org", session)
    assert result == []


@patch("stemscrape.sitemap._try_advertools")
def test_discover_sitemap_urls_uses_robots(mock_adv):
    """discover_sitemap_urls should include URLs found in robots.txt sitemaps."""
    mock_adv.return_value = ["https://www.sdstemecosystem.org/page1/",
                             "https://www.sdstemecosystem.org/page2/"]
    robots_txt = "Sitemap: https://www.sdstemecosystem.org/sitemap.xml\n"
    session = _make_session(robots_txt)

    urls = discover_sitemap_urls("https://www.sdstemecosystem.org", session)
    assert "https://www.sdstemecosystem.org/page1/" in urls
    assert "https://www.sdstemecosystem.org/page2/" in urls


@patch("stemscrape.sitemap._try_advertools")
def test_discover_sitemap_urls_deduplicates(mock_adv):
    """Same URL from multiple sitemaps should appear only once."""
    mock_adv.return_value = ["https://www.sdstemecosystem.org/page1/"]
    robots_txt = (
        "Sitemap: https://www.sdstemecosystem.org/sitemap.xml\n"
        "Sitemap: https://www.sdstemecosystem.org/sitemap2.xml\n"
    )
    session = _make_session(robots_txt)

    urls = discover_sitemap_urls("https://www.sdstemecosystem.org", session)
    assert urls.count("https://www.sdstemecosystem.org/page1/") == 1
