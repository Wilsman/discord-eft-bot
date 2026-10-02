"""Cultist Circle timer tiers.

Mirrors ``REWARD_TIERS`` in cultist-circle/components/rewards-chart.tsx so the bot and
https://cultistcircle.com always agree.
"""

from __future__ import annotations

from dataclasses import dataclass

SIX_HOUR_THRESHOLD = 400_000
HIGH_TIER_THRESHOLD = 350_001
MAX_SLOTS = 5


@dataclass(frozen=True, slots=True)
class Tier:
    range_label: str
    minimum: int
    hours: str
    short: str
    color: int
    note: str = ""


TIERS: tuple[Tier, ...] = (
    Tier("0 - 10,000", 0, "2 hours", "2h", 0xB43D22),
    Tier("10,001 - 25,000", 10_001, "3 hours", "3h", 0x832E14),
    Tier("25,001 - 50,000", 25_001, "4 hours", "4h", 0x834D20),
    Tier("50,001 - 100,000", 50_001, "5 hours", "5h", 0xD4A946),
    Tier("100,001 - 200,000", 100_001, "8 hours", "8h", 0x35579F),
    Tier("200,001 - 350,000", 200_001, "12 hours", "12h", 0x4E7080),
    Tier(">= 350,001", 350_001, "14 hours", "14h", 0x3B8364),
    Tier(
        ">= 400,000",
        400_000,
        "6 hours or 14 hours",
        "6h / 14h",
        0x4ADE80,
        "25% chance of Quest/Hideout items",
    ),
)


def tier_for(total: int) -> Tier:
    for tier in reversed(TIERS):
        if total >= tier.minimum:
            return tier
    return TIERS[0]


def tier_index(total: int) -> int:
    return TIERS.index(tier_for(total))


def outcome(total: int) -> str:
    """One-line plain English result for a sacrifice total."""
    if total >= SIX_HOUR_THRESHOLD:
        return "6h (25%, quest/hideout items) or 14h (75%, high value)"
    if total >= HIGH_TIER_THRESHOLD:
        return "14h, high value loot"
    tier = tier_for(total)
    return f"{tier.short}, normal loot"
