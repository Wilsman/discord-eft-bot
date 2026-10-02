from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

GameMode = Literal["regular", "pve", "pvp-season"]

MODES: tuple[GameMode, ...] = ("regular", "pve", "pvp-season")
MODE_LABEL: dict[str, str] = {"regular": "PvP", "pve": "PvE", "pvp-season": "PvP Season"}

# Below this many live listings the site flags a flea price as unstable (red).
UNSTABLE_OFFERS = 5


@dataclass(frozen=True, slots=True)
class Offer:
    trader: str
    price_rub: int
    price: int
    currency: str
    min_level: int | None = None
    buy_limit: int | None = None
    quest_locked: bool = False

    @property
    def label(self) -> str:
        return f"{self.trader} LL{self.min_level}" if self.min_level else self.trader


@dataclass(frozen=True, slots=True)
class AmmoStats:
    caliber: str
    damage: int
    penetration: int
    armor_damage: int
    fragmentation: float
    projectiles: int
    speed: int | None
    tracer: bool
    ammo_type: str

    @property
    def total_damage(self) -> int:
        return self.damage * max(1, self.projectiles)


@dataclass(slots=True)
class Item:
    id: str
    name: str
    short: str
    normalized: str
    link: str | None
    wiki: str | None
    icon: str | None
    image: str | None
    base: int
    width: int
    height: int
    types: frozenset[str]
    categories: tuple[str, ...]
    flea_low: int | None
    avg24: int | None
    low24: int | None
    high24: int | None
    change48: float | None
    offers: int
    updated: datetime | None
    sell: Offer | None
    buys: tuple[Offer, ...] = field(default_factory=tuple)
    ammo: AmmoStats | None = None

    @property
    def slots(self) -> int:
        return max(1, self.width) * max(1, self.height)

    @property
    def on_flea(self) -> bool:
        return "noFlea" not in self.types and bool(self.flea_low)

    @property
    def unstable(self) -> bool:
        return self.on_flea and self.offers <= UNSTABLE_OFFERS

    @property
    def is_weapon(self) -> bool:
        return "gun" in self.types or "preset" in self.types or "Weapon" in self.categories

    @property
    def flea_price(self) -> int | None:
        """Price used when buying from the flea: last low, falling back to the 24h average."""
        if "noFlea" in self.types:
            return None
        return self.flea_low or self.avg24 or None

    def cheapest_buy(self, max_level: int = 4, allow_quest_locked: bool = True) -> Offer | None:
        offers = [
            o
            for o in self.buys
            if (o.min_level or 1) <= max_level and (allow_quest_locked or not o.quest_locked)
        ]
        return min(offers, key=lambda o: o.price_rub, default=None)

    @property
    def display(self) -> str:
        return f"[{self.name}]({self.link})" if self.link else self.name
