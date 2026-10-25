from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from .. import style
from ..tarkov import MODE_LABEL, Boss, BossMap, GameMode
from ._common import MODE_CHOICES, mode_of

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


def _map_lines(bm: BossMap, boss: Boss) -> str:
    lines = []
    if not bm.zones:
        lines.append("**Spawns** anywhere on the map")
    else:
        # Zone odds only make sense when there's a single spawn entry to split between.
        show_odds = bm.groups == 1 and len(bm.zones) > 1
        zones = [f"{z} {round(c * 100)}%" if show_odds else z for z, c in bm.zones]
        lines.append("**Spawns** " + ", ".join(zones))
    if bm.escorts:
        guards = [
            f"+{e.count} more" if e.name == boss.name else f"{e.name} ×{e.count}" for e in bm.escorts
        ]
        lines.append("**With** " + ", ".join(guards))
    notes = []
    if bm.spawn_after:
        notes.append(f"spawns ~{round(bm.spawn_after / 60)} min in")
    if bm.triggered:
        notes.append("some spawns are triggered (levers, switches)")
    if bm.groups > 1:
        notes.append(f"{bm.groups} spawn groups")
    if notes:
        lines.append("-# " + "  ·  ".join(notes))
    return style.truncate("\n".join(lines), 1024)


def boss_embed(boss: Boss, mode: GameMode, alias: str | None = None) -> discord.Embed:
    bits = [f"Seen on **{len(boss.maps)}** map{'s' if len(boss.maps) != 1 else ''}"]
    if boss.health:
        bits.append(f"**{boss.health:,}** HP")
    desc = "  ·  ".join(bits)
    if alias:
        desc = f"*{alias}* spawns with {boss.name}.\n" + desc
    e = style.embed(boss.name, desc, color=0x9B59B6, url=boss.url)
    if boss.portrait:
        e.set_thumbnail(url=boss.portrait)
    for bm in boss.maps[:24]:
        e.add_field(name=f"{bm.map_name}  ·  {bm.chance}", value=_map_lines(bm, boss), inline=False)
    # Keep well under the 6000-char embed cap.
    while len(e) > 5800 and e.fields:
        e.remove_field(-1)
    shown = len(e.fields)
    extra = f"{shown} of {len(boss.maps)} maps" if shown < len(boss.maps) else ""
    return style.footer(e, f"tarkov.dev  ·  {MODE_LABEL[mode]}", extra)


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

    @app_commands.command(name="boss", description="Where a boss spawns, how often, and who they bring")
    @app_commands.describe(name="Boss name (pick from the list or type part of it)", mode="Game mode (default PvP)")
    @app_commands.choices(mode=MODE_CHOICES)
    @app_commands.checks.cooldown(3, 15)
    async def boss(
        self,
        interaction: discord.Interaction,
        name: str,
        mode: app_commands.Choice[str] | None = None,
    ) -> None:
        from ..bot import DataUnavailable

        await interaction.response.defer()
        assert self.bot.store is not None
        game_mode: GameMode = (mode.value if mode else "regular")  # type: ignore[assignment]
        try:
            book = await self.bot.store.bosses(game_mode)
        except Exception as exc:
            raise DataUnavailable("Couldn't load boss data from tarkov.dev. Try again in a minute.") from exc
        found, candidates = book.resolve(name)
        alias = None
        if found is None and candidates:
            hits = book.search(name, limit=1)
            if hits and hits[0][1]:  # typed a guard's name, e.g. "Big Pipe"
                found, alias = hits[0]
        if found is None:
            hint = ", ".join(f"**{b.name}**" for b in candidates) or ", ".join(book.names)
            await interaction.followup.send(
                embed=style.error(f"No boss called **{style.truncate(name, 60)}**. Try: {hint}", title="No match")
            )
            return
        await interaction.followup.send(embed=boss_embed(found, game_mode, alias))

    @boss.autocomplete("name")
    async def _boss_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        store = self.bot.store
        if store is None:
            return []
        mode = mode_of(interaction)
        book = store.peek_bosses(mode) or store.peek_bosses("regular")
        if book is None:
            try:  # first use: load it, autocomplete has ~3s to answer
                book = await asyncio.wait_for(asyncio.shield(store.bosses(mode)), timeout=2.5)
            except Exception:
                return []
        return [
            app_commands.Choice(name=f"{b.name} ({alias})" if alias else b.name, value=b.name)
            for b, alias in book.search(current, limit=25)
        ]

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
