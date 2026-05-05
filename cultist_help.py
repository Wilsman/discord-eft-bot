from __future__ import annotations

import datetime
from typing import Callable

import discord


def get_cultist_help_response(question: str) -> str:
    """Return a short, canned explanation to a Cultist Circle help question.

    Covers thresholds, base-value math, item combos, pricing modes, and features.

    Args:
        question: Raw user query.

    Returns:
        A single-paragraph response suitable for an embed description.
    """
    q = question.lower().strip()

    def in_q(*terms: str) -> bool:
        return any(t in q for t in terms)

    # Thresholds and durations
    if in_q("6h", "6 h", "6-hour", "six hour"):
        return (
            "6h (quest/hideout items) requires ≥400k base value. At ≥400k: 25% 6h, 75% 14h (high tier loot). "
            "Going over 400k doesn't increase the chance."
        )
    elif in_q("14h", "14 h", "better loot"):
        return (
            "≥350k gives 14h (high tier loot). "
            "At ≥400k: 75% 14h, 25% 6h (quest/hideout items)."
        )
    elif in_q("12h", "12 h", "default"):
        return "12h (normal loot) is the default. <350k is 12h; 350–399k is 14h."

    # Threshold summary - return formatted table
    elif in_q("threshold", "thresholds", "explain thresholds"):
        return get_thresholds_table()

    # Base value calculation
    elif in_q("base value", "multiplier", "vendor"):
        return (
            "Base value = vendor sell price ÷ vendor trading multiplier (avoid Fence). "
            "Example: 126,000 ÷ 0.63 = 200,000."
        )

    # Examples
    elif in_q("moonshine"):
        return "Moonshine base value: 126,000 ÷ 0.63 = 200,000. Two bottles reach 400k (6h/14h pool)."
    elif in_q("vase", "antique"):
        return (
            "Antique Vase: 33,222 ÷ 0.49 ≈ 67,800. Five = ~339k (12h). "
            "1 Moonshine + 3 Vases ≈ 403.4k (6h/14h pool)."
        )

    # Item count rule
    elif in_q("how many", "how much", "items", "slots"):
        return (
            "You can place 1–5 items in the circle. Any mix is fine as long as total "
            "base value hits your target threshold."
        )

    # Weapon-specific behavior and example combos
    elif in_q("weapon", "weapons", "gun"):
        if in_q("investigating") or ("higher" in q and "base" in q):
            return (
                "We're investigating why some weapons return higher base values in the circle; "
                "weapon-specific values may apply."
            )
        else:
            return (
                "Weapons have special circle values; vendor-base math may not apply. "
                "Durability can affect value, so totals can differ."
            )
    elif in_q("durability"):
        return "Item durability can influence effective circle value, especially for weapons."
    elif in_q("mp5sd", "slim diary"):
        return (
            "Reported combo: 2× MP5SD (~$900 total from Peacekeeper) + 1× Slim Diary (~40–50k₽) "
            "can reach the 400k threshold due to weapon-specific values."
        )
    elif in_q("flash drive"):
        return (
            "Flash Drive may be a cheaper alternative to Slim Diary depending on market; "
            "try 2× MP5SD + Diary/Flash Drive."
        )
    elif in_q("5x mp5", "5 x mp5", "five mp5", "mp5"):
        return (
            "Reported combo: 5× MP5 (Peacekeeper L1) can trigger 6/14h due to special weapon circle values."
        )
    elif in_q("g28", "labs access", "labs card"):
        return (
            "Reported combo: 1× G28 Patrol Rifle via barter (1 Labs Access Card, ~166k from Therapist) "
            "can trigger 6/14h due to special weapon values."
        )

    # Features from Instructions
    elif in_q("auto select", "autoselect"):
        return "Auto Select finds the most cost-effective combo to hit your target (e.g., ≥400k) automatically."
    elif in_q("pin"):
        return "Pin locks chosen items so Auto Select must include them in the final combination."
    elif in_q("override"):
        return "Override lets you set custom flea prices when market differs from API data."
    elif in_q("share"):
        return "Share creates a compact code to save or send your selection to others."
    elif in_q("red price", "unstable"):
        return "Red price text = unstable flea price (low offer count at capture)."
    elif in_q("yellow price", "manual"):
        return "Yellow price text = price manually overridden by you."
    elif in_q("exclude", "categories"):
        return "Exclude categories you don't want to sacrifice to narrow results."
    elif in_q("sort"):
        return "Sort items by most recently updated or best value for rubles."

    # PVP flea status and trader pricing
    elif ("pvp" in q and "flea" in q) or in_q("flea disabled", "flea off"):
        return (
            "PVP: Flea is disabled. Use Settings → Price Mode: Trader, then set Trader Levels "
            "to calculate trader-only prices."
        )
    elif in_q("trader price", "price mode", "trader levels"):
        return (
            "Switch Price Mode to Trader in Settings, then pick your Trader Levels (LL1–LL4) "
            "to use trader-only prices."
        )
    elif in_q("hardcore", "l1 traders", "ll1") or ("level 1" in q and "trader" in q):
        return (
            "Hardcore PVP tip (LL1): 5× MP5 from Peacekeeper ≈ 400k+. Cost: $478 (~63,547₽) × 5 = $2,390 (~317,735₽)."
        )
    elif in_q("limitation", "wip", "work in progress", "quest locked"):
        return "Trader pricing is work-in-progress: quest-locked items are currently included."
    elif in_q("mode", "pve", "pvp"):
        return "Toggle PVE/PVP to match the correct flea market for pricing/search."
    elif in_q("tips", "strategy", "optimal"):
        return (
            "Aim slightly over 400k, use Auto Select, pin items you own, and ensure relevant quests are active for quest rewards."
        )
    elif in_q("discord", "discord server", "discord community"):
        return (
            "Join our Discord server for support, updates, and community discussion. https://discord.com/invite/3dFmr5qaJK"
        )

    # Calculator usage
    elif in_q("calculator", "how to use", "use it", "help"):
        return (
            "Pick up to 5 items and check total base value: ≥350k for 14h (high tier); ≥400k for 25% 6h (quest/hideout) / 75% 14h (high tier). "
            "Base value uses vendor price ÷ multiplier."
        )

    # Default
    return (
        "Ask about thresholds (350k/400k), 6h/12h/14h chances, base value math (vendor ÷ trader multiplier), "
        "PVE/PVP flea, item combos, Auto Select/Pin/Override/Share/Refresh, price indicators, excluding categories, sorting, tips, or Discord."
    )


