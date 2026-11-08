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
from ..tarkov import MODE_LABEL, Boss, BossMap, GameMode, GoonReport, Restock
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

BOSS_MODE_CHOICES = [*MODE_CHOICES, app_commands.Choice(name="All modes", value="all")]


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


def boss_embed_all(per_mode: dict[GameMode, Boss], alias: str | None = None) -> discord.Embed:
    """One embed covering every loaded mode; modes with identical spawn data share a field."""
    first = next(iter(per_mode.values()))
    # map name -> [(modes, chance sort key, BossMap)], merging modes whose output is identical
    by_map: dict[str, list[tuple[list[GameMode], BossMap]]] = {}
    for mode, boss in per_mode.items():
        for bm in boss.maps:
            groups = by_map.setdefault(bm.map_name, [])
            body = _map_lines(bm, boss)
            for modes, other in groups:
                if other.chance == bm.chance and _map_lines(other, per_mode[modes[0]]) == body:
                    modes.append(mode)
                    break
            else:
                groups.append(([mode], bm))

    all_modes = list(per_mode)
    ordered = sorted(
        ((name, g) for name, g in by_map.items()),
        key=lambda kv: (-max(bm.chance_high for _, bm in kv[1]), kv[0]),
    )
    bits = [f"Seen on **{len(by_map)}** map{'s' if len(by_map) != 1 else ''}"]
    if first.health:
        bits.append(f"**{first.health:,}** HP")
    desc = "  ·  ".join(bits)
    if alias:
        desc = f"*{alias}* spawns with {first.name}.\n" + desc
    e = style.embed(first.name, desc, color=0x9B59B6, url=first.url)
    if first.portrait:
        e.set_thumbnail(url=first.portrait)
    fields = 0
    for map_name, groups in ordered:
        for modes, bm in groups:
            if fields >= 24:
                break
            label = f"{map_name}  ·  {bm.chance}"
            if len(groups) > 1 or modes != all_modes:
                label = f"{map_name}  ·  {' / '.join(MODE_LABEL[m] for m in modes)}  ·  {bm.chance}"
            e.add_field(name=label, value=_map_lines(bm, per_mode[modes[0]]), inline=False)
            fields += 1
    while len(e) > 5800 and e.fields:
        e.remove_field(-1)
    total = sum(len(g) for _, g in ordered)
    extra = f"{len(e.fields)} of {total} entries" if len(e.fields) < total else ""
    return style.footer(e, "tarkov.dev  ·  All modes", extra)


def restocks_embed(restocks: list[Restock], mode: GameMode, now: datetime | None = None) -> discord.Embed:
    now = now or datetime.now(timezone.utc)
    lines = []
    for r in restocks:
        if r.at is None:
            when = "unknown"
        elif r.at <= now:
            when = "restocking now"
        else:
            stamp = int(r.at.timestamp())
            when = f"<t:{stamp}:R>  ·  <t:{stamp}:t>"
        lines.append(f"**{r.name}**  {when}")
    desc = "\n".join(lines) or "No trader data right now."
    e = style.embed("Trader restocks", desc, color=style.INFO, url="https://tarkov.dev/traders")
    return style.footer(e, "tarkov.dev", MODE_LABEL[mode], "times in your timezone")


