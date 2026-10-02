"""Find the cheapest set of up to five items whose base value reaches a target.

This is a small bounded knapsack: minimise cost subject to ``sum(value) >= target``
with at most ``slots`` items and at most ``cap`` copies of each item (trader buy
limits). Two things keep it fast on a tiny server:

* Pareto pruning: an item is useless if enough cheaper-or-equal, higher-or-equal value
  copies exist to fill every slot. This cuts ~3,000 candidates to a few dozen.
* Value buckets: partial sums are grouped into ``step``-rouble buckets and every sum at
  or above the target collapses into one "done" bucket. Exact sums are kept, so a
  returned combo always genuinely reaches the target.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

DONE = -1


@dataclass(frozen=True, slots=True)
class Candidate:
    key: str
    name: str
    value: int
    cost: int
    cap: int = 5
    source: str = ""
    link: str | None = None


@dataclass(frozen=True, slots=True)
class Pick:
    candidate: Candidate
    count: int

    @property
    def value(self) -> int:
        return self.candidate.value * self.count

    @property
    def cost(self) -> int:
        return self.candidate.cost * self.count


@dataclass(frozen=True, slots=True)
class Combo:
    picks: tuple[Pick, ...]

    @property
    def value(self) -> int:
        return sum(p.value for p in self.picks)

    @property
    def cost(self) -> int:
        return sum(p.cost for p in self.picks)

    @property
    def slots(self) -> int:
        return sum(p.count for p in self.picks)


def prune(candidates: Iterable[Candidate], slots: int) -> list[Candidate]:
    """Drop candidates that can never appear in an optimal answer."""
    ordered = sorted(
        (c for c in candidates if c.value > 0 and c.cost > 0 and c.cap > 0),
        key=lambda c: (-c.value, c.cost),
    )
    kept: list[Candidate] = []
    for cand in ordered:
        # Everything already kept has value >= cand.value (sorted). If those that are
        # also no more expensive can fill every slot, cand is dominated.
        cover = sum(k.cap for k in kept if k.cost <= cand.cost)
        if cover < slots:
            kept.append(cand)
    return kept


def cheapest(
    candidates: Iterable[Candidate],
    target: int,
    slots: int = 5,
    step: int = 250,
) -> Combo | None:
    if target <= 0:
        return Combo(())
    # Visit the best value-per-rouble items first so a tight cost bound appears early.
    pool = sorted(prune(candidates, slots), key=lambda c: c.cost / c.value)
    if not pool:
        return None

    # layers[n] maps bucket -> (cost, exact value, picks) for combos using n items.
    layers: list[dict[int, tuple[int, int, tuple[tuple[int, int], ...]]]] = [
        {} for _ in range(slots + 1)
    ]
    layers[0][0] = (0, 0, ())
    # Cheapest finished combo so far; anything that already costs more is dead weight.
    bound = float("inf")
    # Largest value still available from candidate i onwards, for reachability checks.
    suffix_max = [0] * (len(pool) + 1)
    for i in range(len(pool) - 1, -1, -1):
        suffix_max[i] = max(pool[i].value, suffix_max[i + 1])

    for ci, cand in enumerate(pool):
        max_copies = min(cand.cap, slots)
        # Pool is sorted by cost/value, so no remaining item fills value more cheaply.
        ratio = cand.cost / cand.value
        reach = suffix_max[ci]
        # Walk item counts downwards so this candidate is used at most once per combo
        # (its multiplicity is chosen explicitly by ``m``).
        for used in range(slots - 1, -1, -1):
            layer = layers[used]
            if not layer:
                continue
            free = slots - used
            for bucket, (cost, value, picks) in list(layer.items()):
                if bucket == DONE:
                    continue
                missing = target - value
                if value + free * reach < target or cost + missing * ratio > bound:
                    continue  # can't finish, or can't finish cheaper than what we have
                for m in range(1, min(max_copies, free) + 1):
                    new_cost = cost + cand.cost * m
                    if new_cost > bound:
                        break  # more copies only cost more
                    new_value = value + cand.value * m
                    key = DONE if new_value >= target else new_value // step
                    dest = layers[used + m]
                    best = dest.get(key)
                    if best is None or _better(new_cost, new_value, best, key):
                        dest[key] = (new_cost, new_value, picks + ((ci, m),))
                        if key == DONE and new_cost < bound:
                            bound = new_cost

    finished = [layer[DONE] for layer in layers if DONE in layer]
    if not finished:
        return None
    cost, value, picks = min(finished, key=lambda s: (s[0], s[1], sum(m for _, m in s[2])))
    ordered = sorted(picks, key=lambda p: (-pool[p[0]].value, pool[p[0]].cost))
    return Combo(tuple(Pick(pool[ci], m) for ci, m in ordered))


def _better(cost: int, value: int, best: tuple[int, int, tuple], key: int) -> bool:
    if cost != best[0]:
        return cost < best[0]
    # Same cost: finished combos prefer less overshoot, partial ones more progress.
    return value < best[1] if key == DONE else value > best[1]
