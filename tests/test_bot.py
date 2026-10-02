"""Boot the bot offline with fixture data and exercise every renderer."""

from __future__ import annotations

import json

import discord
import pytest

from nerdbot.bot import EXTENSIONS, NerdBot
from nerdbot.circle.knowledge import FAQ, HOT_SACRIFICES, RECIPES
from nerdbot.circle.planner import PlanOptions, plan
from nerdbot.cogs.circle import hot_embed, parse_combo, recipe_pages, thresholds_reply
from nerdbot.cogs.market import _split_mode, ammo_embed, price_embed
from nerdbot.config import Settings


class FakeStore:
    def __init__(self, catalog):
        self.catalog = catalog
        self.loaded_modes = ["regular"]

    def peek(self, mode):
        return self.catalog

    async def get(self, mode):
        return self.catalog


@pytest.fixture
async def bot(catalog):
    b = NerdBot(Settings(token="test"))
    b.store = FakeStore(catalog)
    for ext in EXTENSIONS:
        await b.load_extension(ext)
    yield b
    await b.session.close() if b.session else None


def check_embed(e: discord.Embed) -> None:
    assert len(e) <= 6000
    assert len(e.fields) <= 25
    if e.title:
        assert len(e.title) <= 256
    if e.description:
        assert len(e.description) <= 4096
    for f in e.fields:
        assert 0 < len(f.name) <= 256, f.name
        assert 0 < len(f.value) <= 1024, (f.name, len(f.value))


def check_reply(reply: dict) -> None:
    check_embed(reply["embed"])


async def test_slash_commands_serialize(bot):
    names = set()
    for cmd in bot.tree.get_commands():
        payload = cmd.to_dict(bot.tree)
        json.dumps(payload)
        names.add(cmd.name)
        for opt in payload.get("options", []):
            assert len(opt["description"]) <= 100, opt
            for sub in opt.get("options", []):
                assert len(sub["description"]) <= 100, sub
    assert {"price", "ammo", "thresholds", "circle", "faq", "help", "status", "bosses"} <= names
    circle = bot.tree.get_command("circle")
    assert {c.name for c in circle.commands} == {"cheapest", "check", "value", "hot", "recipes"}


async def test_prefix_commands_registered(bot):
    assert {c.name for c in bot.commands} >= {"thresholds", "price", "hot", "faq", "help"}
    assert bot.get_command("ask") is not None and bot.get_command("threshold") is not None


@pytest.mark.parametrize(
    "query",
    ["ledx", "m995", "graphics card", "NFM THOR Integrated Carrier body armor", "Roubles", "Diary",
     "HK MP5 9x19 submachine gun (Navy 3 Round Burst) Default"],
)
def test_price_embeds(catalog, query):
    item, candidates = catalog.index.resolve(query)
    item = item or candidates[0]
    check_embed(price_embed(item, catalog))


@pytest.mark.parametrize("query", ["m995", "igolnik", "12/70 7mm buckshot", "5.45x39mm BS gs"])
def test_ammo_embeds(catalog, query):
    item, candidates = catalog.index.resolve(query, where=lambda i: i.ammo is not None)
    item = item or candidates[0]
    e = ammo_embed(item, catalog)
    check_embed(e)
    assert any("lineup" in f.name for f in e.fields)


def test_thresholds_replies():
    for total in (None, 0, 385_000, 400_000, 10_000_000):
        reply = thresholds_reply(total)
        check_reply(reply)
        assert reply["file"].filename == "thresholds.png"


async def test_cheapest_embeds(bot, catalog):
    cog = bot.get_cog("Circle")
    moonshine, _ = catalog.index.resolve("moonshine")
    for options, pinned, count in [
        (PlanOptions("flea"), None, 0),
        (PlanOptions("trader", 1), None, 0),
        (PlanOptions("flea"), moonshine, 2),
        (PlanOptions("flea"), moonshine, 5),
    ]:
        combo = plan(catalog, 400_000, options, pinned, count)
        e = cog._cheapest_embed(catalog, 400_000, options, combo, pinned, count)
        check_embed(e)
    check_embed(cog._cheapest_embed(catalog, 400_000, PlanOptions("trader", 1), None, None, 0))


async def test_check_and_value(bot, catalog):
    cog = bot.get_cog("Circle")
    ok = cog._check_reply(catalog, "2x moonshine + 1 graphics card")
    check_reply(ok)
    assert "file" in ok
    check_reply(cog._check_reply(catalog, "6x moonshine"))
    check_reply(cog._check_reply(catalog, "1x flash drive, 2 bitcoin"))
    check_reply(cog._check_reply(catalog, "zzzzqqq"))
    for name in ("Graphics card", "LEDX Skin Transilluminator", "HK MP5 9x19 submachine gun (Navy 3 Round Burst) Default"):
        item, cands = catalog.index.resolve(name)
        check_embed(cog._value_embed(item or cands[0], catalog))


def test_hot_and_recipes(catalog):
    e = hot_embed(catalog)
    check_embed(e)
    assert len(e.fields) == len(HOT_SACRIFICES)
    assert "Est. cost **~" in e.fields[0].value
    pages = recipe_pages(list(RECIPES), "Recipes")
    assert sum(len(p.fields) for p in pages) == len(RECIPES)
    for p in pages:
        check_embed(p)


async def test_faq_answers(bot):
    cog = bot.get_cog("Faq")
    for question in [
        "what do I need for a 6h",
        "can I sacrifice a pilgrim?",
        "can i sacrifice graphics card",
        "can I use the zzzz thing in the circle",
        "will a 6h ever give me a ledx",
        "what's the weather",
        "faq:base-value",
        *(e.question for e in FAQ),
    ]:
        check_reply(cog.answer(question))
    assert cog.answer("can I sacrifice a pilgrim?")["embed"].title.startswith("No")
    assert cog.answer("can i sacrifice graphics card")["embed"].title.startswith("Yes")
    check_embed(cog.help_embed())


def test_combo_parsing():
    parts = parse_combo("3x Ratchet Wrench & 1x Flash Drive, moonshine x2 + 2 diary")
    assert [(p.count, p.text) for p in parts] == [(3, "Ratchet Wrench"), (1, "Flash Drive"), (2, "moonshine"), (2, "diary")]


def test_prefix_mode_parsing():
    assert _split_mode("ledx pve") == ("ledx", "pve")
    assert _split_mode("ledx") == ("ledx", "regular")
    assert _split_mode("pve") == ("pve", "regular")


async def test_command_sync_hash_is_stable(bot):
    """The sync stamp must not change between identical boots, or we'd resync every restart."""
    guild = None
    payload_a = json.dumps([c.to_dict(bot.tree) for c in bot.tree.get_commands(guild=guild)], sort_keys=True)
    payload_b = json.dumps([c.to_dict(bot.tree) for c in bot.tree.get_commands(guild=guild)], sort_keys=True)
    assert payload_a == payload_b
