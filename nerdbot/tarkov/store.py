from __future__ import annotations

import asyncio
import gc
import logging
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import aiohttp
import orjson

from .calibers import caliber_name
from .models import AmmoStats, GameMode, Item, Offer
from .search import ItemIndex

log = logging.getLogger(__name__)

USER_AGENT = "NerdBot (+https://github.com/Wilsman/discord-eft-bot)"


def _ts(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _int(value: Any) -> int | None:
    return int(value) if isinstance(value, (int, float)) and value > 0 else None


@dataclass(slots=True)
class Catalog:
    mode: GameMode
    items: list[Item]
    by_id: dict[str, Item]
    index: ItemIndex
    flea_enabled: bool
    data_updated: datetime | None
    loaded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    _ammo: dict[str, list[Item]] = field(default_factory=dict)

    def ammo_for(self, caliber: str) -> list[Item]:
        if not self._ammo:
            groups: dict[str, list[Item]] = defaultdict(list)
            for item in self.items:
                if item.ammo:
                    groups[item.ammo.caliber].append(item)
            self._ammo = dict(groups)
        return self._ammo.get(caliber, [])


def build_catalog(
    mode: GameMode, items_raw: bytes, translations_raw: bytes, traders: dict[str, str]
) -> Catalog:
    """Parse the json.tarkov.dev items payload into slim ``Item`` records.

    The raw payload is ~17 MB per mode because of weapon slot trees we never use, so
    we keep only what the bot needs and let the parsed document go immediately.
    """
    tr: dict[str, str] = orjson.loads(translations_raw)["data"]
    doc = orjson.loads(items_raw)["data"]
    del items_raw

    def t(key: str | None) -> str:
        return tr.get(key, key) if key else ""

    category_names = {
        cid: sys.intern(t(cat.get("name"))) for cid, cat in doc.get("itemCategories", {}).items()
    }
    flea_enabled = bool((doc.get("fleaMarket") or {}).get("enabled", True))

    def trader(tid: str) -> str:
        return traders.get(tid, "Trader")

    items: list[Item] = []
    newest: datetime | None = None
    for raw in doc["items"].values():
        sells = [
            Offer(trader(o["trader"]), int(o["priceRUB"]), int(o["price"]), o.get("currency", "RUB"))
            for o in raw.get("sellToTrader") or ()
            if _int(o.get("priceRUB"))
        ]
        buys = tuple(
            Offer(
                trader(o["trader"]),
                int(o["priceRUB"]),
                int(o["price"]),
                o.get("currency", "RUB"),
                o.get("minTraderLevel"),
                o.get("buyLimit"),
                bool(o.get("taskUnlock")),
            )
            for o in raw.get("buyFromTrader") or ()
            if _int(o.get("priceRUB"))
        )
        ammo = None
        props = raw.get("properties") or {}
        if "damage" in raw and props.get("propertiesType") == "ItemPropertiesAmmo":
            ammo = AmmoStats(
                caliber=caliber_name(props.get("caliber")),
                damage=int(props.get("damage") or 0),
                penetration=int(props.get("penetrationPower") or 0),
                armor_damage=int(props.get("armorDamage") or 0),
                fragmentation=float(props.get("fragmentationChance") or 0),
                projectiles=int(props.get("projectileCount") or 1),
                speed=_int(props.get("initialSpeed")),
                tracer=bool(props.get("tracer")),
                ammo_type=str(props.get("ammoType") or "bullet"),
            )
        updated = _ts(raw.get("updated"))
        if updated and (newest is None or updated > newest):
            newest = updated
        items.append(
            Item(
                id=raw["id"],
                name=t(raw.get("name")),
                short=t(raw.get("shortName")),
                normalized=raw.get("normalizedName") or "",
                link=raw.get("link"),
                wiki=raw.get("wikiLink"),
                icon=raw.get("iconLink"),
                image=raw.get("gridImageLink") or raw.get("iconLink"),
                base=int(raw.get("basePrice") or 0),
                width=int(raw.get("width") or 1),
                height=int(raw.get("height") or 1),
                types=frozenset(sys.intern(x) for x in raw.get("types") or ()),
                categories=tuple(category_names.get(c, "") for c in raw.get("categories") or ()),
                flea_low=_int(raw.get("lastLowPrice")),
                avg24=_int(raw.get("avg24hPrice")),
                low24=_int(raw.get("low24hPrice")),
                high24=_int(raw.get("high24hPrice")),
                change48=raw.get("changeLast48hPercent"),
                offers=int(raw.get("lastOfferCount") or 0),
                updated=updated,
                sell=max(sells, key=lambda o: o.price_rub, default=None),
                buys=buys,
                ammo=ammo,
            )
        )
    del doc, tr
    items.sort(key=lambda i: i.name.lower())
    return Catalog(
        mode=mode,
        items=items,
        by_id={i.id: i for i in items},
        index=ItemIndex(items),
        flea_enabled=flea_enabled,
        data_updated=newest,
    )


class TarkovStore:
    """Owns the per-mode catalogs and keeps them fresh with conditional requests."""

    def __init__(self, session: aiohttp.ClientSession, base_url: str) -> None:
        self._session = session
        self._base = base_url.rstrip("/")
        self._catalogs: dict[str, Catalog] = {}
        self._etags: dict[str, str] = {}
        self._blobs: dict[str, bytes] = {}  # small payloads we re-use when items change
        self._traders: dict[str, dict[str, str]] = {}
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    def peek(self, mode: GameMode) -> Catalog | None:
        return self._catalogs.get(mode)

    @property
    def loaded_modes(self) -> list[GameMode]:
        return list(self._catalogs)  # type: ignore[arg-type]

    async def get(self, mode: GameMode) -> Catalog:
        catalog = self._catalogs.get(mode)
        if catalog is not None:
            return catalog
        async with self._locks[mode]:
            if mode not in self._catalogs:
                await self._load(mode, force=True)
        return self._catalogs[mode]

    async def refresh(self, mode: GameMode) -> bool:
        """Re-fetch a loaded mode. Returns True when new data was applied."""
        async with self._locks[mode]:
            return await self._load(mode, force=False)

    async def fetch_json(self, path: str) -> Any:
        """Uncached helper for small endpoints such as ``/status``."""
        body = await self._fetch(path, conditional=False)
        assert body is not None
        return orjson.loads(body)

    async def _fetch(self, path: str, conditional: bool = True) -> bytes | None:
        headers = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"}
        if conditional and path in self._etags:
            headers["If-None-Match"] = self._etags[path]
        timeout = aiohttp.ClientTimeout(total=90, sock_connect=15)
        for attempt in range(1, 4):
            try:
                async with self._session.get(
                    f"{self._base}/{path}", headers=headers, timeout=timeout
                ) as resp:
                    if resp.status == 304:
                        return None
                    resp.raise_for_status()
                    body = await resp.read()
                    if etag := resp.headers.get("ETag"):
                        self._etags[path] = etag
                    return body
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                if attempt == 3:
                    raise
                log.warning("GET %s failed (%s), retrying", path, exc)
                await asyncio.sleep(2**attempt)
        return None

    async def _small(self, path: str) -> bytes:
        body = await self._fetch(path, conditional=path in self._blobs)
        if body is not None:
            self._blobs[path] = body
        return self._blobs[path]

    async def _trader_names(self, mode: GameMode) -> dict[str, str]:
        raw = await self._small(f"{mode}/traders")
        names = orjson.loads(await self._small(f"{mode}/traders_en"))["data"]
        traders = orjson.loads(raw)["data"]
        return {tid: names.get(t["name"], t.get("normalizedName", "").title()) for tid, t in traders.items()}

    async def _load(self, mode: GameMode, force: bool) -> bool:
        path = f"{mode}/items"
        if force:
            self._etags.pop(path, None)
        body = await self._fetch(path)
        if body is None:
            return False
        translations = await self._small(f"{mode}/items_en")
        traders = await self._trader_names(mode)
        self._traders[mode] = traders
        started = datetime.now(timezone.utc)
        catalog = await asyncio.to_thread(build_catalog, mode, body, translations, traders)
        del body
        self._catalogs[mode] = catalog
        gc.collect()
        took = (datetime.now(timezone.utc) - started).total_seconds()
        log.info("Loaded %s catalog: %d items in %.1fs", mode, len(catalog.items), took)
        return True
