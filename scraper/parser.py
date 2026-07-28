import logging
from dataclasses import dataclass, field
from urllib.parse import urljoin

from bs4.element import Tag

from .utils import clean_text, content_hash, html_to_soup, make_article_id, slugify

logger = logging.getLogger(__name__)


@dataclass
class ListItem:
    url: str
    mode: str  # "link" (visit a detail page) or "inline" (article data is on the list page itself)
    tag: Tag | None = field(default=None, repr=False)


def parse_list_page(html: str, page_url: str, site_config: dict) -> list[ListItem]:
    soup = html_to_soup(html)
    list_cfg = site_config["list_page"]
    items = soup.select(list_cfg["item_selector"])

    results: list[ListItem] = []
    if list_cfg.get("item_is_article"):
        for idx, item in enumerate(items):
            synthetic_url = f"{page_url}#item-{idx}"
            results.append(ListItem(url=synthetic_url, mode="inline", tag=item))
    else:
        link_selector = list_cfg.get("link_selector")
        link_attr = list_cfg.get("link_attr", "href")
        for item in items:
            link_el = item.select_one(link_selector) if link_selector else item
            if link_el is None or not link_el.has_attr(link_attr):
                continue
            detail_url = urljoin(page_url, link_el[link_attr])
            results.append(ListItem(url=detail_url, mode="link"))

    return results


def find_next_page(html: str, page_url: str, pagination_config: dict) -> str | None:
    if not pagination_config.get("enabled"):
        return None
    soup = html_to_soup(html)
    next_el = soup.select_one(pagination_config["next_selector"])
    if next_el is None:
        return None
    attr = pagination_config.get("next_attr", "href")
    if not next_el.has_attr(attr):
        return None
    return urljoin(page_url, next_el[attr])


def _extract_field(scope: Tag, selector: str | None, attr: str | None = None) -> str | None:
    if not selector:
        return None
    el = scope.select_one(selector)
    if el is None:
        return None
    if attr:
        return el.get(attr)
    return clean_text(el) or None


def _extract_metadata(scope: Tag, metadata_selectors: dict | None) -> dict:
    metadata = {}
    for key, selector in (metadata_selectors or {}).items():
        els = scope.select(selector)
        if not els:
            continue
        if len(els) > 1:
            metadata[key] = [clean_text(e) or " ".join(e.get("class", [])) for e in els]
        else:
            metadata[key] = clean_text(els[0]) or " ".join(els[0].get("class", []))
    return metadata


def extract_article(scope: Tag, url: str, domain: str, article_config: dict) -> dict:
    """Extract article fields from a parsed scope (a full detail page, or an
    inline item tag from a list page), removing configured noise elements first.
    """
    for selector in article_config.get("remove_selectors") or []:
        for el in scope.select(selector):
            el.decompose()

    title = _extract_field(scope, article_config.get("title_selector"))
    body = _extract_field(scope, article_config.get("body_selector"))
    published_at = _extract_field(
        scope,
        article_config.get("published_at_selector"),
        article_config.get("published_at_attr"),
    )
    category = _extract_field(scope, article_config.get("category_selector"))
    author = _extract_field(scope, article_config.get("author_selector"))
    featured_image = _extract_field(
        scope,
        article_config.get("featured_image_selector"),
        article_config.get("featured_image_attr", "src"),
    )
    if featured_image:
        featured_image = urljoin(url, featured_image)
    metadata = _extract_metadata(scope, article_config.get("metadata_selectors"))

    article_id = make_article_id(url)
    slug = slugify(title) if title else slugify(url.rsplit("/", 1)[-1])
    body_hash_input = title or ""
    hash_value = content_hash(body_hash_input, body or "", published_at or "")

    return {
        "domain": domain,
        "article_id": article_id,
        "title": title,
        "slug": slug,
        "body": body,
        "published_at": published_at,
        "category": category,
        "author": author,
        "featured_image": featured_image,
        "metadata": metadata,
        "url": url,
        "content_hash": hash_value,
    }
