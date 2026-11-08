from __future__ import annotations

from nerdbot.cogs.game import boss_embed, boss_embed_all
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


def test_combined_embed_merges_identical_modes(boss_book):
    import copy

    boss = next(iter(boss_book.bosses.values()))
    same = boss_embed_all({"regular": boss, "pve": copy.deepcopy(boss)})
    check_embed(same)
    assert len(same.fields) == len(boss.maps)
    assert "PvE" not in "".join(f.name for f in same.fields)

    other = copy.deepcopy(boss)
    other.maps[0].chance_low = other.maps[0].chance_high = 0.01
    diff = boss_embed_all({"regular": boss, "pve": other})
    check_embed(diff)
    names = [f.name for f in diff.fields]
    assert len(names) == len(boss.maps) + 1
    assert any("PvP" in n for n in names) and any("PvE" in n for n in names)


def test_zone_fallback_names():
    from nerdbot.tarkov.bosses import _zone_fallback

    assert _zone_fallback("ZoneGasStation") == "Gas Station"
    assert _zone_fallback("Zone1BD1PortAmbush1") == "Port Ambush"
    assert _zone_fallback("Zone2VSRFPassMiddle15") == "Pass Middle"
    assert _zone_fallback("BotZoneMash_t1") == "Mash"
    assert _zone_fallback("Zone2ScavPort29") == "Scav Port"
    assert _zone_fallback("Zone1BD1HangarBD11") == "Hangar"
    assert _zone_fallback("Zone2VSRFExit33") == "Exit"


def test_goon_reports_parsed_newest_first():
    import orjson

    from nerdbot.tarkov import build_bosses

    maps = {"data": {
        "maps": {"m1": {"id": "m1", "name": "m1 Name", "bosses": []},
                 "m2": {"id": "m2", "name": "m2 Name", "bosses": []}},
        "mobs": {},
        "goonReports": [
            {"map": "m1", "timestamp": "1794000000000"},
            {"map": "m2", "timestamp": "1794100000000"},
            {"map": "gone", "timestamp": "1794200000000"},  # unknown map: skipped
            {"map": "m1", "timestamp": "nope"},  # bad timestamp: skipped
        ],
    }}
    tr = {"data": {"m1 Name": "Customs", "m2 Name": "Shoreline"}}
    book = build_bosses(orjson.dumps(maps), orjson.dumps(tr))
    assert [g.map_name for g in book.goon_reports] == ["Shoreline", "Customs"]


def test_goons_embed(boss_book):
    from datetime import datetime, timedelta, timezone

    from nerdbot.cogs.game import goons_embed
    from nerdbot.tarkov import GoonReport

    now = datetime(2026, 11, 8, 12, tzinfo=timezone.utc)
    knight = boss_book.bosses["Knight"]
    reports = [GoonReport("Customs", now - timedelta(hours=1)), GoonReport("Lighthouse", now - timedelta(hours=5))]
    e = goons_embed(reports, knight, "regular", now)
    check_embed(e)
    assert "Customs" in e.description and "out of date" not in e.description
    assert {f.name for f in e.fields} == {"Recent reports", "Spawn chance"}

    stale = goons_embed([GoonReport("Woods", now - timedelta(days=2))], knight, "pve", now)
    check_embed(stale)
    assert "out of date" in stale.description

    empty = goons_embed([], None, "pvp-season", now)
    check_embed(empty)
    assert "No recent sightings" in empty.description


def test_restocks_parsed_and_rendered():
    from datetime import datetime, timezone

    import orjson

    from nerdbot.cogs.game import restocks_embed
    from nerdbot.tarkov import parse_restocks

    two = [{"level": 1}, {"level": 2}]
    traders = {"data": {
        "a": {"name": "a Nickname", "normalizedName": "prapor", "resetTime": "2026-11-08T12:42:25.000Z", "levels": two},
        "b": {"name": "b Nickname", "normalizedName": "therapist", "resetTime": "2026-11-08T11:45:43.000Z", "levels": two},
        "c": {"name": "c Nickname", "normalizedName": "btr-driver", "resetTime": "2026-11-08T11:00:00.000Z", "levels": [{"level": 1}]},
        "d": {"name": "d Nickname", "normalizedName": "ref", "resetTime": None, "levels": two},
    }}
    names = {"data": {"a Nickname": "Prapor", "b Nickname": "Therapist"}}
    restocks = parse_restocks(orjson.dumps(traders), orjson.dumps(names))
    assert [r.name for r in restocks] == ["Therapist", "Prapor", "Ref"]  # soonest first, unknown last

    now = datetime(2026, 11, 8, 12, tzinfo=timezone.utc)
    e = restocks_embed(restocks, "regular", now)
    check_embed(e)
    lines = e.description.splitlines()
    assert "restocking now" in lines[0] and "<t:" in lines[1] and "unknown" in lines[2]
