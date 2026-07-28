from scraper.utils import clean_text, content_hash, make_article_id, slugify


def test_slugify_basic():
    assert slugify("A Light in the Attic") == "a-light-in-the-attic"


def test_slugify_strips_punctuation_and_accents():
    assert slugify("Café: Déjà Vu!!") == "cafe-deja-vu"


def test_slugify_empty():
    assert slugify("") == ""
    assert slugify(None) == ""


def test_make_article_id_is_stable_and_url_specific():
    id1 = make_article_id("https://example.com/a")
    id2 = make_article_id("https://example.com/a")
    id3 = make_article_id("https://example.com/b")
    assert id1 == id2
    assert id1 != id3
    assert len(id1) == 16


def test_content_hash_changes_when_content_changes():
    h1 = content_hash("title", "body", "2024-01-01")
    h2 = content_hash("title", "body", "2024-01-01")
    h3 = content_hash("title", "different body", "2024-01-01")
    assert h1 == h2
    assert h1 != h3


def test_clean_text_collapses_whitespace():
    assert clean_text("  hello   \n\n  world  ") == "hello world"


def test_clean_text_none():
    assert clean_text(None) == ""