def goons_embed(reports: list[GoonReport], knight: Boss | None, mode: GameMode, now: datetime | None = None) -> discord.Embed:
    now = now or datetime.now(timezone.utc)
    if reports:
        latest = reports[0]
        desc = f"Last reported on **{latest.map_name}** {style.relative(latest.seen_at)}"
        if (now - latest.seen_at).total_seconds() > 24 * 3600:
            desc += "\n-# No reports in the last day, so this may be out of date."
    else:
        desc = f"No recent sightings reported for {MODE_LABEL[mode]}."
    e = style.embed("Goons tracker", desc, color=0x9B59B6, url="https://tarkov.dev/boss/knight")
    if knight and knight.portrait:
        e.set_thumbnail(url=knight.portrait)
    if len(reports) > 1:
        recent = "\n".join(f"{r.map_name}  ·  {style.relative(r.seen_at)}" for r in reports[:8])
        e.add_field(name="Recent reports", value=recent, inline=False)
    if knight and knight.maps:
        chances = "\n".join(f"{bm.map_name}  ·  {bm.chance}" for bm in knight.maps)
        e.add_field(name="Spawn chance", value=style.truncate(chances, 1024), inline=False)
    return style.footer(e, "tarkov.dev player reports", MODE_LABEL[mode])


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
    @app_commands.describe(name="Boss name (pick from the list or type part of it)", mode="Game mode, or all modes combined")
    @app_commands.choices(mode=BOSS_MODE_CHOICES)
    @app_commands.checks.cooldown(3, 15)
    async def boss(
        self,
        interaction: discord.Interaction,
        name: str,
        mode: app_commands.Choice[str],
    ) -> None:
        from ..bot import DataUnavailable

        await interaction.response.defer()
        assert self.bot.store is not None
        single = mode.value in MODE_LABEL
        modes: list[GameMode] = [mode.value] if single else list(MODE_LABEL)  # type: ignore[list-item]
        store = self.bot.store
        results = await asyncio.gather(*(store.bosses(m) for m in modes), return_exceptions=True)
        books = {m: r for m, r in zip(modes, results) if not isinstance(r, BaseException)}
        if not books:
            raise DataUnavailable("Couldn't load boss data from tarkov.dev. Try again in a minute.") from results[0]  # type: ignore[arg-type]

        found, alias, candidates, book = None, None, [], next(iter(books.values()))
        for book in books.values():
            found, candidates = book.resolve(name)
            if found is None and candidates:
                hits = book.search(name, limit=1)
                if hits and hits[0][1]:  # typed a guard's name, e.g. "Big Pipe"
                    found, alias = hits[0]
            if found is not None:
                break
        if found is None:
            book = next(iter(books.values()))
            hint = ", ".join(f"**{b.name}**" for b in candidates) or ", ".join(book.names)
            await interaction.followup.send(
                embed=style.error(f"No boss called **{style.truncate(name, 60)}**. Try: {hint}", title="No match")
            )
            return
        if single:
            await interaction.followup.send(embed=boss_embed(found, modes[0], alias))
            return
        per_mode = {m: b.bosses[found.name] for m, b in books.items() if found.name in b.bosses}
        await interaction.followup.send(embed=boss_embed_all(per_mode, alias))

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

    @app_commands.command(name="traders", description="When each trader restocks next")
    @app_commands.describe(mode="Game mode (default PvP)")
    @app_commands.choices(mode=MODE_CHOICES)
    @app_commands.checks.cooldown(3, 15)
    async def traders(self, interaction: discord.Interaction, mode: app_commands.Choice[str] | None = None) -> None:
        from ..bot import DataUnavailable

        await interaction.response.defer()
        assert self.bot.store is not None
        game_mode: GameMode = mode.value if mode else "regular"  # type: ignore[assignment]
        try:
            restocks = await self.bot.store.restocks(game_mode)
        except Exception as exc:
            raise DataUnavailable("Couldn't load trader data from tarkov.dev. Try again in a minute.") from exc
        await interaction.followup.send(embed=restocks_embed(restocks, game_mode))

    @app_commands.command(name="goons", description="Where the Goons were last reported, plus their spawn chances")
    @app_commands.describe(mode="Game mode (default PvP)")
    @app_commands.choices(mode=MODE_CHOICES)
    @app_commands.checks.cooldown(3, 15)
    async def goons(self, interaction: discord.Interaction, mode: app_commands.Choice[str] | None = None) -> None:
        from ..bot import DataUnavailable

        await interaction.response.defer()
        assert self.bot.store is not None
        game_mode: GameMode = mode.value if mode else "regular"  # type: ignore[assignment]
        try:
            # Reports come in all the time, so re-check sooner than /boss does.
            book = await self.bot.store.bosses(game_mode, max_age_minutes=5)
        except Exception as exc:
            raise DataUnavailable("Couldn't load Goons data from tarkov.dev. Try again in a minute.") from exc
        await interaction.followup.send(embed=goons_embed(book.goon_reports, book.bosses.get("Knight"), game_mode))

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
