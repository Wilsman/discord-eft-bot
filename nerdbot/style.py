"""Shared look and feel: palette, number formatting and embed scaffolding."""

from __future__ import annotations

from datetime import datetime

import discord

# Palette follows cultistcircle.com: amber accent on charcoal, tier greens for wins.
ACCENT = 0xEAB308
GOOD = 0x4ADE80
HIGH = 0x3B8364
WARN = 0xF59E0B
BAD = 0xEF4444
INFO = 0x60A5FA
MUTED = 0x2B2D31

RUB = "₽"


def rub(value: int | float | None) -> str:
    if not value:
        return "n/a"
    return f"{round(value):,}{RUB}"


def compact(value: int | float | None) -> str:
    if not value:
        return "n/a"
    v = float(value)
    for div, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "k")):
        if abs(v) >= div:
            text = f"{v / div:.2f}".rstrip("0").rstrip(".")
            return f"{text}{suffix}"
    return f"{round(v):,}"


def pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    sign = "+" if value > 0 else "-" if value < 0 else ""
    return f"{sign}{abs(value):.1f}%"


def relative(dt: datetime | None) -> str:
    return f"<t:{int(dt.timestamp())}:R>" if dt else "unknown"


def bar(value: int, target: int, width: int = 20) -> str:
    """Progress bar made of block characters, e.g. ``██████████░░░░``."""
    if target <= 0:
        return "█" * width
    filled = max(0, min(width, round(width * value / target)))
    return "█" * filled + "░" * (width - filled)


def truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def embed(
    title: str | None = None,
    description: str | None = None,
    *,
    color: int = ACCENT,
    url: str | None = None,
) -> discord.Embed:
    return discord.Embed(
        title=truncate(title, 256) if title else None,
        description=truncate(description, 4096) if description else None,
        color=color,
        url=url,
    )


def footer(e: discord.Embed, *parts: str, when: datetime | None = None) -> discord.Embed:
    e.set_footer(text="  ·  ".join(p for p in parts if p))
    if when is not None:
        e.timestamp = when
    return e


def error(message: str, title: str = "Hmm, that didn't work") -> discord.Embed:
    return embed(title, message, color=BAD)


def table(rows: list[list[str]], align: str) -> str:
    """Monospace table inside a code block. ``align`` is a string of 'l'/'r' per column."""
    widths = [max(len(r[i]) for r in rows) for i in range(len(align))]
    lines = []
    for row in rows:
        cells = [
            cell.ljust(widths[i]) if align[i] == "l" else cell.rjust(widths[i])
            for i, cell in enumerate(row)
        ]
        lines.append("  ".join(cells).rstrip())
    return "```\n" + "\n".join(lines) + "\n```"
