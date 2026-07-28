import hashlib
import re
import unicodedata

from bs4 import BeautifulSoup, Tag

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_WHITESPACE_RE = re.compile(r"\s+")


def slugify(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = _SLUG_RE.sub("-", text.lower()).strip("-")
    return text


def make_article_id(url: str) -> str:
    """Stable, content-independent identifier derived from the canonical URL."""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def content_hash(*parts: str) -> str:
    """Hash of extracted content, used to detect changed articles on re-scrape."""
    joined = "␟".join(p or "" for p in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def strip_noise(soup_or_tag, remove_selectors=None):
    """Remove ads/nav/comment/script noise elements in place before text extraction."""
    if soup_or_tag is None:
        return soup_or_tag
    for selector in remove_selectors or []:
        for el in soup_or_tag.select(selector):
            el.decompose()
    return soup_or_tag


def clean_text(value) -> str:
    """Collapse whitespace and strip tags down to plain, readable text."""
    if value is None:
        return ""
    if isinstance(value, Tag):
        text = value.get_text(separator=" ", strip=True)
    else:
        text = str(value)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text


def html_to_soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")
