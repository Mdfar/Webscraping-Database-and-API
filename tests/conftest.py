import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"
CONFIG_DIR = Path(__file__).parent.parent / "config"


def read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def load_site_config(name: str) -> dict:
    with open(CONFIG_DIR / "sites" / f"{name}.json", "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def books_config():
    return load_site_config("books_toscrape")


@pytest.fixture
def quotes_config():
    return load_site_config("quotes_toscrape_js")
