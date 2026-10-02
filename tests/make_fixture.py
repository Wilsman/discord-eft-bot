"""Regenerate the trimmed tarkov.dev fixture used by the tests.

    python tests/make_fixture.py

Downloads the live regular-mode feed and keeps only the fields the bot reads, so the
fixture stays small enough to commit.
"""
from __future__ import annotations

import gzip
import urllib.request
from pathlib import Path

import orjson

BASE = "https://json.tarkov.dev"
OUT = Path(__file__).parent / "fixtures"
DROP = {"properties", "containsItems", "conflictingItems", "conflictingSlotIds", "conflictingCategories",
        "description", "baseImageLink", "inspectImageLink", "image512pxLink", "image8xLink",
        "handbookCategories", "backgroundColor"}
AMMO_PROPS = {"propertiesType", "caliber", "damage", "penetrationPower", "armorDamage",
              "fragmentationChance", "projectileCount", "initialSpeed", "tracer", "ammoType"}


def get(path: str) -> bytes:
    req = urllib.request.Request(f"{BASE}/{path}", headers={"Accept-Encoding": "gzip", "User-Agent": "nerdbot-tests"})
    with urllib.request.urlopen(req) as r:
        raw = r.read()
        return gzip.decompress(raw) if r.headers.get("Content-Encoding") == "gzip" else raw


def main() -> None:
    OUT.mkdir(exist_ok=True)
    doc = orjson.loads(get("regular/items"))
    data = doc["data"]
    slim = {}
    for iid, item in data["items"].items():
        props = item.get("properties") or {}
        out = {k: v for k, v in item.items() if k not in DROP}
        if props.get("propertiesType") == "ItemPropertiesAmmo":
            out["properties"] = {k: v for k, v in props.items() if k in AMMO_PROPS}
        slim[iid] = out
    payload = {"data": {"items": slim, "itemCategories": data["itemCategories"], "fleaMarket": data["fleaMarket"]}}
    (OUT / "regular_items.json.gz").write_bytes(gzip.compress(orjson.dumps(payload), 9))
    (OUT / "regular_items_en.json.gz").write_bytes(gzip.compress(get("regular/items_en"), 9))
    traders = orjson.loads(get("regular/traders"))["data"]
    names = orjson.loads(get("regular/traders_en"))["data"]
    (OUT / "traders.json").write_bytes(orjson.dumps({tid: names[t["name"]] for tid, t in traders.items()}))


if __name__ == "__main__":
    main()
