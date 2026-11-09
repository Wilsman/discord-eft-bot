from __future__ import annotations

import asyncio
import io
import logging
from collections.abc import Awaitable, Callable, Sequence
from typing import TYPE_CHECKING

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from .. import style
from ..circle.knowledge import RECIPES_URL
from ..circle.recipes import (
    RESTRICTION_LABEL,
    VOTE_MODE_LABEL,
    LiveRecipe,
    Priced,
    RecipeBook,
    RecipeSource,
    names,
    price_entries,
    reward_worth,
    search,
)
from ..circle.recipe_art import Tile, load_icons, render_recipe
from ..tarkov import MODE_LABEL, MODES, Catalog, GameMode
from ..views import OwnedView, Reply, edit_kwargs
from ._common import MODE_CHOICES, catalog_for, split_mode

if TYPE_CHECKING:
    from ..bot import NerdBot

log = logging.getLogger("nerdbot.recipes")

PER_PAGE = 8


# ---------------------------------------------------------------- rendering

def _money_range(lo: int, hi: int, plus: bool = False) -> str:
    text = f"**{style.rub(lo)}**" if lo == hi else f"**{style.rub(lo)}** to **{style.rub(hi)}**"
    return text + ("+" if plus else "")


def _signed(value: int) -> str:
    return f"+{style.rub(value)}" if value > 0 else f"-{style.rub(-value)}" if value < 0 else "0" + style.RUB


def _priced_line(p: Priced) -> str:
    name = f"[{p.text}]({p.item.link})" if p.item and p.item.link else p.text
    if not p.each:
        price = "  ·  no market price"
    elif p.count > 1:
        price = f"  ·  {style.rub(p.each)} each"
    else:
        price = f"  ·  {style.rub(p.each)}"
    return f"**{p.count}x** {name}{price}"


def votes_text(r: LiveRecipe) -> str:
    v = r.votes
    if not v.total:
        return "No votes yet"
    lines = [f"✅ {v.worked}  ·  ❌ {v.didnt}"]
    lines.append(f"**{v.rate:.0%}** worked" if v.enough else "Not enough votes yet")
    if v.last_worked:
        where = VOTE_MODE_LABEL.get(v.last_worked_mode or "", "")
        lines.append(f"Last worked {style.relative(v.last_worked)}" + (f" in {where}" if where else ""))
    return "\n".join(lines)


def badges(r: LiveRecipe) -> list[str]:
    out = []
    if r.expired:
        out.append("Expired")
    if r.is_new:
        out.append("🆕 New")
    if r.is_updated:
        out.append("Updated")
    if r.repeatable:
        out.append("Repeatable")
    if r.restriction:
        out.append(RESTRICTION_LABEL.get(r.restriction, r.restriction))
    return out


def rewards_short(r: LiveRecipe) -> str:
    if r.rewards:
        return ", ".join(r.rewards)
    return "random: " + " / ".join(r.reward_names)


def recipe_color(r: LiveRecipe) -> int:
    if r.expired:
        return style.MUTED
    if r.votes.doubtful:
        return style.WARN
    return style.GOOD if r.votes.enough else style.ACCENT


def recipe_card(r: LiveRecipe, catalog: Catalog) -> discord.Embed:
    head = [f"⏱ **{r.time}**", *badges(r)]
    desc = ["  ·  ".join(head)]
    if r.expired:
        when = f" (retired {style.relative(r.expired_at)})" if r.expired_at else ""
        desc.append(f"~~This recipe no longer works~~{when}.")
    elif r.votes.doubtful:
        desc.append(f"⚠️ Only {r.votes.rate:.0%} of {r.votes.total} players say this worked for them.")
    e = style.embed(r.title, "\n".join(desc), color=recipe_color(r), url=r.url)

    inputs = price_entries(catalog, r.inputs, buying=True)
    e.add_field(name="Sacrifice", value=style.truncate("\n".join(map(_priced_line, inputs)), 1024), inline=False)

    if r.rewards:
        lines = [_priced_line(p) for p in price_entries(catalog, r.rewards, buying=False)]
        e.add_field(name="Reward", value=style.truncate("\n".join(lines), 1024), inline=False)
    for i, outcome in enumerate(r.outcomes[:4]):
        lines = [f"*{outcome.explanation}*"] if outcome.explanation else []
        lines += [_priced_line(p) for p in price_entries(catalog, outcome.items, buying=False)]
        name = "Reward (random)" if len(r.outcomes) == 1 else f"Possible reward {i + 1}"
        e.add_field(name=name, value=style.truncate("\n".join(lines), 1024), inline=False)

    e.add_field(name="Community", value=votes_text(r), inline=True)
    cost = sum(p.total or 0 for p in inputs) if all(p.total for p in inputs) else None
    worth = reward_worth(catalog, r)
    money = [f"Cost **{style.rub(cost)}**" if cost else "Cost n/a"]
    money.append(f"Worth {_money_range(worth.low, worth.high, worth.partial)}" if worth else "Worth n/a")
    if cost and worth:
        lo, hi = worth.low - cost, worth.high - cost
        profit = f"**{_signed(lo)}**" if lo == hi else f"**{_signed(lo)}** to **{_signed(hi)}**"
        money.append(f"Profit {'at least ' if worth.partial else ''}{profit}")
    if worth and worth.partial:
        money.append("*Some rewards have no market price*")
    e.add_field(name="Prices", value="\n".join(money), inline=True)
    return style.footer(
        e,
        "cultistcircle.com",
        f"{MODE_LABEL[catalog.mode]} prices",
        "rewards at flea, trader if no flea",
        when=catalog.data_updated,
    )


