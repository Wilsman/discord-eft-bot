"""Live Cultist Circle recipes from the cultistcircle.com feedback API.

The API returns every recipe with community votes (worked / didn't work). We cache it for a
few minutes and keep serving the last good copy if a refresh fails.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any

import aiohttp
from rapidfuzz import fuzz, utils

from ..tarkov import Catalog, GameMode, Item

log = logging.getLogger("nerdbot.recipes")

CACHE_SECONDS = 300
# A recipe is "doubtful" when enough people voted and too few said it worked.
MIN_VOTES = 5
DOUBTFUL_RATE = 0.6

_COUNT_FRONT = re.compile(r"^(\d+)\s*[x×]\s+(.+)$", re.IGNORECASE)
_COUNT_BACK = re.compile(r"^(.+?)\s*[x×]\s*(\d+)$", re.IGNORECASE)
_POOL_SIZE = re.compile(r"\bget (\d+) items?\b", re.IGNORECASE)

VOTE_MODE_LABEL = {"pvp": "PvP", "pve": "PvE", "season": "Season"}
RESTRICTION_LABEL = {"pvp-only": "PvP only", "pve-only": "PvE only", "season-only": "Season only"}


@dataclass(frozen=True, slots=True)
class Votes:
    worked: int = 0
    didnt: int = 0
    last_worked: datetime | None = None
    last_worked_mode: str | None = None
    last_failed: datetime | None = None
    last_failed_mode: str | None = None

    @property
    def total(self) -> int:
        return self.worked + self.didnt

    @property
    def rate(self) -> float | None:
        return self.worked / self.total if self.total else None

    @property
    def enough(self) -> bool:
        return self.total >= MIN_VOTES

    @property
    def doubtful(self) -> bool:
        return self.enough and (self.rate or 0) < DOUBTFUL_RATE


@dataclass(frozen=True, slots=True)
class Outcome:
    items: tuple[str, ...]
    explanation: str

    @property
    def pool_size(self) -> int | None:
        """'You always get 2 items' means N random picks from ``items``, not all of them."""
        m = _POOL_SIZE.search(self.explanation)
        return int(m.group(1)) if m else None


@dataclass(frozen=True, slots=True)
class LiveRecipe:
    id: str
    url: str
    inputs: tuple[str, ...]
    time: str
    rewards: tuple[str, ...]
    outcomes: tuple[Outcome, ...]
    restriction: str | None
    is_new: bool
    is_updated: bool
    repeatable: bool
    expired: bool
    expired_at: datetime | None
    votes: Votes

    @property
    def title(self) -> str:
        return " + ".join(self.inputs)

    @property
    def reward_names(self) -> tuple[str, ...]:
        if self.rewards:
            return self.rewards
        return tuple(dict.fromkeys(i for o in self.outcomes for i in o.items))

    @property
    def haystack(self) -> str:
        return " ".join(self.inputs + self.reward_names)

    def allowed_in(self, mode: GameMode) -> bool:
        if self.restriction == "pvp-only":
            return mode != "pve"
        if self.restriction == "pve-only":
            return mode == "pve"
        if self.restriction == "season-only":
            return mode == "pvp-season"
        return True


@dataclass(slots=True)
class RecipeBook:
    active: list[LiveRecipe]
    expired: list[LiveRecipe]
    fetched_at: float = field(default_factory=time.monotonic)

    @property
    def all(self) -> list[LiveRecipe]:
        return self.active + self.expired


# ---------------------------------------------------------------- parsing

def _when(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _strings(value: Any) -> tuple[str, ...]:
    return tuple(s.strip() for s in value if isinstance(s, str) and s.strip()) if isinstance(value, list) else ()


def _recipe(raw: dict[str, Any]) -> LiveRecipe | None:
    inputs = _strings(raw.get("requiredItems"))
    if not inputs:
        return None
    v = raw.get("votes") or {}
    outcomes = tuple(
        Outcome(_strings(o.get("items")), str(o.get("explanation") or "").strip())
        for o in raw.get("outcomes") or []
        if isinstance(o, dict) and _strings(o.get("items"))
    )
    return LiveRecipe(
        id=str(raw.get("id") or ""),
        url=str(raw.get("url") or "https://cultistcircle.com/recipes"),
        inputs=inputs,
        time=str(raw.get("craftingTime") or "?"),
        rewards=_strings(raw.get("rewards")),
        outcomes=outcomes,
        restriction=raw.get("modeRestriction") or None,
        is_new=bool(raw.get("isNew")),
        is_updated=bool(raw.get("isUpdated")),
        repeatable=bool(raw.get("isRepeatable")),
        expired=bool(raw.get("expired")),
        expired_at=_when(raw.get("expiredAt")),
        votes=Votes(
            worked=int(v.get("worked") or 0),
            didnt=int(v.get("didntWork") or 0),
            last_worked=_when(v.get("lastWorkedAt")),
            last_worked_mode=v.get("lastWorkedMode"),
            last_failed=_when(v.get("lastDidntWorkAt")),
            last_failed_mode=v.get("lastDidntWorkMode"),
        ),
    )


def parse_book(data: Any) -> RecipeBook:
    if not isinstance(data, dict) or not isinstance(data.get("recipes"), list):
        raise ValueError("unexpected recipes payload")

    def build(rows: Any, expired: bool) -> list[LiveRecipe]:
        out = []
        for row in rows if isinstance(rows, list) else []:
            if isinstance(row, dict) and (r := _recipe(row)) is not None:
                out.append(r if r.expired == expired else replace(r, expired=expired))
        return out

    return RecipeBook(build(data["recipes"], False), build(data.get("expired"), True))


# ---------------------------------------------------------------- source

class RecipeSource:
    """Fetches the recipe list, caches it, and falls back to the last good copy."""

    def __init__(self, session: aiohttp.ClientSession, base_url: str, ttl: float = CACHE_SECONDS) -> None:
        self.session = session
        self.url = f"{base_url.rstrip('/')}/api/recipes"
        self.ttl = ttl
        self._book: RecipeBook | None = None
        self._lock = asyncio.Lock()

    def peek(self) -> RecipeBook | None:
        return self._book

    async def get(self) -> RecipeBook:
        if self._book and time.monotonic() - self._book.fetched_at < self.ttl:
            return self._book
        async with self._lock:
            if self._book and time.monotonic() - self._book.fetched_at < self.ttl:
                return self._book
            try:
                timeout = aiohttp.ClientTimeout(total=15)
                async with self.session.get(self.url, timeout=timeout) as resp:
                    resp.raise_for_status()
                    self._book = parse_book(await resp.json(content_type=None))
            except Exception:
                if self._book is None:
                    raise
                log.warning("Recipe refresh failed; serving the last good copy", exc_info=True)
                self._book.fetched_at = time.monotonic() - self.ttl + 60  # retry in a minute
        return self._book


# ---------------------------------------------------------------- search

def item_name(entry: str) -> tuple[int, str]:
    """Split '2x Foo' or 'Foo ×2' into (2, 'Foo')."""
    entry = entry.strip()
    if m := _COUNT_FRONT.match(entry):
        return int(m.group(1)), m.group(2).strip()
    if m := _COUNT_BACK.match(entry):
        return int(m.group(2)), m.group(1).strip()
    return 1, entry


def match_score(query: str, text: str) -> float:
    """Every word of the query has to show up (or nearly) in ``text``; the weakest word sets the score."""
    q, hay = utils.default_process(query), utils.default_process(text)
    if not q:
        return 0
    if q in hay:
        return 100
    words = hay.split()
    return min(100 if t in hay else max((fuzz.ratio(t, w) for w in words), default=0) for t in q.split())


def search(book: RecipeBook, query: str, mode: GameMode) -> list[LiveRecipe]:
    """Active recipes first, then expired; best name match (inputs before rewards), then most trusted."""
    scored = []
    for r in book.all:
        if not r.allowed_in(mode):
            continue
        score = match_score(query, r.haystack)
        if score >= 80:
            as_input = match_score(query, " ".join(r.inputs))
            scored.append((r.expired, -score, -as_input, -(r.votes.rate or 0), -r.votes.total, r.title, r))
    scored.sort(key=lambda s: s[:6])
    return [s[-1] for s in scored]


def names(book: RecipeBook) -> list[str]:
    """Every distinct item name across inputs and rewards, for autocomplete."""
    seen = {item_name(n)[1] for r in book.all for n in r.inputs + r.reward_names}
    return sorted(seen, key=str.lower)


# ---------------------------------------------------------------- pricing

@dataclass(frozen=True, slots=True)
class Priced:
    count: int
    text: str
    item: Item | None
    each: int | None

    @property
    def total(self) -> int | None:
        return self.each * self.count if self.each else None


def _match(catalog: Catalog, name: str) -> Item | None:
    """Only trust a catalog hit when its name is close to what the recipe says."""
    item, candidates = catalog.index.resolve(name)
    pool = [item] if item else candidates[:3]
    target = utils.default_process(name)
    for it in pool:
        if fuzz.ratio(target, utils.default_process(it.name)) >= 90:
            return it
    return None


def buy_price(item: Item) -> int | None:
    offer = item.cheapest_buy()
    prices = [p for p in (item.flea_price, offer.price_rub if offer else None) if p]
    return min(prices) if prices else None


def sell_price(item: Item) -> int | None:
    return item.flea_price or (item.sell.price_rub if item.sell else None)


def price_entries(catalog: Catalog, entries: tuple[str, ...], buying: bool) -> list[Priced]:
    out = []
    for entry in entries:
        count, name = item_name(entry)
        parts = [p.strip() for p in name.split(", ")] if ", " in name else [name]
        items = [_match(catalog, p) for p in parts]
        if all(items):
            prices = [(buy_price if buying else sell_price)(it) for it in items]  # type: ignore[arg-type]
            each = sum(prices) if all(prices) else None  # type: ignore[arg-type]
            out.append(Priced(count, name, items[0] if len(items) == 1 else None, each))
        else:
            out.append(Priced(count, name, None, None))
    return out


@dataclass(frozen=True, slots=True)
class Worth:
    low: int
    high: int
    partial: bool  # some items had no price, so the real value is higher


def _sum(priced: list[Priced]) -> Worth | None:
    known = [p.total for p in priced if p.total]
    if not known:
        return None
    total = sum(known)
    return Worth(total, total, len(known) < len(priced))


def outcome_worth(catalog: Catalog, outcome: Outcome) -> Worth | None:
    priced = price_entries(catalog, outcome.items, buying=False)
    if n := outcome.pool_size:
        values = [p.each for p in priced if p.each]
        if not values:
            return None
        return Worth(n * min(values), n * max(values), len(values) < len(priced))
    return _sum(priced)


def reward_worth(catalog: Catalog, recipe: LiveRecipe) -> Worth | None:
    if recipe.rewards:
        return _sum(price_entries(catalog, recipe.rewards, buying=False))
    worths = [w for o in recipe.outcomes if (w := outcome_worth(catalog, o))]
    if not worths:
        return None
    partial = len(worths) < len(recipe.outcomes) or any(w.partial for w in worths)
    return Worth(min(w.low for w in worths), max(w.high for w in worths), partial)
