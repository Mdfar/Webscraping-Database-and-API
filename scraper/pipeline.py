import json
import logging
from pathlib import Path

from .db import Database
from .fetchers import SeleniumFetcher, StaticFetcher
from .pagination import DisallowedByRobots, fetch_url, iterate_pages
from .parser import extract_article, parse_list_page
from .rate_limiter import RateLimiter
from .robots import RobotsChecker
from .state import resolve_start
from .utils import html_to_soup, make_article_id

logger = logging.getLogger(__name__)


def load_config(config_path: str = "config/config.json") -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_site_configs(config: dict, only: list[str] | None = None) -> list[dict]:
    sites_dir = Path(config["sites_dir"])
    sites = []
    for path in sorted(sites_dir.glob("*.json")):
        with open(path, "r", encoding="utf-8") as f:
            site_config = json.load(f)
        if not site_config.get("enabled", True):
            continue
        if only and site_config["name"] not in only:
            continue
        sites.append(site_config)
    return sites


def build_fetcher(site_config: dict, defaults: dict):
    request_cfg = site_config.get("request", {})
    headers = {"User-Agent": defaults["user_agent"]}
    headers.update(request_cfg.get("headers") or {})

    if site_config.get("render"):
        return SeleniumFetcher(
            user_agent=headers["User-Agent"],
            timeout_seconds=defaults["timeout_seconds"],
            max_retries=defaults["max_retries"],
            retry_wait_fixed_ms=defaults["retry_wait_fixed_ms"],
        )
    return StaticFetcher(
        headers=headers,
        timeout_seconds=defaults["timeout_seconds"],
        max_retries=defaults["max_retries"],
        retry_wait_fixed_ms=defaults["retry_wait_fixed_ms"],
    )


class SiteStats:
    def __init__(self):
        self.inserted = 0
        self.updated = 0
        self.skipped = 0
        self.errors = 0

    def __repr__(self):
        return (f"inserted={self.inserted} updated={self.updated} "
                f"skipped={self.skipped} errors={self.errors}")


def process_article_item(db, robots, rate_limiter, fetcher, item, site_config, force_refresh: bool) -> str:
    """Resolve one list-page item into a stored article. Returns 'inserted' |
    'updated' | 'skipped' | 'error'.
    """
    domain = site_config["domain"]
    article_cfg = site_config["article"]

    article_id = make_article_id(item.url)
    if not force_refresh and item.mode == "link" and db.article_exists(domain, article_id):
        logger.debug("Already have %s, skipping fetch", item.url)
        return "skipped"

    try:
        if item.mode == "inline":
            scope = item.tag
        else:
            html = fetch_url(fetcher, robots, rate_limiter, item.url)
            scope = html_to_soup(html)

        article = extract_article(scope, item.url, domain, article_cfg)

        article["category_id"] = db.get_or_create_category(domain, article.pop("category"))
        article["author_id"] = db.get_or_create_author(domain, article.pop("author"))
        article["featured_image_id"] = db.get_or_create_featured_image(
            domain, article.pop("featured_image")
        )

        return db.upsert_article(article)
    except DisallowedByRobots:
        logger.warning("Skipping %s: disallowed by robots.txt", item.url)
        return "skipped"
    except Exception:
        logger.exception("Failed to process article %s", item.url)
        return "error"


def run_site(config: dict, site_config: dict, db: Database, max_pages_override: int | None = None,
             force_refresh: bool = False) -> SiteStats:
    defaults = config["defaults"]
    stats = SiteStats()

    if max_pages_override is not None:
        site_config = {**site_config, "pagination": {**site_config["pagination"], "max_pages": max_pages_override}}

    fetcher = build_fetcher(site_config, defaults)
    robots = RobotsChecker(user_agent=defaults["user_agent"], enabled=defaults["respect_robots_txt"])
    rate_limiter = RateLimiter(
        delay_seconds=site_config.get("request", {}).get("delay_seconds", defaults["delay_seconds"]),
        jitter_seconds=site_config.get("request", {}).get("jitter_seconds", defaults["jitter_seconds"]),
    )

    start_url, start_page = resolve_start(db, site_config)

    try:
        for page_number, page_url, html, next_url in iterate_pages(
            fetcher, robots, rate_limiter, start_url, site_config, start_page
        ):
            logger.info("[%s] page %s: %s", site_config["name"], page_number, page_url)
            items = parse_list_page(html, page_url, site_config)
            logger.info("[%s] page %s: %d items found", site_config["name"], page_number, len(items))

            for item in items:
                result = process_article_item(db, robots, rate_limiter, fetcher, item, site_config, force_refresh)
                if result == "inserted":
                    stats.inserted += 1
                elif result == "updated":
                    stats.updated += 1
                elif result == "skipped":
                    stats.skipped += 1
                elif result == "error":
                    stats.errors += 1

            if next_url:
                db.set_state(site_config["domain"], next_url, page_number + 1)
            else:
                db.reset_state(site_config["domain"])
    finally:
        fetcher.close()

    return stats


def run(config_path: str = "config/config.json", only: list[str] | None = None,
        max_pages_override: int | None = None, force_refresh: bool = False,
        reset_state: bool = False) -> dict:
    config = load_config(config_path)
    site_configs = load_site_configs(config, only)

    if not site_configs:
        logger.warning("No enabled site configs matched %s", only)
        return {}

    with Database(config["database"]["path"]) as db:
        results = {}
        for site_config in site_configs:
            if reset_state:
                db.reset_state(site_config["domain"])
            logger.info("Starting site: %s", site_config["name"])
            stats = run_site(config, site_config, db, max_pages_override, force_refresh)
            logger.info("Finished site %s: %s", site_config["name"], stats)
            results[site_config["name"]] = stats
        return results