def list_line(n: int, r: LiveRecipe) -> str:
    title = style.truncate(r.title, 120)
    title = f"~~{title}~~" if r.expired else f"**{title}**"
    v = r.votes
    meta = [r.time]
    if v.total:
        meta.append(f"✅ {v.rate:.0%} of {v.total}" if v.enough else f"{v.total} vote{'s' if v.total != 1 else ''}")
    if v.doubtful and not r.expired:
        meta.append("⚠️ doubtful")
    meta += badges(r)
    return f"`{n}.` {title}\n→ {style.truncate(rewards_short(r), 150)}\n└ " + "  ·  ".join(meta)


def list_pages(found: Sequence[LiveRecipe], query: str, mode: GameMode) -> list[discord.Embed]:
    pages = []
    for start in range(0, len(found), PER_PAGE):
        chunk = found[start : start + PER_PAGE]
        lines = [list_line(start + i + 1, r) for i, r in enumerate(chunk)]
        e = style.embed(
            f"{len(found)} recipes matching \"{style.truncate(query, 60)}\"",
            "\n\n".join(lines) + "\n\nPick one below for prices and details.",
            color=style.ACCENT,
        )
        pages.append(style.footer(e, "cultistcircle.com/recipes", MODE_LABEL[mode]))
    return pages


# ---------------------------------------------------------------- picture

def _tile(p: Priced, count: int | None = None) -> Tile:
    url = (p.item.image or p.item.icon) if p.item else None
    return Tile(p.count if count is None else count, p.text, url)


async def card_reply(r: LiveRecipe, catalog: Catalog, session: aiohttp.ClientSession | None) -> Reply:
    """The recipe card, plus a picture of its icons when we can reach the icon CDN."""
    embed = recipe_card(r, catalog)
    if session is None or session.closed:
        return {"embed": embed}
    inputs = [_tile(p) for p in price_entries(catalog, r.inputs, buying=True)]
    if r.rewards:
        rewards = [_tile(p) for p in price_entries(catalog, r.rewards, buying=False)]
    else:
        seen: dict[str, Tile] = {}
        for p in price_entries(catalog, r.reward_names, buying=False):
            seen.setdefault(p.text, _tile(p, count=1))
        rewards = list(seen.values())
    try:
        icons = await load_icons(session, inputs + rewards)
        png = await asyncio.to_thread(render_recipe, inputs, rewards, icons, not r.rewards)
    except Exception:
        log.warning("Couldn't draw recipe picture", exc_info=True)
        return {"embed": embed}
    embed.set_image(url="attachment://recipe.png")
    return {"embed": embed, "file": discord.File(io.BytesIO(png), filename="recipe.png")}


# ---------------------------------------------------------------- views

CardRender = Callable[[LiveRecipe], Awaitable[Reply]]


