from scraper.parser import extract_article, find_next_page, parse_list_page

from .conftest import read_fixture


def test_parse_list_page_books_returns_link_items(books_config):
    html = read_fixture("books_list_page1.html")
    page_url = "https://books.toscrape.com/catalogue/page-1.html"

    items = parse_list_page(html, page_url, books_config)

    assert len(items) == 2
    assert all(item.mode == "link" for item in items)
    assert items[0].url == "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html"
    assert items[1].url == "https://books.toscrape.com/catalogue/soumission_998/index.html"


def test_find_next_page_books(books_config):
    html = read_fixture("books_list_page1.html")
    page_url = "https://books.toscrape.com/catalogue/page-1.html"

    next_url = find_next_page(html, page_url, books_config["pagination"])

    assert next_url == "https://books.toscrape.com/catalogue/page-2.html"


def test_find_next_page_none_on_last_page(books_config):
    html = read_fixture("books_list_page2.html")
    page_url = "https://books.toscrape.com/catalogue/page-2.html"

    assert find_next_page(html, page_url, books_config["pagination"]) is None


def test_extract_article_books_detail_page(books_config):
    html = read_fixture("books_detail_page.html")
    url = "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html"

    from scraper.utils import html_to_soup
    soup = html_to_soup(html)

    article = extract_article(soup, url, books_config["domain"], books_config["article"])

    assert article["title"] == "A Light in the Attic"
    assert "Shel Silverstein" in article["body"]
    assert article["category"] == "Poetry"
    assert article["featured_image"].startswith("https://books.toscrape.com/")
    assert article["metadata"]["price"] == "£51.77"
    assert "In stock" in article["metadata"]["availability"]
    # noise removed: nav text must not leak into the parsed tree used for body extraction
    assert "Ignore this nav noise" not in str(soup)


def test_parse_list_page_quotes_returns_inline_items(quotes_config):
    html = read_fixture("quotes_list_page1.html")
    page_url = "https://quotes.toscrape.com/js/"

    items = parse_list_page(html, page_url, quotes_config)

    assert len(items) == 2
    assert all(item.mode == "inline" for item in items)
    assert items[0].tag is not None
    assert items[0].url == f"{page_url}#item-0"


def test_extract_article_quotes_inline(quotes_config):
    html = read_fixture("quotes_list_page1.html")
    page_url = "https://quotes.toscrape.com/js/"
    items = parse_list_page(html, page_url, quotes_config)

    article = extract_article(items[0].tag, items[0].url, quotes_config["domain"], quotes_config["article"])

    assert "world as we have created it" in article["body"]
    assert article["author"] == "Albert Einstein"
    assert article["metadata"]["tags"] == ["change", "deep-thoughts"]


def test_find_next_page_quotes(quotes_config):
    html = read_fixture("quotes_list_page1.html")
    page_url = "https://quotes.toscrape.com/js/"

    next_url = find_next_page(html, page_url, quotes_config["pagination"])

    assert next_url == "https://quotes.toscrape.com/js/page/2/"
