from __future__ import annotations

from nerdbot.cogs.game import boss_embed
from test_bot import check_embed


def test_bosses_grouped_by_name(boss_book):
    names = set(boss_book.names)
    assert {"Reshala", "Killa", "Tagilla", "Knight", "Rogue", "Black Div."} <= names
    assert "bossBully" not in names  # ids are translated


def test_reshala_details(boss_book):
    reshala = boss_book.bosses["Reshala"]
    customs = next(m for m in reshala.maps if m.map_name == "Customs")
    assert {z for z, _ in customs.zones} >= {"Dorms", "New Gas Station"}
    guard = next(e for e in customs.escorts if e.name == "Reshala Guard")
    assert (guard.low, guard.high) == (2, 4)
    assert reshala.health and reshala.portrait


def test_resolve_and_aliases(boss_book):
    assert boss_book.resolve("reshala")[0].name == "Reshala"
    assert boss_book.resolve("RESHALA")[0].name == "Reshala"
    assert boss_book.search("kilia")[0][0].name == "Killa"
    boss, alias = boss_book.search("big pipe")[0]
    assert boss.name == "Knight" and alias == "Big Pipe"
    assert len(boss_book.search("")) == min(25, len(boss_book.bosses))


def test_boss_embeds_fit(boss_book):
    for boss in boss_book.bosses.values():
        e = boss_embed(boss, "regular")
        check_embed(e)
        assert e.fields


def test_zone_fallback_names():
    from nerdbot.tarkov.bosses import _zone_fallback

    assert _zone_fallback("ZoneGasStation") == "Gas Station"
    assert _zone_fallback("Zone1BD1PortAmbush1") == "Port Ambush"
    assert _zone_fallback("Zone2VSRFPassMiddle15") == "Pass Middle"
    assert _zone_fallback("BotZoneMash_t1") == "Mash"
    assert _zone_fallback("Zone2ScavPort29") == "Scav Port"
    assert _zone_fallback("Zone1BD1HangarBD11") == "Hangar"
    assert _zone_fallback("Zone2VSRFExit33") == "Exit"