class RecipeCardView(OwnedView):
    """A recipe card, with a way back to the list it came from."""

    def __init__(self, recipe: LiveRecipe, owner_id: int, back: RecipeBrowser | None = None) -> None:
        super().__init__(owner_id, timeout=300)
        self.back_to = back
        if back is None:
            self.remove_item(self.back)
        self.add_item(discord.ui.Button(label="Vote on cultistcircle.com", url=recipe.url))

    @discord.ui.button(label="Back to list", style=discord.ButtonStyle.secondary)
    async def back(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        assert self.back_to is not None
        self.back_to.message = self.message
        self.back_to.sync()
        await interaction.response.edit_message(
            embed=self.back_to.pages[self.back_to.index], view=self.back_to, attachments=[]
        )
        self.stop()


class RecipeBrowser(OwnedView):
    def __init__(self, found: Sequence[LiveRecipe], pages: list[discord.Embed], render: CardRender, owner_id: int) -> None:
        super().__init__(owner_id, timeout=300)
        self.found = list(found)
        self.pages = pages
        self.render = render
        self.index = 0
        self.picker = discord.ui.Select(placeholder="Open a recipe", row=0)
        self.picker.callback = self._picked
        self.add_item(self.picker)
        self.sync()

    def sync(self) -> None:
        start = self.index * PER_PAGE
        self.picker.options = [
            discord.SelectOption(
                label=style.truncate(f"{start + i + 1}. {r.title}", 100),
                description=style.truncate("→ " + rewards_short(r), 100),
                value=str(start + i),
            )
            for i, r in enumerate(self.found[start : start + PER_PAGE])
        ]
        self.prev.disabled = self.index == 0
        self.next.disabled = self.index >= len(self.pages) - 1
        self.counter.label = f"{self.index + 1} / {len(self.pages)}"
        if len(self.pages) == 1:
            for b in (self.prev, self.counter, self.next):
                if b in self.children:
                    self.remove_item(b)

    async def _picked(self, interaction: discord.Interaction) -> None:
        recipe = self.found[int(self.picker.values[0])]
        await interaction.response.defer()
        card = RecipeCardView(recipe, self.owner_id, back=self)
        card.message = self.message
        reply = await self.render(recipe)
        reply["view"] = card
        await interaction.edit_original_response(**edit_kwargs(reply))

    @discord.ui.button(label="Prev", style=discord.ButtonStyle.secondary, row=1)
    async def prev(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        self.index = max(0, self.index - 1)
        self.sync()
        await interaction.response.edit_message(embed=self.pages[self.index], view=self)

    @discord.ui.button(label="1 / 1", style=discord.ButtonStyle.secondary, disabled=True, row=1)
    async def counter(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.defer()

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary, row=1)
    async def next(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        self.index = min(len(self.pages) - 1, self.index + 1)
        self.sync()
        await interaction.response.edit_message(embed=self.pages[self.index], view=self)


async def recipe_reply(
    book: RecipeBook, catalog: Catalog, query: str, owner_id: int, session: aiohttp.ClientSession | None = None
) -> Reply:
    """send() kwargs for a search: a card for one match, a pick list for several, or an error."""
    found = search(book, query, catalog.mode)
    if not found:
        other = {RESTRICTION_LABEL.get(r.restriction or "", "") for m in MODES for r in search(book, query, m)} - {""}
        hint = f"\nThere's a {' / '.join(sorted(other))} match. Try another mode." if other else ""
        e = style.error(
            f"No recipe uses or gives **{style.truncate(query, 80)}**.{hint}\nFull list: {RECIPES_URL}",
            "No recipes found",
        )
        return {"embed": e}

    async def render(r: LiveRecipe) -> Reply:
        return await card_reply(r, catalog, session)

    if len(found) == 1:
        reply = await render(found[0])
        reply["view"] = RecipeCardView(found[0], owner_id)
        return reply
    pages = list_pages(found, query, catalog.mode)
    return {"embed": pages[0], "view": RecipeBrowser(found, pages, render, owner_id)}


# ---------------------------------------------------------------- cog

class Recipes(commands.Cog):
    def __init__(self, bot: NerdBot) -> None:
        self.bot = bot

    @property
    def source(self) -> RecipeSource | None:
        return getattr(self.bot, "recipes", None)

    async def book(self) -> RecipeBook:
        from ..bot import DataUnavailable

        if self.source is None:
            raise DataUnavailable("Recipes aren't loaded yet. Give it a minute and try again.")
        try:
            return await self.source.get()
        except Exception as exc:
            raise DataUnavailable("Couldn't reach cultistcircle.com for recipes. Try again in a minute.") from exc

    @app_commands.command(name="recipe", description="Cultist Circle recipes with community votes and live prices")
    @app_commands.describe(
        search="An item to sacrifice or get, e.g. fence figurine",
        mode="Game mode for prices and mode-only recipes (default PvP)",
    )
    @app_commands.choices(mode=MODE_CHOICES)
    @app_commands.checks.cooldown(3, 15)
    async def recipe(
        self, interaction: discord.Interaction, search: str, mode: app_commands.Choice[str] | None = None
    ) -> None:
        await interaction.response.defer()
        book = await self.book()
        catalog = await catalog_for(self.bot, mode.value if mode else None)
        reply = await recipe_reply(book, catalog, search, interaction.user.id, self.bot.session)
        msg = await interaction.followup.send(**reply, wait=True)
        if view := reply.get("view"):
            view.message = msg

    @recipe.autocomplete("search")
    async def _recipe_names(self, interaction: discord.Interaction, current: str):
        if self.source is None:
            return []
        book = self.source.peek()
        if book is None:
            # Discord drops autocomplete answers after 3 seconds, so don't wait long.
            try:
                book = await asyncio.wait_for(self.source.get(), timeout=2.0)
            except Exception:
                return []
        options = names(book)
        if current:
            low = current.lower()
            options = [n for n in options if low in n.lower()]
        return [app_commands.Choice(name=style.truncate(n, 100), value=style.truncate(n, 100)) for n in options[:25]]

    @commands.command(name="recipe", aliases=["recipes"])
    @commands.cooldown(3, 15, commands.BucketType.user)
    async def recipe_prefix(self, ctx: commands.Context, *, query: str) -> None:
        """!recipe <item> [pve|season]"""
        text, mode = split_mode(query)
        book = await self.book()
        catalog = await catalog_for(self.bot, mode)
        reply = await recipe_reply(book, catalog, text, ctx.author.id, self.bot.session)
        msg = await ctx.reply(**reply, mention_author=False)
        if view := reply.get("view"):
            view.message = msg


async def setup(bot: NerdBot) -> None:
    await bot.add_cog(Recipes(bot))


