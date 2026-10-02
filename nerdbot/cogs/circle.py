from __future__ import annotations

import asyncio
import io
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands
from rapidfuzz import fuzz, utils

from .. import style
from ..circle.card import render_thresholds
from ..circle.knowledge import HOT_SACRIFICES, RECIPES, RECIPES_URL, SITE, HotSacrifice, Recipe
from ..circle.optimizer import Combo
from ..circle.planner import PlanOptions, eligible, plan
from ..circle.tiers import HIGH_TIER_THRESHOLD, MAX_SLOTS, SIX_HOUR_THRESHOLD, outcome, tier_for
from ..tarkov import MODE_LABEL, Catalog, Item
from ..views import Pager, Reply, link_view
from ._common import MODE_CHOICES, catalog_for, followup, item_choices, lookup, reply_for_item

if TYPE_CHECKING:
    from ..bot import NerdBot

TARGET_CHOICES = [
    app_commands.Choice(name="400,000 - 6h or 14h", value=SIX_HOUR_THRESHOLD),
    app_commands.Choice(name="350,001 - 14h", value=HIGH_TIER_THRESHOLD),
]
PRICE_CHOICES = [
    app_commands.Choice(name="Flea market", value="flea"),
    app_commands.Choice(name="Traders only", value="trader"),
]


def thresholds_file(total: int | None = None) -> discord.File:
    return discord.File(io.BytesIO(render_thresholds(total)), filename="thresholds.png")


def thresholds_reply(total: int | None = None) -> Reply:
    if total is None:
        e = style.embed(
            "Cultist Circle thresholds",
            "Total **base value** of up to 5 items sets the timer. "
            "Hit **400,000** for a 25% shot at the 6 hour quest and hideout pool.",
        )
    else:
        e = style.embed(
            f"{total:,} base value",
            f"**{outcome(total)}**\n`{style.bar(total, SIX_HOUR_THRESHOLD)}`",
            color=tier_for(total).color,
        )
    e.set_image(url="attachment://thresholds.png")
    style.footer(e, "cultistcircle.com")
    return {"embed": e, "file": thresholds_file(total), "view": link_view(("Open calculator", SITE))}


def progress_block(total: int, target: int) -> str:
    return f"**{outcome(total)}**\n`{style.bar(total, target)}`  {total:,} / {target:,}"


def combo_lines(combo: Combo, catalog: Catalog) -> str:
    lines = []
    for pick in combo.picks:
        c = pick.candidate
        name = f"[{c.name}]({c.link})" if c.link else c.name
        lines.append(f"**{pick.count}x** {name}\n└ {c.value:,} base  ·  {style.rub(c.cost)} each  ·  {c.source}")
    return "\n".join(lines)


# ---------------------------------------------------------------- combo parsing

