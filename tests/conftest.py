from __future__ import annotations

import gzip
from pathlib import Path

import orjson
import pytest

from nerdbot.tarkov import Catalog, build_catalog

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def catalog() -> Catalog:
    items = gzip.decompress((FIXTURES / "regular_items.json.gz").read_bytes())
    translations = gzip.decompress((FIXTURES / "regular_items_en.json.gz").read_bytes())
    traders = orjson.loads((FIXTURES / "traders.json").read_bytes())
    return build_catalog("regular", items, translations, traders)
