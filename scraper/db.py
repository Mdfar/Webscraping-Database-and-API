import json
import logging
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT NOT NULL,
    name TEXT NOT NULL,
    UNIQUE(domain, name)
);

CREATE TABLE IF NOT EXISTS authors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT NOT NULL,
    name TEXT NOT NULL,
    UNIQUE(domain, name)
);

CREATE TABLE IF NOT EXISTS featured_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT NOT NULL,
    url TEXT NOT NULL,
    UNIQUE(domain, url)
);

CREATE TABLE IF NOT EXISTS articles_raw (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT NOT NULL,
    article_id TEXT NOT NULL,
    title TEXT,
    slug TEXT,
    body TEXT,
    published_at TEXT,
    category_id INTEGER REFERENCES categories(id),
    author_id INTEGER REFERENCES authors(id),
    featured_image_id INTEGER REFERENCES featured_images(id),
    metadata TEXT,
    url TEXT NOT NULL,
    content_hash TEXT,
    scraped_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(domain, article_id),
    UNIQUE(url)
);

CREATE TABLE IF NOT EXISTS scrape_state (
    domain TEXT PRIMARY KEY,
    last_url TEXT,
    last_page INTEGER DEFAULT 0,
    updated_at TEXT
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON;")
        self.init_schema()

    def init_schema(self) -> None:
        with self.conn:
            self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    # -- lookup tables ----------------------------------------------------

    def get_or_create_category(self, domain: str, name: str):
        if not name:
            return None
        with self.conn:
            self.conn.execute(
                "INSERT OR IGNORE INTO categories (domain, name) VALUES (?, ?)",
                (domain, name),
            )
        row = self.conn.execute(
            "SELECT id FROM categories WHERE domain = ? AND name = ?", (domain, name)
        ).fetchone()
        return row["id"] if row else None

    def get_or_create_author(self, domain: str, name: str):
        if not name:
            return None
        with self.conn:
            self.conn.execute(
                "INSERT OR IGNORE INTO authors (domain, name) VALUES (?, ?)",
                (domain, name),
            )
        row = self.conn.execute(
            "SELECT id FROM authors WHERE domain = ? AND name = ?", (domain, name)
        ).fetchone()
        return row["id"] if row else None

    def get_or_create_featured_image(self, domain: str, url: str):
        if not url:
            return None
        with self.conn:
            self.conn.execute(
                "INSERT OR IGNORE INTO featured_images (domain, url) VALUES (?, ?)",
                (domain, url),
            )
        row = self.conn.execute(
            "SELECT id FROM featured_images WHERE domain = ? AND url = ?",
            (domain, url),
        ).fetchone()
        return row["id"] if row else None

    # -- articles -----------------------------------------------------------

    def upsert_article(self, article: dict) -> str:
        """Insert a new article, update an existing one whose content changed,
        or skip one that is unchanged. Dedup key is (domain, article_id) and
        falls back to url. Returns 'inserted' | 'updated' | 'skipped'.
        """
        existing = self.conn.execute(
            "SELECT id, content_hash FROM articles_raw WHERE domain = ? AND article_id = ?",
            (article["domain"], article["article_id"]),
        ).fetchone()

        metadata_json = json.dumps(article.get("metadata") or {}, ensure_ascii=False)
        now = _now()

        if existing is None:
            with self.conn:
                self.conn.execute(
                    """
                    INSERT INTO articles_raw (
                        domain, article_id, title, slug, body, published_at,
                        category_id, author_id, featured_image_id, metadata,
                        url, content_hash, scraped_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        article["domain"],
                        article["article_id"],
                        article.get("title"),
                        article.get("slug"),
                        article.get("body"),
                        article.get("published_at"),
                        article.get("category_id"),
                        article.get("author_id"),
                        article.get("featured_image_id"),
                        metadata_json,
                        article["url"],
                        article.get("content_hash"),
                        now,
                        now,
                    ),
                )
            return "inserted"

        if existing["content_hash"] == article.get("content_hash"):
            return "skipped"

        with self.conn:
            self.conn.execute(
                """
                UPDATE articles_raw SET
                    title = ?, slug = ?, body = ?, published_at = ?,
                    category_id = ?, author_id = ?, featured_image_id = ?,
                    metadata = ?, url = ?, content_hash = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    article.get("title"),
                    article.get("slug"),
                    article.get("body"),
                    article.get("published_at"),
                    article.get("category_id"),
                    article.get("author_id"),
                    article.get("featured_image_id"),
                    metadata_json,
                    article["url"],
                    article.get("content_hash"),
                    now,
                    existing["id"],
                ),
            )
        return "updated"

    def article_exists(self, domain: str, article_id: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM articles_raw WHERE domain = ? AND article_id = ?",
            (domain, article_id),
        ).fetchone()
        return row is not None

    # -- resume state ---------------------------------------------------------

    def get_state(self, domain: str):
        row = self.conn.execute(
            "SELECT domain, last_url, last_page, updated_at FROM scrape_state WHERE domain = ?",
            (domain,),
        ).fetchone()
        return dict(row) if row else None

    def set_state(self, domain: str, last_url: str, last_page: int) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO scrape_state (domain, last_url, last_page, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(domain) DO UPDATE SET
                    last_url = excluded.last_url,
                    last_page = excluded.last_page,
                    updated_at = excluded.updated_at
                """,
                (domain, last_url, last_page, _now()),
            )

    def reset_state(self, domain: str) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM scrape_state WHERE domain = ?", (domain,))
