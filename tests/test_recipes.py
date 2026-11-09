from __future__ import annotations

import json
from pathlib import Path

import pytest

from nerdbot.circle.recipes import Outcome, item_name, match_score, names, parse_book, reward_worth, search
from nerdbot.cogs.recipes import RecipeBrowser, RecipeCardView, list_pages, recipe_card, recipe_reply
from test_bot import check_embed

FIXTURE = Path(__file__).parent / "fixtures" / "recipes.json"


@pytest.fixture(scope="module")
def book():
    return parse_book(json.loads(FIXTURE.read_text(encoding="utf-8")))


def test_parse(book):
    assert len(book.active) > 50
    assert all(r.inputs and r.url.startswith("https://") for r in book.all)
    assert any(r.outcomes for r in book.active)


def test_parse_rejects_garbage():
    with pytest.raises(ValueError):
        parse_book({"nope": 1})


@pytest.mark.parametrize(
    "entry, expected",
    [
        ("3x Fence figurine", (3, "Fence figurine")),
        ("Cultist figurine \u00d75", (5, "Cultist figurine")),
        ("Light bulb \u00d72", (2, "Light bulb")),
        ("Medical bloodset", (1, "Medical bloodset")),
        ("5x BD dogtag \u2022| Ferrum", (5, "BD dogtag \u2022| Ferrum")),
    ],
)
def test_item_name(entry, expected):
    assert item_name(entry) == expected


def test_search_ranks_and_filters(book):
    found = search(book, "fence", "regular")
    assert found and "Fence figurine" in found[0].title
    duck_pvp = search(book, "duck figurine", "regular")
    assert any(r.restriction == "pvp-only" for r in duck_pvp)
    assert not any(r.restriction == "pvp-only" for r in search(book, "duck figurine", "pve"))
    assert not any(r.restriction == "season-only" for r in search(book, "dogtag", "regular"))
    assert any(r.restriction == "season-only" for r in search(book, "dogtag", "pvp-season"))
    assert search(book, "zzzqqqxx", "regular") == []


def test_search_needs_every_word(book):
    assert match_score("den figurine", "1x Elvisvista figurine") < 80
    assert match_score("fence figrine", "1x Fence figurine") >= 80
    den = search(book, "den figurine", "regular")
    assert den and all("den" in r.haystack.lower() for r in den)
    assert "Den figurine" in den[0].title


def test_partial_worth(book, catalog):
    mastichin = search(book, "mastichin", "regular")[0]
    worth = reward_worth(catalog, mastichin)
    assert worth is not None and worth.partial and worth.low > 0


def test_expired_sort_last(book):
    import dataclasses

    retired = dataclasses.replace(book.active[0], expired=True)
    mixed = type(book)([*book.active[1:]], [retired])
    found = search(mixed, book.active[0].inputs[0], "regular")
    assert found[-1].expired


def test_names(book):
    all_names = names(book)
    assert "Fence figurine" in all_names
    assert not any(n.startswith("1x ") for n in all_names)


def test_pool_outcome_range(catalog):
    pool = Outcome(("1x Graphics card", "1x Physical Bitcoin"), "You always get 2 items from this pool.")
    assert pool.pool_size == 2


def test_cards_render(book, catalog):
    for r in book.all:
        check_embed(recipe_card(r, catalog))
    fence = search(book, "fence", "regular")[0]
    e = recipe_card(fence, catalog)
    assert "Community" in [f.name for f in e.fields]
    for r in book.active:
        if r.outcomes:
            reward_worth(catalog, r)  # must not raise


def test_doubtful_flag(book, catalog):
    dogtag = search(book, "dogtag", "pvp-season")[0]
    assert dogtag.votes.doubtful
    assert "Only" in (recipe_card(dogtag, catalog).description or "")


def test_list_pages(book):
    found = search(book, "figurine", "regular")
    pages = list_pages(found, "figurine", "regular")
    assert len(pages) > 1
    for p in pages:
        check_embed(p)


async def test_reply_kinds(book, catalog):
    reply = await recipe_reply(book, catalog, "figurine", 1)
    assert isinstance(reply["view"], RecipeBrowser) and len(reply["view"].picker.options) <= 25
    reply = await recipe_reply(book, catalog, "Wedge figurine Black Division Team Leader Operator", 1)
    assert reply.get("view") is not None
    reply = await recipe_reply(book, catalog, "zzzqqqxx", 1)
    assert "view" not in reply and reply["embed"].title == "No recipes found"
    one = [r for r in book.active if len(search(book, r.inputs[0], "regular")) == 1]
    if one:
        reply = await recipe_reply(book, catalog, one[0].inputs[0], 1)
        assert isinstance(reply["view"], RecipeCardView)
        assert "file" not in reply  # no session, so no picture


def test_render_picture_offline():
    from nerdbot.circle.recipe_art import Tile, render_recipe

    many = [Tile(1, f"Item {i}", None) for i in range(9)]
    png = render_recipe([Tile(5, "BD dogtag", None)], many, {}, random=True)
    assert png.startswith(b"\x89PNG")
    assert render_recipe([Tile(1, "Thing", None)], [], {}).startswith(b"\x89PNG")
