"""Boss spawn data from the json.tarkov.dev ``{mode}/maps`` feed.

The feed is ~9 MB per mode (loot positions, extracts, etc.). We keep only the boss
entries and mob details, grouped by display name so ids like ``ExUsec`` and
``exUsecFree`` both become "Rogue".
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import orjson
from rapidfuzz import fuzz, process, utils


@dataclass(slots=True)
class Escort:
    name: str
    low: int
    high: int

    @property
    def count(self) -> str:
        return str(self.low) if self.low == self.high else f"{self.low}-{self.high}"


@dataclass(slots=True)
class BossMap:
    map_name: str
    chance_low: float
    chance_high: float
    zones: list[tuple[str, float]]  # (zone name, chance given the boss spawns)
    escorts: list[Escort]
    spawn_after: int | None = None  # seconds into the raid, when known
    triggered: bool = False  # some spawns wait for a lever, switch, etc.
    groups: int = 1  # how many separate spawn entries the map has

    @property
    def chance(self) -> str:
        low, high = round(self.chance_low * 100), round(self.chance_high * 100)
        return f"{high}%" if low == high else f"{low}-{high}%"


@dataclass(slots=True)
class Boss:
    name: str
    slug: str
    portrait: str | None
    health: int | None
    maps: list[BossMap] = field(default_factory=list)
    aliases: set[str] = field(default_factory=set)  # escort names that point here

    @property
    def url(self) -> str:
        return f"https://tarkov.dev/boss/{self.slug}"


@dataclass(slots=True)
class GoonReport:
    """A player report of where the Goons (Knight, Big Pipe, Birdeye) were seen."""

    map_name: str
    seen_at: datetime


@dataclass(slots=True)
class BossBook:
    bosses: dict[str, Boss]
    goon_reports: list[GoonReport] = field(default_factory=list)  # newest first
    loaded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    _keys: list[str] = field(default_factory=list)
    _owners: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        for boss in self.bosses.values():
            for text in {boss.name, boss.slug, *boss.aliases}:
                self._keys.append(utils.default_process(text))
                self._owners.append(boss.name)

    @property
    def names(self) -> list[str]:
        return sorted(self.bosses, key=str.lower)

    def search(self, query: str, limit: int = 25) -> list[tuple[Boss, str | None]]:
        """Best matches as (boss, alias that matched or None)."""
        q = utils.default_process(query or "")
        if not q:
            return [(self.bosses[n], None) for n in self.names[:limit]]
        hits = process.extract(q, self._keys, scorer=fuzz.WRatio, limit=None, score_cutoff=60)
        out: dict[str, tuple[float, str | None]] = {}
        for key, score, pos in hits:
            boss = self.bosses[self._owners[pos]]
            if key.startswith(q):
                score += 10
            is_alias = key not in (utils.default_process(boss.name), utils.default_process(boss.slug))
            alias = next((a for a in boss.aliases if utils.default_process(a) == key), None) if is_alias else None
            if score > out.get(boss.name, (0, None))[0]:
                out[boss.name] = (score, alias)
        ranked = sorted(out.items(), key=lambda kv: -kv[1][0])
        return [(self.bosses[name], alias) for name, (_, alias) in ranked[:limit]]

    def resolve(self, query: str) -> tuple[Boss | None, list[Boss]]:
        q = (query or "").strip().lower()
        for boss in self.bosses.values():
            if q in (boss.name.lower(), boss.slug):
                return boss, []
        hits = self.search(query, limit=5)
        if len(hits) == 1:
            return hits[0][0], []
        return None, [b for b, _ in hits]


def _zone_fallback(key: str) -> str:
    """Readable name for zones missing from the translations.

    'ZoneGasStation' -> 'Gas Station', '1BD1PortAmbush1' -> 'Port Ambush', 'Mash_t1' -> 'Mash'.
    """
    raw = key
    key = re.sub(r"^(Bot)?Zone_?", "", key)
    key = re.sub(r"^\d*(BD|VSRF)?\d*", "", key)  # Terminal's wave prefixes
    key = re.sub(r"(_t\d+|BD\d*|\d+)$", "", key)
    key = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", key).replace("_", " ").strip()
    return key or raw


def _escort_counts(entry: dict[str, Any], name_of) -> dict[str, tuple[int, int]]:
    """Total guard count range per guard name for one spawn entry."""
    totals: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for esc in entry.get("escorts") or ():
        counts = [int(a.get("count") or 0) for a in esc.get("amount") or () if (a.get("chance") or 0) > 0]
        if not counts:
            continue
        t = totals[name_of(esc.get("mob"))]
        t[0] += min(counts)
        t[1] += max(counts)
    return {k: (lo, hi) for k, (lo, hi) in totals.items() if hi > 0}


def build_bosses(maps_raw: bytes, translations_raw: bytes) -> BossBook:
    tr: dict[str, str] = orjson.loads(translations_raw)["data"]
    doc = orjson.loads(maps_raw)["data"]
    del maps_raw
    mobs: dict[str, Any] = doc.get("mobs") or {}

    def name_of(mob_id: str | None) -> str:
        mob = mobs.get(mob_id or "") or {}
        key = mob.get("name") or mob_id or "Unknown"
        return tr.get(key, key)

    # boss name -> map name -> spawn entries
    spawns: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    raid_secs: dict[str, int] = {}
    mob_ids: dict[str, list[str]] = defaultdict(list)
    map_names: dict[str, str] = {}
    for map_id, m in (doc.get("maps") or {}).items():
        map_name = tr.get(m.get("name"), m.get("normalizedName") or "?")
        map_names[m.get("id") or map_id] = map_name
        raid_secs[map_name] = int(m.get("raidDuration") or 0) * 60
        for entry in m.get("bosses") or ():
            boss = name_of(entry.get("mob"))
            spawns[boss][map_name].append(entry)
            if entry.get("mob") not in mob_ids[boss]:
                mob_ids[boss].append(entry["mob"])
    goons = _goon_reports(doc.get("goonReports") or (), map_names)
    del doc

    bosses: dict[str, Boss] = {}
    for boss_name, by_map in spawns.items():
        mob = next((mobs[i] for i in mob_ids[boss_name] if mobs.get(i, {}).get("imagePortraitLink")), None)
        mob = mob or mobs.get(mob_ids[boss_name][0], {})
        health = sum(int(p.get("max") or 0) for p in mob.get("health") or ()) or None
        boss = Boss(
            name=boss_name,
            slug=mob.get("normalizedName") or boss_name.lower(),
            portrait=mob.get("imagePortraitLink"),
            health=health,
        )
        for map_name, entries in by_map.items():
            chances = [float(e.get("spawnChance") or 0) for e in entries]
            zones: dict[str, float] = {}
            for e in entries:
                for z in e.get("spawnLocations") or ():
                    key = z.get("name") or ""
                    label = tr.get(key) or key
                    if " " not in label:  # untranslated ids, e.g. Terminal's "1BD1PortAmbush1"
                        label = _zone_fallback(label)
                    zones[label] = max(zones.get(label, 0), float(z.get("chance") or 0))
            guards: dict[str, list[int]] = {}
            for e in entries:
                for g, (lo, hi) in _escort_counts(e, name_of).items():
                    if g in guards:
                        guards[g] = [min(guards[g][0], lo), max(guards[g][1], hi)]
                    else:
                        guards[g] = [lo, hi]
                    if g != boss_name:
                        boss.aliases.add(g)
            limit = raid_secs.get(map_name) or 0
            times = [int(e.get("spawnTime") or -1) for e in entries]
            timed = [t for t in times if 0 < t < limit]
            boss.maps.append(
                BossMap(
                    map_name=map_name,
                    chance_low=min(chances),
                    chance_high=max(chances),
                    zones=sorted(zones.items(), key=lambda z: -z[1]),
                    escorts=[Escort(g, lo, hi) for g, (lo, hi) in sorted(guards.items())],
                    # Only call it a timed spawn when every entry waits; otherwise it can be there at start.
                    spawn_after=min(timed) if timed and len(timed) == len(times) else None,
                    triggered=any(e.get("spawnTrigger") for e in entries),
                    groups=len(entries),
                )
            )
        boss.maps.sort(key=lambda bm: (-bm.chance_high, bm.map_name))
        bosses[boss_name] = boss

    # Escorts that are bosses in their own right shouldn't redirect elsewhere.
    for boss in bosses.values():
        boss.aliases -= bosses.keys()
    return BossBook(bosses, goon_reports=goons)


def _goon_reports(raw: Any, map_names: dict[str, str]) -> list[GoonReport]:
    reports = []
    for r in raw:
        try:
            seen = datetime.fromtimestamp(int(r.get("timestamp")) / 1000, tz=timezone.utc)
        except (TypeError, ValueError, OverflowError):
            continue
        name = map_names.get(r.get("map") or "")
        if name:
            reports.append(GoonReport(name, seen))
    reports.sort(key=lambda g: g.seen_at, reverse=True)
    return reports
