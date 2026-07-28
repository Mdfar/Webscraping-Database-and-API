import argparse
import logging

from scraper.logging_config import setup_logging
from scraper.pipeline import load_config, run


def parse_args():
    parser = argparse.ArgumentParser(description="Article scraping pipeline")
    parser.add_argument(
        "--site", action="append", dest="sites",
        help="Name of a site config to run (config/sites/<name>.json). Repeatable. Default: all enabled sites.",
    )
    parser.add_argument(
        "--max-pages", type=int, default=None,
        help="Override each site's configured max_pages for this run.",
    )
    parser.add_argument(
        "--force-refresh", action="store_true",
        help="Re-fetch and re-extract articles even if already stored (still skips DB writes if content is unchanged).",
    )
    parser.add_argument(
        "--reset-state", action="store_true",
        help="Ignore any saved resume checkpoint and start each site from its first configured start_url.",
    )
    parser.add_argument(
        "--config", default="config/config.json",
        help="Path to the global config file.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    config = load_config(args.config)
    setup_logging(config["logging"]["level"], config["logging"]["file"])
    logger = logging.getLogger("main")

    results = run(
        config_path=args.config,
        only=args.sites,
        max_pages_override=args.max_pages,
        force_refresh=args.force_refresh,
        reset_state=args.reset_state,
    )

    for name, stats in results.items():
        logger.info("%s -> %s", name, stats)


if __name__ == "__main__":
    main()
