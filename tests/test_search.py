from __future__ import annotations

import pytest

CONFIDENT = {
    "ledx": "LEDX Skin Transilluminator",
    "moonshine": "Bottle of Fierce Hatchling moonshine",
    "gpu": "Graphics card",
    "graphics card": "Graphics card",
    "salewa": "Salewa first aid kit",
    "igolnik": "5.45x39mm PPBS gs Igolnik",
    "m995": "5.56x45mm M995",
    "m855a1": "5.56x45mm M855A1",
    "5.56 m855a1": "5.56x45mm M855A1",
    "diary": "Diary",
    "ratchet": "Ratchet wrench",
    "tetriz": "Tetriz portable game console",
    "vaseline": "Vaseline balm",
}


@pytest.mark.parametrize(("query", "expected"), sorted(CONFIDENT.items()))
def test_confident_matches(catalog, query, expected):
    item, candidates = catalog.index.resolve(query)
    assert item is not None, f"{query!r} was ambiguous: {[c.name for c in candidates[:4]]}"
    assert item.name == expected


@pytest.mark.parametrize(
    ("query", "should_include"),
    [
        ("mp5", "HK MP5 9x19 submachine gun (Navy 3 Round Burst)"),
        ("labs card", "TerraGroup Labs access keycard"),
        ("bitcoin", "Physical Bitcoin"),
        ("flash drive", "Secure Flash drive"),
        ("red keycard", "TerraGroup Labs keycard (Red)"),
        ("labs keycard", "TerraGroup Labs access keycard"),
    ],
)
def test_ambiguous_queries_offer_the_right_choice(catalog, query, should_include):
    item, candidates = catalog.index.resolve(query)
    names = [item.name] if item else [c.name for c in candidates]
    assert should_include in names


def test_search_filter(catalog):
    hits = catalog.index.search("m855", where=lambda i: i.ammo is not None)
    assert hits and all(item.ammo for item, _ in hits)
