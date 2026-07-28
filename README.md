# Project Anna — Article Scraping Pipeline

A config-driven Python pipeline that scrapes articles from multiple websites
and stores them in SQLite, ready for later LLM re-processing (see
`project_detail.txt`). Adding a new site is a JSON file, not a code change.

## Stack

- `requests` + `BeautifulSoup` for static HTML
- `selenium` (headless Chrome) for JS-rendered pages
- `sqlite3` for storage
- `retrying` for retry/backoff on transient failures
- `config/*.json` for global + per-site settings

## Setup

```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash; use .venv\Scripts\Activate.ps1 in PowerShell
pip install -r requirements.txt
```

Selenium needs a Chrome/Chromium binary on the machine; `webdriver-manager`
downloads the matching driver automatically the first time it runs.

## Running it

```bash
python main.py                          # run every enabled site in config/sites/
python main.py --site books_toscrape     # run one site by name
python main.py --site books_toscrape --max-pages 2
python main.py --reset-state             # ignore saved checkpoints, start over
python main.py --force-refresh           # re-fetch even already-stored articles
```

Logs go to `logs/scraper.log` and the console. Data lands in
`data/articles.db` (path configurable in `config/config.json`).

## Included demo sites

Two placeholder sites are wired up to prove the architecture end-to-end
without touching real news sites' infrastructure — both are public sandboxes
built specifically for scraping practice:

- `config/sites/books_toscrape.json` — static HTML, real pagination
  (`requests` + `BeautifulSoup`)
- `config/sites/quotes_toscrape_js.json` — JS-rendered content (Selenium)

Swap these for real news sites by adding new files under `config/sites/`
(see below) — no code changes needed.

## Adding a new site

Drop a new JSON file in `config/sites/`, e.g. `config/sites/my_news_site.json`:

```jsonc
{
  "name": "my_news_site",
  "domain": "example-news.com",
  "enabled": true,
  "render": false,               // true if the site needs JS rendering (Selenium)
  "start_urls": ["https://example-news.com/latest"],

  "list_page": {
    "item_selector": "article.card",     // one CSS selector per article on a listing page
    "link_selector": "a.card-link",      // link to the article's detail page, relative to item_selector
    "link_attr": "href"
  },

  "pagination": {
    "enabled": true,
    "next_selector": "a.pagination-next",
    "next_attr": "href",
    "max_pages": 20                       // safety cap per run; omit/null for unbounded
  },

  "article": {
    "title_selector": "h1.headline",
    "body_selector": "div.article-body",
    "published_at_selector": "time.published",
    "published_at_attr": "datetime",      // read an attribute instead of text; null to read text
    "category_selector": "a.category",
    "author_selector": "span.byline",
    "featured_image_selector": "figure.hero img",
    "featured_image_attr": "src",
    "remove_selectors": ["script", "style", "nav", ".ad", ".comments", ".related-articles"],
    "metadata_selectors": {
      "tags": "div.tags a"
    }
  },

  "request": {
    "delay_seconds": 2,
    "jitter_seconds": 1,
    "headers": {}
  }
}
```

Notes:

- Any selector can be `null` if the site doesn't have that field.
- `item_is_article: true` under `list_page` (see `quotes_toscrape_js.json`)
  is for sites where the listing page already contains the full article
  content — no detail-page fetch happens for those items.
- Global defaults (timeouts, retries, user agent, robots.txt enforcement)
  live in `config/config.json` and apply unless a site overrides them.

## Data model

`data/articles.db`:

- `articles_raw` — one row per article: `domain`, `article_id` (hash of the
  canonical URL), `title`, `slug`, `body`, `published_at`, `category_id`,
  `author_id`, `featured_image_id`, `metadata` (JSON), `url`, `content_hash`,
  timestamps. Unique on `(domain, article_id)` and on `url`.
- `categories`, `authors`, `featured_images` — normalized lookup tables,
  scoped per domain, referenced from `articles_raw` by foreign key.
- `scrape_state` — one checkpoint row per domain (`last_url`, `last_page`)
  used to resume a killed/interrupted run without re-scraping finished pages.

## Politeness / robustness built in

- **robots.txt** is checked per domain before every request (`scraper/robots.py`);
  disallowed URLs are skipped and logged, not fetched.
- **Rate limiting**: a configurable delay + random jitter is enforced per
  domain between requests (`scraper/rate_limiter.py`).
- **Retries**: transient network errors and 429/5xx responses are retried
  with backoff via the `retrying` library (`scraper/fetchers/`).
- **Dedup**: articles already stored (by `domain` + `article_id`) are
  detected before the detail page is even fetched, so re-runs don't
  re-hit pages they already have. If content changed since last time
  (`content_hash` differs), the row is updated instead of duplicated.
- **Resume**: after each listing page is fully processed, its domain's
  checkpoint is saved; a killed run picks back up from there instead of
  restarting from page 1 (`--reset-state` to opt out).
- **Noise removal**: `remove_selectors` strips ads/nav/comment/script
  elements from the DOM before body text is extracted.

## Tests

```bash
python -m pytest -q
```

25 tests cover the parser (against saved HTML fixtures, no network), the
SQLite layer (insert/update/skip/dedup, lookup tables, resume state), and
pagination logic (via fake fetcher/robots/rate-limiter) — none of them hit
the network, so they're fast and safe to run repeatedly.

A live smoke test was also run against both demo sites to validate the
real end-to-end path (`python main.py --site books_toscrape --max-pages 1`
and `--site quotes_toscrape_js`), confirming static fetch+parse+store,
Selenium fetch+parse+store, checkpointed resume, and dedup skip all work
against real HTTP responses.

## Feeding this into the next stage (LLM re-processing)

`articles_raw` is the durable historical store described in
`project_detail.txt`. Point a separate downstream job at this SQLite file
(read-only) to pull `domain`, `title`, `body`, `published_at`, `category_id`,
and `metadata` per theme/category for LLM analysis and rewriting — this
pipeline's job ends at "clean data in SQLite."
