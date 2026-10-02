"""Turn catalog items into optimizer candidates using the site's default rules."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from ..tarkov import Catalog, Item
from .knowledge import DEFAULT_EXCLUDED_CATEGORIES, INCOMPATIBLE_ITEMS
from .optimizer import Candidate, Combo, cheapest
from .tiers import MAX_SLOTS

PriceSource = Literal["flea", "trader"]


@dataclass(frozen=True, slots=True)
class PlanOptions:
    source: PriceSource = "flea"
    trader_level: int = 4
    include_weapons: bool = False


def eligible(item: Item, options: PlanOptions) -> bool:
    if item.base <= 0 or item.name in INCOMPATIBLE_ITEMS:
        return False
    blocked = DEFAULT_EXCLUDED_CATEGORIES - ({"Weapon"} if options.include_weapons else set())
    if blocked.intersection(item.categories):
        return False
    if item.is_weapon and not options.include_weapons:
        return False
    return True


def candidate_for(item: Item, options: PlanOptions) -> Candidate | None:
    if options.source == "trader":
        offer = item.cheapest_buy(options.trader_level)
        if offer is None:
            return None
        cap = offer.buy_limit if offer.buy_limit and offer.buy_limit > 0 else MAX_SLOTS
        return Candidate(item.id, item.name, item.base, offer.price_rub, min(cap, MAX_SLOTS), offer.label, item.link)
    if item.unstable:
        return None
    price = item.flea_price
    if not price:
        return None
    return Candidate(item.id, item.name, item.base, price, MAX_SLOTS, "Flea", item.link)


def build_candidates(catalog: Catalog, options: PlanOptions, exclude: Iterable[str] = ()) -> list[Candidate]:
    skip = set(exclude)
    out = []
    for item in catalog.items:
        if item.id in skip or not eligible(item, options):
            continue
        cand = candidate_for(item, options)
        if cand is not None:
            out.append(cand)
    return out


def plan(
    catalog: Catalog,
    target: int,
    options: PlanOptions,
    pinned: Item | None = None,
    pinned_count: int = 0,
) -> Combo | None:
    """Cheapest combo reaching ``target`` around an optional set of owned items."""
    slots = MAX_SLOTS - pinned_count
    remaining = target - (pinned.base * pinned_count if pinned else 0)
    if remaining <= 0:
        return Combo(())
    if slots <= 0:
        return None
    pool = build_candidates(catalog, options, exclude=[pinned.id] if pinned else ())
    return cheapest(pool, remaining, slots=slots)
