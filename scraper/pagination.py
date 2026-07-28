import logging

from .parser import find_next_page

logger = logging.getLogger(__name__)


class DisallowedByRobots(Exception):
    pass


def fetch_url(fetcher, robots, rate_limiter, url, wait_for_selector=None):
    """Fetch a single URL, enforcing robots.txt and the politeness delay first."""
    if not robots.is_allowed(url):
        raise DisallowedByRobots(url)
    rate_limiter.wait(url)
    return fetcher.fetch(url, wait_for_selector=wait_for_selector)


def iterate_pages(fetcher, robots, rate_limiter, start_url, site_config, start_page=1):
    """Yield (page_number, page_url, html, next_url) for a site, following the
    configured 'next' link until pagination ends or max_pages is reached.
    Applies the robots.txt check and politeness delay before every request.
    """
    pagination_cfg = site_config.get("pagination", {})
    max_pages = pagination_cfg.get("max_pages")
    wait_for_selector = site_config.get("list_page", {}).get("wait_for_selector")

    url = start_url
    page_number = start_page

    while url:
        try:
            html = fetch_url(fetcher, robots, rate_limiter, url, wait_for_selector)
        except DisallowedByRobots:
            logger.warning("Skipping %s: disallowed by robots.txt", url)
            return

        next_url = find_next_page(html, url, pagination_cfg)
        if next_url == url:
            next_url = None

        yield page_number, url, html, next_url

        if not next_url:
            return
        if max_pages and page_number >= max_pages:
            logger.info("Reached max_pages=%s for this run, stopping pagination", max_pages)
            return

        url = next_url
        page_number += 1