_SPLIT = re.compile(r"\s*(?:,|&|\+|\band\b|\n)\s*", re.IGNORECASE)
_QTY = re.compile(r"^(?:(\d+)\s*x?\s+|x\s*(\d+)\s+)?(.+?)(?:\s+x\s*(\d+)|\s+(\d+)x)?$", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class ComboPart:
    count: int
    text: str


def parse_combo(raw: str) -> list[ComboPart]:
    parts = []
    for chunk in filter(None, (p.strip() for p in _SPLIT.split(raw))):
        m = _QTY.match(chunk)
        if not m:
            continue
        count = next((int(g) for g in (m.group(1), m.group(2), m.group(4), m.group(5)) if g), 1)
        name = m.group(3).strip()
        if count > 0 and name:
            parts.append(ComboPart(count, name))
    return parts


# ---------------------------------------------------------------- hot sacrifices

def _ingredient_cost(catalog: Catalog, name: str, vendor: str) -> tuple[Item | None, int | None]:
    item, _ = lookup(catalog, name)
    if item is None:
        return None, None
    if vendor:
        offers = [o for o in item.buys if o.trader == vendor]
        if offers:
            return item, min(o.price_rub for o in offers)
    return item, item.flea_price


def hot_embed(catalog: Catalog) -> discord.Embed:
    e = style.embed(
        "Hot sacrifices",
        "Community-tested weapon combos. Weapons carry special circle values, "
        "so these beat what base value math predicts.",
        color=style.WARN,
    )
    e.set_thumbnail(url="https://assets.tarkov.dev/59411aa786f7747aeb37f9a5-icon.webp")
    for combo in HOT_SACRIFICES:
        e.add_field(**_hot_field(combo, catalog), inline=False)
    return style.footer(e, "cultistcircle.com", f"Est. costs from {MODE_LABEL[catalog.mode]} prices")


def _hot_field(combo: HotSacrifice, catalog: Catalog) -> dict[str, str]:
    title = " + ".join(f"{i.count}x {i.short}" for i in combo.ingredients)
    if combo.barter:
        first, second = combo.ingredients
        title = f"{first.short} into {second.short}"
    if combo.disabled:
        return {
            "name": f"{title}  ·  retired",
            "value": "~~No longer works~~ after a base value change.",
        }
    lines, total, known = [], 0, True
    for idx, ing in enumerate(combo.ingredients):
        if combo.barter and idx == 1:
            lines.append(f"└ barter for **{ing.count}x {ing.short}** at {ing.vendor} {ing.level}")
            continue
        _, cost = _ingredient_cost(catalog, ing.name, ing.vendor)
        where = f"{ing.vendor} {ing.level}" if ing.vendor else "flea"
        price = style.rub(cost) if cost else "n/a"
        lines.append(f"**{ing.count}x** {ing.short}  ·  {where}  ·  {price} each")
        if cost:
            total += cost * ing.count
        else:
            known = False
    est = f"~{style.rub(total)}" if total and known else "n/a"
    prefix = "Featured  ·  " if combo.featured else ""
    return {"name": f"{prefix}{title}  ·  {combo.result}", "value": "\n".join(lines) + f"\nEst. cost **{est}**"}


# ---------------------------------------------------------------- recipes

def recipe_line(r: Recipe) -> tuple[str, str]:
    name = " + ".join(r.inputs)
    flags = [r.time]
    if r.pvp_only:
        flags.append("PvP only")
    if r.repeatable:
        flags.append("repeatable")
    value = "→ " + ", ".join(r.outputs) + "\n└ " + "  ·  ".join(flags)
    if r.note:
        value += f"\n*{r.note}*"
    return style.truncate(name, 256), style.truncate(value, 1024)


def search_recipes(query: str) -> list[Recipe]:
    q = utils.default_process(query)
    scored = []
    for r in RECIPES:
        hay = utils.default_process(" ".join(r.inputs + r.outputs))
        score = 100 if q in hay else fuzz.partial_token_set_ratio(q, hay)
        if score >= 80:
            scored.append((score, r))
    scored.sort(key=lambda s: -s[0])
    return [r for _, r in scored]


def recipe_pages(recipes: list[Recipe], title: str) -> list[discord.Embed]:
    pages = []
    per_page = 8
    for start in range(0, len(recipes), per_page):
        e = style.embed(title, f"Fixed-outcome sacrifices. Full list: {RECIPES_URL}", color=style.ACCENT)
        for r in recipes[start : start + per_page]:
            name, value = recipe_line(r)
            e.add_field(name=name, value=value, inline=False)
        pages.append(style.footer(e, "cultistcircle.com/recipes"))
    return pages


class Circle(commands.Cog):
    circle = app_commands.Group(name="circle", description="Cultist Circle planning tools")

    def __init__(self, bot: NerdBot) -> None:
        self.bot = bot

    # ------------------------------------------------------------ /thresholds

    @app_commands.command(name="thresholds", description="The Cultist Circle value to timer chart")
    @app_commands.describe(total="Optional: your sacrifice's total base value to see where it lands")
    async def thresholds(
        self, interaction: discord.Interaction, total: app_commands.Range[int, 0, 50_000_000] | None = None
    ) -> None:
        await interaction.response.send_message(**thresholds_reply(total))

    @commands.command(name="thresholds", aliases=["threshold", "timers", "tiers"])
    @commands.cooldown(2, 10, commands.BucketType.channel)
    async def thresholds_prefix(self, ctx: commands.Context, total: str | None = None) -> None:
        """!thresholds [total]"""
        value = None
        if total:
            digits = re.sub(r"[^\d.km]", "", total.lower())
            mult = 1_000 if digits.endswith("k") else 1_000_000 if digits.endswith("m") else 1
            try:
                value = int(float(digits.rstrip("km")) * mult)
            except ValueError:
                value = None
        await ctx.reply(mention_author=False, **thresholds_reply(value))

    # ------------------------------------------------------------ /circle cheapest

    @circle.command(name="cheapest", description="Cheapest combo that reaches a circle threshold")
    @app_commands.describe(
        target="Threshold to hit (default 400k)",
        mode="Game mode for prices (default PvP)",
        prices="Buy from the flea or from traders only",
        trader_level="Highest trader loyalty level you have (traders only)",
        weapons="Include weapons (off by default, their circle values are unreliable)",
        own="An item you already have and want to use",
        own_count="How many of that item you have",
    )
    @app_commands.choices(target=TARGET_CHOICES, mode=MODE_CHOICES, prices=PRICE_CHOICES)
    @app_commands.checks.cooldown(2, 15)
    async def cheapest(
        self,
        interaction: discord.Interaction,
        target: app_commands.Choice[int] | None = None,
        mode: app_commands.Choice[str] | None = None,
        prices: app_commands.Choice[str] | None = None,
        trader_level: app_commands.Range[int, 1, 4] = 4,
        weapons: bool = False,
        own: str | None = None,
        own_count: app_commands.Range[int, 1, 5] = 1,
    ) -> None:
        await interaction.response.defer()
        catalog = await catalog_for(self.bot, mode.value if mode else None)
        goal = target.value if target else SIX_HOUR_THRESHOLD
        source = prices.value if prices else ("flea" if catalog.flea_enabled else "trader")
        options = PlanOptions(source, trader_level, weapons)  # type: ignore[arg-type]

        async def render(pinned: Item | None) -> Reply:
            count = own_count if pinned else 0
            combo = await asyncio.to_thread(plan, catalog, goal, options, pinned, count)
            return {"embed": self._cheapest_embed(catalog, goal, options, combo, pinned, count)}

        if own:
            await reply_for_item(followup(interaction), interaction.user.id, catalog, own, render)
        else:
            await interaction.followup.send(**(await render(None)))

    @cheapest.autocomplete("own")
    async def _own_items(self, interaction: discord.Interaction, current: str):
        return await item_choices(interaction, current, where=lambda i: i.base > 0)

    def _cheapest_embed(
        self,
        catalog: Catalog,
        goal: int,
        options: PlanOptions,
        combo: Combo | None,
        pinned: Item | None,
        pinned_count: int,
    ) -> discord.Embed:
        mode = MODE_LABEL[catalog.mode]
        price_label = "flea prices" if options.source == "flea" else f"traders up to LL{options.trader_level}"
        context = f"{mode}  ·  {price_label}  ·  weapons {'included' if options.include_weapons else 'excluded'}"
        title = f"Cheapest {style.compact(goal)} sacrifice"
        if combo is None:
            e = style.embed(
                title,
                f"Couldn't reach **{goal:,}** with {MAX_SLOTS - pinned_count} slot(s) using {price_label}.\n"
                f"{context}\n\nTry flea prices, a higher trader level, or `/circle hot`.",
                color=style.WARN,
            )
            return style.footer(e, "tarkov.dev", mode)

        pinned_value = pinned.base * pinned_count if pinned else 0
        total_value = combo.value + pinned_value
        e = style.embed(title, f"{progress_block(total_value, goal)}\n{context}", color=tier_for(total_value).color)
        if pinned:
            e.add_field(
                name="Already in your stash",
                value=f"**{pinned_count}x** {pinned.display}\n└ {pinned.base:,} base each",
                inline=False,
            )
        if combo.picks:
            e.add_field(name="Buy these" if pinned else "Sacrifice", value=combo_lines(combo, catalog), inline=False)
        else:
            e.add_field(name="Nothing to buy", value="What you have already reaches the target.", inline=False)
        e.add_field(name="Total base", value=f"**{total_value:,}**")
        e.add_field(name="Cost", value=f"**{style.rub(combo.cost)}**")
        e.add_field(name="Slots", value=f"{combo.slots + pinned_count} / {MAX_SLOTS}")
        note = "Skips flea prices with 5 or fewer listings" if options.source == "flea" else "Respects trader buy limits"
        return style.footer(e, "tarkov.dev", note, when=catalog.data_updated)

    # ------------------------------------------------------------ /circle check

    @circle.command(name="check", description="Total up a sacrifice and see which timer it lands on")
    @app_commands.describe(
        combo="Items separated by commas or +, e.g. 2x moonshine + 1 graphics card",
        mode="Game mode for prices (default PvP)",
    )
    @app_commands.choices(mode=MODE_CHOICES)
    async def check(
        self, interaction: discord.Interaction, combo: str, mode: app_commands.Choice[str] | None = None
    ) -> None:
        await interaction.response.defer()
        catalog = await catalog_for(self.bot, mode.value if mode else None)
        await interaction.followup.send(**self._check_reply(catalog, combo))

    def _check_reply(self, catalog: Catalog, raw: str) -> Reply:
        parts = parse_combo(raw)
        if not parts:
            return {"embed": style.error("Try something like `2x moonshine + 1 graphics card`.", "Couldn't read that combo")}
        slots = sum(p.count for p in parts)
        if slots > MAX_SLOTS:
            return {"embed": style.error(f"That's {slots} items. The circle only takes {MAX_SLOTS}.", "Too many items")}

        resolved: list[tuple[int, Item]] = []
        problems: list[str] = []
        for part in parts:
            item, candidates = lookup(catalog, part.text, where=lambda i: i.base > 0)
            if item:
                resolved.append((part.count, item))
            elif candidates:
                options = ", ".join(f"`{c.name}`" for c in candidates[:3])
                problems.append(f"**{part.text}** could be {options}")
            else:
                problems.append(f"**{part.text}** didn't match anything")
        if problems:
            e = style.embed("Which items did you mean?", "\n".join(problems) + "\n\nUse fuller names and run it again.", color=style.WARN)
            return {"embed": e}

        total = sum(count * item.base for count, item in resolved)
        e = style.embed("Sacrifice check", progress_block(total, SIX_HOUR_THRESHOLD), color=tier_for(total).color)
        lines, cost, priced = [], 0, True
        for count, item in resolved:
            lines.append(f"**{count}x** {item.display}\n└ {item.base:,} base each  ·  {count * item.base:,} total")
            if item.is_weapon:
                lines[-1] += "\n└ *weapon: real circle value may differ*"
            if item.flea_price:
                cost += item.flea_price * count
            else:
                priced = False
        e.add_field(name="Items", value="\n".join(lines), inline=False)
        e.add_field(name="Total base", value=f"**{total:,}**")
        e.add_field(name="Flea cost", value=style.rub(cost) if priced else f"{style.rub(cost)}+")
        e.add_field(name="Slots", value=f"{slots} / {MAX_SLOTS}")
        e.set_image(url="attachment://thresholds.png")
        style.footer(e, "tarkov.dev", MODE_LABEL[catalog.mode], when=catalog.data_updated)
        return {"embed": e, "file": thresholds_file(total)}

    # ------------------------------------------------------------ /circle value

    @circle.command(name="value", description="An item's base value and how many it takes to hit each tier")
    @app_commands.describe(item="Start typing an item name", mode="Game mode for prices (default PvP)")
    @app_commands.choices(mode=MODE_CHOICES)
    async def value(
        self, interaction: discord.Interaction, item: str, mode: app_commands.Choice[str] | None = None
    ) -> None:
        await interaction.response.defer()
        catalog = await catalog_for(self.bot, mode.value if mode else None)

        async def render(it: Item) -> Reply:
            return {"embed": self._value_embed(it, catalog)}

        await reply_for_item(followup(interaction), interaction.user.id, catalog, item, render, where=lambda i: i.base > 0)

    @value.autocomplete("item")
    async def _value_items(self, interaction: discord.Interaction, current: str):
        return await item_choices(interaction, current, where=lambda i: i.base > 0)

    def _value_embed(self, item: Item, catalog: Catalog) -> discord.Embed:
        e = style.embed(item.name, f"Base value **{item.base:,}**", url=item.link, color=style.ACCENT)
        if item.image:
            e.set_thumbnail(url=item.image)
        rows = [["", "TOTAL", "TIMER"]]
        for n in range(1, MAX_SLOTS + 1):
            total = item.base * n
            rows.append([f"{n}x", f"{total:,}", tier_for(total).short])
        e.add_field(name="Copies", value=style.table(rows, "lrl"), inline=False)
        flea = item.flea_price
        offer = item.cheapest_buy()
        e.add_field(name="Flea", value=style.rub(flea) if flea else "Not on flea")
        e.add_field(name="Trader", value=f"{style.rub(offer.price_rub)}\n{offer.label}" if offer else "Not sold")
        best = min(p for p in (flea, offer.price_rub if offer else None) if p) if (flea or offer) else None
        e.add_field(name="Base per rouble", value=f"{item.base / best:.2f}" if best else "n/a")
        notes = []
        if item.is_weapon:
            notes.append("Weapons have special circle values; durability and attachments change the result.")
        if not eligible(item, PlanOptions(include_weapons=True)):
            notes.append("Auto-select skips this category by default on the site.")
        if notes:
            e.add_field(name="Heads up", value="\n".join(notes), inline=False)
        return style.footer(e, "tarkov.dev", MODE_LABEL[catalog.mode], when=item.updated)

    # ------------------------------------------------------------ /circle hot

    @circle.command(name="hot", description="Community-tested cheap combos, with live cost estimates")
    @app_commands.describe(mode="Game mode for prices (default PvP)")
    @app_commands.choices(mode=MODE_CHOICES)
    async def hot(self, interaction: discord.Interaction, mode: app_commands.Choice[str] | None = None) -> None:
        await interaction.response.defer()
        catalog = await catalog_for(self.bot, mode.value if mode else None)
        await interaction.followup.send(embed=hot_embed(catalog), view=link_view(("Open calculator", SITE)))

    @commands.command(name="hot", aliases=["hotsacrifices", "combos"])
    @commands.cooldown(2, 10, commands.BucketType.channel)
    async def hot_prefix(self, ctx: commands.Context, mode: str = "pvp") -> None:
        """!hot [pve]"""
        catalog = await catalog_for(self.bot, "pve" if mode.lower() == "pve" else "regular")
        await ctx.reply(embed=hot_embed(catalog), view=link_view(("Open calculator", SITE)), mention_author=False)

    # ------------------------------------------------------------ /circle recipes

    @circle.command(name="recipes", description="Fixed-outcome recipes, like figurines and keys")
    @app_commands.describe(search="Optional: an item to look for in inputs or rewards")
    async def recipes(self, interaction: discord.Interaction, search: str | None = None) -> None:
        found = search_recipes(search) if search else list(RECIPES)
        if not found:
            await interaction.response.send_message(
                embed=style.error(f"No recipe uses or gives **{style.truncate(search or '', 80)}**.", "No recipes found"),
                ephemeral=True,
            )
            return
        title = f"Recipes matching \"{style.truncate(search, 60)}\"" if search else "Cultist Circle recipes"
        pages = recipe_pages(found, title)
        if len(pages) == 1:
            await interaction.response.send_message(embed=pages[0])
            return
        view = Pager(pages, interaction.user.id)
        await interaction.response.send_message(embed=pages[0], view=view)
        view.message = await interaction.original_response()

    @recipes.autocomplete("search")
    async def _recipe_search(self, interaction: discord.Interaction, current: str):
        names = sorted({n.split("x ", 1)[-1] if re.match(r"^\d+x ", n) else n for r in RECIPES for n in r.inputs})
        if current:
            names = [n for n in names if current.lower() in n.lower()] or names
        return [app_commands.Choice(name=style.truncate(n, 100), value=style.truncate(n, 100)) for n in names[:25]]


async def setup(bot: NerdBot) -> None:
    await bot.add_cog(Circle(bot))
