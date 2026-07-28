import pytest

from scraper.pagination import DisallowedByRobots, fetch_url, iterate_pages

PAGE_TEMPLATE = """
<html><body>
<div class="item">item-{n}</div>
{next_link}
</body></html>
"""


def make_pages(count):
    pages = {}
    for n in range(1, count + 1):
        url = f"https://example.com/page-{n}.html"
        next_link = (
            f'<a class="next" href="page-{n + 1}.html">next</a>' if n < count else ""
        )
        pages[url] = PAGE_TEMPLATE.format(n=n, next_link=next_link)
    return pages


class FakeFetcher:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def fetch(self, url, wait_for_selector=None):
        self.calls.append(url)
        return self.pages[url]


class AllowAllRobots:
    def is_allowed(self, url):
        return True


class DenyAllRobots:
    def is_allowed(self, url):
        return False


class NoWaitRateLimiter:
    def wait(self, url):
        pass


SITE_CONFIG = {
    "pagination": {"enabled": True, "next_selector": "a.next", "next_attr": "href", "max_pages": None},
    "list_page": {},
}


def test_iterate_pages_follows_next_until_end():
    pages = make_pages(3)
    fetcher = FakeFetcher(pages)

    seen = list(iterate_pages(fetcher, AllowAllRobots(), NoWaitRateLimiter(),
                               "https://example.com/page-1.html", SITE_CONFIG))

    assert [p[0] for p in seen] == [1, 2, 3]
    assert seen[-1][3] is None  # no next_url on the last page
    assert fetcher.calls == [
        "https://example.com/page-1.html",
        "https://example.com/page-2.html",
        "https://example.com/page-3.html",
    ]


def test_iterate_pages_stops_at_max_pages():
    pages = make_pages(5)
    fetcher = FakeFetcher(pages)
    config = {**SITE_CONFIG, "pagination": {**SITE_CONFIG["pagination"], "max_pages": 2}}

    seen = list(iterate_pages(fetcher, AllowAllRobots(), NoWaitRateLimiter(),
                               "https://example.com/page-1.html", config))

    assert [p[0] for p in seen] == [1, 2]
    assert fetcher.calls == [
        "https://example.com/page-1.html",
        "https://example.com/page-2.html",
    ]


def test_iterate_pages_stops_when_robots_disallow():
    pages = make_pages(2)
    fetcher = FakeFetcher(pages)

    seen = list(iterate_pages(fetcher, DenyAllRobots(), NoWaitRateLimiter(),
                               "https://example.com/page-1.html", SITE_CONFIG))

    assert seen == []
    assert fetcher.calls == []


def test_fetch_url_raises_when_disallowed():
    with pytest.raises(DisallowedByRobots):
        fetch_url(FakeFetcher({}), DenyAllRobots(), NoWaitRateLimiter(), "https://example.com/x")
