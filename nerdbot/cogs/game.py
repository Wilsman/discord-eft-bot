from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from .. import style
from ..tarkov import MODE_LABEL

if TYPE_CHECKING:
    from ..bot import NerdBot

STATUS_WORDS = {0: "OK", 1: "Updating", 2: "Unstable", 3: "Down"}
STATUS_COLORS = {0: style.GOOD, 1: style.INFO, 2: style.WARN, 3: style.BAD}

BOSS_LABELS = {
    "regular": "PvP",
    "pve": "PvE",
    "pvp-season": "PvP Season",
    "arenafighter": "Arena Fighter",
    "spawnChance": "spawn",
}


def _pretty(value: Any) -> str:
    raw = str(value or "Unknown")
    return BOSS_LABELS.get(raw, raw.replace("_", " ").replace("-", " ").title())


def _change_line(change: dict[str, Any]) -> str:
    field = change.get("field")
    boss = _pretty(change.get("boss"))
    old, new = change.get("old_value") or "?", change.get("new_value") or "?"
    if field == "bossAdded":
        return f"**{boss}** added  ·  {new}"
    if field == "bossRemoved":
        return f"**{boss}** removed"
    if field == "spawnChance":
        return f"**{boss}**  {old} → **{new}**"
    return f"**{boss}** {_pretty(field)}  {old} → **{new}**"


class Game(commands.Cog):
    def __init__(self, bot: NerdBot) -> None:
        self.bot = bot

    @app_commands.command(name="status", description="Escape from Tarkov server status")
    async def status(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        assert self.bot.store is not None
        data = (await self.bot.store.fetch_json("status"))["data"]
        general = data.get("generalStatus") or {}
        level = int(general.get("status") or 0)
        services = [s for s in data.get("currentStatuses") or [] if s.get("name") != "Global"]
        worst = max([level, *(int(s.get("status") or 0) for s in services)], default=0)

        headline = "All systems normal" if worst == 0 else f"Some services are {STATUS_WORDS.get(worst, 'having issues').lower()}"
        e = style.embed("Tarkov servers", f"**{headline}**", color=STATUS_COLORS.get(worst, style.WARN))
        if general.get("message"):
            e.description += f"\n{general['message']}"
        rows = [["SERVICE", "STATUS"]] + [
            [s.get("name", "?"), STATUS_WORDS.get(int(s.get("status") or 0), s.get("statusCode", "?"))]
            for s in services
        ]
        e.add_field(name="Services", value=style.table(rows, "ll"), inline=False)
        for msg in (data.get("messages") or [])[:3]:
            content = msg.get("content") or msg.get("message")
            if content:
                e.add_field(name="Notice", value=style.truncate(str(content), 1024), inline=False)

        loaded = [self.bot.store.peek(m) for m in MODE_LABEL]
        fresh = "\n".join(
            f"{MODE_LABEL[c.mode]}  ·  {len(c.items):,} items  ·  checked {style.relative(c.loaded_at)}"
            for c in loaded
            if c
        )
        if fresh:
            e.add_field(name="Bot market data", value=fresh, inline=False)
        await interaction.followup.send(embed=style.footer(e, "tarkov.dev", when=datetime.now(timezone.utc)))

    @app_commands.command(name="bosses", description="Latest boss spawn chance changes")
    @app_commands.checks.cooldown(2, 20)
    async def bosses(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        assert self.bot.session is not None
        url = f"{self.bot.settings.boss_api}/api/changes?limit=100"
        async with self.bot.session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
            resp.raise_for_status()
            data = await resp.json()

        dated = []
        for change in data if isinstance(data, list) else []:
            try:
                ts = int(change.get("timestamp") or 0)
            except (TypeError, ValueError):
                continue
            if ts > 0:
                dated.append((datetime.fromtimestamp(ts / 1000, tz=timezone.utc), change))
        if not dated:
            await interaction.followup.send(embed=style.embed("Boss changes", "No boss changes recorded yet.", color=style.MUTED))
            return

        dated.sort(key=lambda d: d[0], reverse=True)
        latest_day = dated[0][0].date()
        batch = [(dt, c) for dt, c in dated if dt.date() == latest_day]
        today = datetime.now(timezone.utc).date()
        title = "Boss changes today" if latest_day == today else f"Latest boss changes  ·  {latest_day:%d %b}"

        grouped: dict[str, list[str]] = defaultdict(list)
        for _, change in batch:
            key = f"{_pretty(change.get('map'))}  ·  {_pretty(change.get('game_mode'))}"
            grouped[key].append(_change_line(change))

        e = style.embed(title, f"Latest change {style.relative(batch[0][0])}", color=0x9B59B6)
        shown = 0
        for key, lines in list(grouped.items())[:8]:
            e.add_field(name=key, value="\n".join(lines[:6]), inline=False)
            shown += min(6, len(lines))
        extra = f"showing {shown} of {len(batch)}" if len(batch) > shown else f"{len(batch)} change(s)"
        await interaction.followup.send(embed=style.footer(e, "cultistcircle.com boss tracker", extra))


async def setup(bot: NerdBot) -> None:
    await bot.add_cog(Game(bot))
