import pytest

from scraper.db import Database


@pytest.fixture
def db(tmp_path):
    database = Database(str(tmp_path / "test.db"))
    yield database
    database.close()


def make_article(**overrides):
    article = {
        "domain": "example.com",
        "article_id": "abc123",
        "title": "Hello World",
        "slug": "hello-world",
        "body": "Some body text.",
        "published_at": "2024-01-01T00:00:00Z",
        "category_id": None,
        "author_id": None,
        "featured_image_id": None,
        "metadata": {"tags": ["a", "b"]},
        "url": "https://example.com/hello-world",
        "content_hash": "hash-v1",
    }
    article.update(overrides)
    return article


def test_upsert_article_inserts_new(db):
    result = db.upsert_article(make_article())
    assert result == "inserted"
    row = db.conn.execute("SELECT * FROM articles_raw WHERE article_id = ?", ("abc123",)).fetchone()
    assert row["title"] == "Hello World"
    assert row["url"] == "https://example.com/hello-world"


def test_upsert_article_skips_when_unchanged(db):
    db.upsert_article(make_article())
    result = db.upsert_article(make_article())
    assert result == "skipped"


def test_upsert_article_updates_when_content_hash_changes(db):
    db.upsert_article(make_article())
    result = db.upsert_article(make_article(title="Hello World, Updated", content_hash="hash-v2"))
    assert result == "updated"
    row = db.conn.execute("SELECT title FROM articles_raw WHERE article_id = ?", ("abc123",)).fetchone()
    assert row["title"] == "Hello World, Updated"


def test_article_exists(db):
    assert db.article_exists("example.com", "abc123") is False
    db.upsert_article(make_article())
    assert db.article_exists("example.com", "abc123") is True


def test_get_or_create_category_is_idempotent(db):
    id1 = db.get_or_create_category("example.com", "Tech")
    id2 = db.get_or_create_category("example.com", "Tech")
    assert id1 == id2

    id_other_domain = db.get_or_create_category("other.com", "Tech")
    assert id_other_domain != id1


def test_get_or_create_returns_none_for_empty_name(db):
    assert db.get_or_create_category("example.com", None) is None
    assert db.get_or_create_author("example.com", "") is None
    assert db.get_or_create_featured_image("example.com", None) is None


def test_scrape_state_roundtrip(db):
    assert db.get_state("example.com") is None

    db.set_state("example.com", "https://example.com/page-2", 2)
    state = db.get_state("example.com")
    assert state["last_url"] == "https://example.com/page-2"
    assert state["last_page"] == 2

    db.set_state("example.com", "https://example.com/page-3", 3)
    state = db.get_state("example.com")
    assert state["last_page"] == 3

    db.reset_state("example.com")
    assert db.get_state("example.com") is None
