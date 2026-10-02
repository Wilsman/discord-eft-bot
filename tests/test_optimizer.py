from __future__ import annotations

import itertools
import random
import time

import pytest

from nerdbot.circle.optimizer import Candidate, cheapest, prune
from nerdbot.circle.planner import PlanOptions, build_candidates, plan
from nerdbot.circle.tiers import SIX_HOUR_THRESHOLD, outcome, tier_for


def brute_force(cands, target, slots):
    best = None
    for n in range(1, slots + 1):
        for combo in itertools.combinations_with_replacement(cands, n):
            counts = {c: combo.count(c) for c in set(combo)}
            if any(count > c.cap for c, count in counts.items()):
                continue
            value = sum(c.value for c in combo)
            cost = sum(c.cost for c in combo)
            if value >= target and (best is None or cost < best):
                best = cost
    return best


@pytest.mark.parametrize("seed", range(25))
def test_matches_brute_force(seed):
    rng = random.Random(seed)
    cands = [
        Candidate(str(i), f"item{i}", rng.randint(5_000, 160_000), rng.randint(1_000, 250_000), rng.randint(1, 5))
        for i in range(9)
    ]
    target = rng.choice([100_000, 250_000, 350_001, 400_000])
    expected = brute_force(cands, target, 5)
    combo = cheapest(cands, target, slots=5, step=1)
    if expected is None:
        assert combo is None
    else:
        assert combo is not None and combo.cost == expected and combo.value >= target


def test_bucketing_never_returns_a_combo_below_target():
    rng = random.Random(7)
    cands = [Candidate(str(i), str(i), rng.randint(70_000, 90_000), rng.randint(10_000, 90_000)) for i in range(40)]
    for target in (350_001, 399_999, 400_000):
        combo = cheapest(cands, target)
        assert combo is not None and combo.value >= target and combo.slots <= 5


def test_buy_limits_respected():
    cheap = Candidate("a", "cheap", 100_000, 1_000, cap=2)
    pricey = Candidate("b", "pricey", 100_000, 50_000, cap=5)
    combo = cheapest([cheap, pricey], 400_000)
    counts = {p.candidate.key: p.count for p in combo.picks}
    assert counts == {"a": 2, "b": 2}


def test_prune_keeps_only_useful_items():
    best = Candidate("best", "best", 100_000, 1_000)
    worse = Candidate("worse", "worse", 90_000, 2_000)
    assert prune([best, worse], slots=5) == [best]
    limited = Candidate("ltd", "ltd", 100_000, 1_000, cap=1)
    assert len(prune([limited, worse], slots=5)) == 2


def test_tiers_match_the_site():
    assert tier_for(0).hours == "2 hours"
    assert tier_for(10_000).hours == "2 hours"
    assert tier_for(10_001).hours == "3 hours"
    assert tier_for(350_000).hours == "12 hours"
    assert tier_for(350_001).hours == "14 hours"
    assert tier_for(399_999).hours == "14 hours"
    assert tier_for(400_000).short == "6h / 14h"
    assert outcome(400_000).startswith("6h")


def test_real_catalog_plans_are_valid_and_fast(catalog):
    for options in (PlanOptions("flea"), PlanOptions("trader", trader_level=4), PlanOptions("trader", trader_level=1)):
        started = time.perf_counter()
        combo = plan(catalog, SIX_HOUR_THRESHOLD, options)
        took = time.perf_counter() - started
        assert combo is not None, options
        assert combo.value >= SIX_HOUR_THRESHOLD and combo.slots <= 5
        assert took < 3, f"{options} took {took:.2f}s"


def test_default_rules_exclude_weapons_and_incompatible(catalog):
    pool = build_candidates(catalog, PlanOptions("flea"))
    names = {c.name for c in pool}
    assert "Roubles" not in names and "Pilgrim" not in names
    by_id = catalog.by_id
    assert not any(by_id[c.key].is_weapon for c in pool)
    with_guns = build_candidates(catalog, PlanOptions("trader", include_weapons=True))
    assert any(by_id[c.key].is_weapon for c in with_guns)


def test_pinned_items_reduce_the_problem(catalog):
    moonshine, _ = catalog.index.resolve("moonshine")
    combo = plan(catalog, SIX_HOUR_THRESHOLD, PlanOptions("flea"), pinned=moonshine, pinned_count=2)
    assert combo is not None
    assert combo.value + moonshine.base * 2 >= SIX_HOUR_THRESHOLD
    assert combo.slots <= 3