def _pick_color(question: str) -> int:
    """Pick an embed color based on the question topic cluster."""
    q = question.lower()
    if any(k in q for k in ("6h", "6-hour", "14h", "12h")):
        return 0x9b59b6  # purple
    if any(k in q for k in ("base value", "multiplier", "vendor")):
        return 0x3498db  # blue
    if any(k in q for k in ("weapon", "mp5", "g28")):
        return 0xe67e22  # orange
    return 0x2ecc71  # green default


def get_thresholds_table() -> str:
    """Return a formatted markdown table showing cultist circle thresholds."""
    return (
        "```\n"
        "┌───────────────────┬──────────┬───────────────────────────────────────┐\n"
        "│ Range (Value)     │ Time     │ Results                               │\n"
        "├───────────────────┼──────────┼───────────────────────────────────────┤\n"
        "│ 0 - 10,000        │ 2 hours  │ Normal value item                     │\n"
        "│ 10,001 - 25,000   │ 3 hours  │ Normal value item                     │\n"
        "│ 25,001 - 50,000   │ 4 hours  │ Normal value item                     │\n"
        "│ 50,001 - 100,000  │ 5 hours  │ Normal value item                     │\n"
        "│ 100,001 - 200,000 │ 8 hours  │ Normal value item                     │\n"
        "│ 200,001 - 349,999 │ 12 hours │ Normal value item (guaranteed)        │\n"
        "│ 350,000 - 399,999 │ 14 hours │ High tier item                        │\n"
        "│ ≥ 400,000         │ 14h / 6h │ High tier (75%) / Quest-Hideout (25%) │\n"
        "└───────────────────┴──────────┴───────────────────────────────────────┘\n"
        "```"
    )


def build_cultist_help_embed(question: str) -> discord.Embed:
    """Return a rich Discord embed answering the user's help question.

    Includes the original question and a loot tier legend for clarity.
    """
    answer = get_cultist_help_response(question)
    color = _pick_color(question)

    embed = discord.Embed(
        title="🕯️ Cultist Circle Help",
        description=answer,
        color=color,
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    embed.add_field(name="Question", value=f"“{question}”", inline=False)
    embed.add_field(
        name="Loot tiers",
        value="- 12h — normal loot\n- 14h — high tier loot\n- 6h — quest/hideout items",
        inline=False,
    )
    embed.set_footer(text="Cultist Calculator • Help")
    return embed
