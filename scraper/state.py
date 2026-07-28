import logging

logger = logging.getLogger(__name__)


def resolve_start(db, site_config: dict) -> tuple[str, int]:
    """Where to resume a site's crawl from.

    scrape_state stores the *next* URL to fetch (checkpointed after each page
    is fully processed), so a killed run picks back up without re-scraping
    pages it already finished. Falls back to the site's first configured
    start_url when there is no checkpoint.
    """
    domain = site_config["domain"]
    state = db.get_state(domain)
    if state and state.get("last_url"):
        logger.info("Resuming %s from page %s (%s)", domain, state["last_page"], state["last_url"])
        return state["last_url"], state["last_page"] or 1
    return site_config["start_urls"][0], 1
