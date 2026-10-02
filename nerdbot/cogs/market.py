from __future__ import annotations

import math
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from .. import style
from ..circle.tiers import MAX_SLOTS, SIX_HOUR_THRESHOLD, tier_for
from ..tarkov import MODE_LABEL, Catalog, Item
from ..views import Reply, link_view
from ._common import MODE_CHOICES, catalog_for, followup, item_choices, reply_for_item

if TYPE_CHECKING:
    from ..bot import NerdBot


def _kind(item: Item) -> str:
    for cat in item.categories:
        if cat and cat not in ("Item", "Compound item", "Stackable item"):
            return cat
    return "Item"


def circle_hint(base: int) -> str:
    if base <= 0:
        return "No circle value"
    copies = math.ceil(SIX_HOUR_THRESHOLD / base)
    if copies <= MAX_SLOTS:
        return f"{copies}x reaches 400k" if copies > 1 else "Hits 400k on its own"
    return f"5x = {style.compact(base * MAX_SLOTS)} ({tier_for(base * MAX_SLOTS).short})"


def price_embed(item: Item, catalog: Catalog) -> discord.Embed:
    mode = MODE_LABEL[catalog.mode]
    lines = [f"**{_kind(item)}**  ·  {item.width}x{item.height}  ·  {mode}"]
    if item.unstable:
        lines.append(f"*Only {item.offers} listings, so the flea price may be unstable.*")
    e = style.embed(item.name, "\n".join(lines), url=item.link, color=style.ACCENT)
    if item.image:
        e.set_thumbnail(url=item.image)

    if "noFlea" in item.types:
        flea = "Can't be listed"
    elif not catalog.flea_enabled:
        flea = f"Flea is off in {mode}"
    elif item.flea_low:
        change = f"\n{style.pct(item.change48)} in 48h" if item.change48 is not None else ""
        flea = f"**{style.rub(item.flea_low)}**{change}"
    else:
        flea = "No listings"
    e.add_field(name="Flea market", value=flea)

    if item.avg24:
        spread = (
            f"\n{style.compact(item.low24)} to {style.compact(item.high24)}"
            if item.low24 and item.high24
            else ""
        )
        e.add_field(name="24h average", value=f"{style.rub(item.avg24)}{spread}")
    else:
        e.add_field(name="24h average", value="n/a")

    ref = item.flea_price or (item.sell.price_rub if item.sell else None)
    per_slot = style.rub(ref / item.slots) if ref else "n/a"
    e.add_field(name="Per slot", value=f"{per_slot}\n{item.slots} slot{'s' if item.slots > 1 else ''}")

    if item.sell:
        native = f" ({item.sell.currency} {item.sell.price:,})" if item.sell.currency != "RUB" else ""
        e.add_field(name="Best trader sell", value=f"**{style.rub(item.sell.price_rub)}**{native}\n{item.sell.trader}")
    else:
        e.add_field(name="Best trader sell", value="Traders won't buy it")

    offer = item.cheapest_buy()
    if offer:
        extras = []
        if offer.buy_limit:
            extras.append(f"limit {offer.buy_limit}")
        if offer.quest_locked:
            extras.append("quest locked")
        tail = f"  ({', '.join(extras)})" if extras else ""
        e.add_field(name="Cheapest trader buy", value=f"{style.rub(offer.price_rub)}\n{offer.label}{tail}")
    else:
        e.add_field(name="Cheapest trader buy", value="Not sold by traders")

    e.add_field(name="Base value", value=f"**{style.rub(item.base)}**\n{circle_hint(item.base)}")
    return style.footer(e, "tarkov.dev", mode, when=item.updated)


def ammo_embed(item: Item, catalog: Catalog) -> discord.Embed:
    ammo = item.ammo
    assert ammo is not None
    e = style.embed(item.name, f"**{ammo.caliber}**  ·  {ammo.ammo_type.title()}", url=item.link, color=style.INFO)
    if item.image:
        e.set_thumbnail(url=item.image)
    damage = f"{ammo.projectiles} x {ammo.damage} = **{ammo.total_damage}**" if ammo.projectiles > 1 else f"**{ammo.damage}**"
    e.add_field(name="Damage", value=damage)
    e.add_field(name="Penetration", value=f"**{ammo.penetration}**")
    e.add_field(name="Armor damage", value=f"{ammo.armor_damage}%")
    e.add_field(name="Fragmentation", value=f"{ammo.fragmentation * 100:.0f}%")
    e.add_field(name="Velocity", value=f"{ammo.speed} m/s" if ammo.speed else "n/a")
    e.add_field(name="Flea", value=style.rub(item.flea_price) if item.flea_price else "Not on flea")

    rounds = sorted(
        (i for i in catalog.ammo_for(ammo.caliber) if "ammoBox" not in i.types),
        key=lambda i: (-i.ammo.penetration, -i.ammo.total_damage),  # type: ignore[union-attr]
    )
    if len(rounds) > 1:
        rows = [["", "ROUND", "DMG", "PEN", "ARM", "FLEA"]]
        shown = rounds[:14]
        if item not in shown:
            shown[-1] = item
        for r in shown:
            a = r.ammo
            assert a is not None
            rows.append([
                ">" if r.id == item.id else "",
                style.truncate(r.short or r.name, 14),
                str(a.total_damage),
                str(a.penetration),
                f"{a.armor_damage}",
                style.compact(r.flea_price) if r.flea_price else "-",
            ])
        e.add_field(name=f"{ammo.caliber} lineup, by penetration", value=style.table(rows, "llrrrr"), inline=False)
    return style.footer(e, "tarkov.dev", MODE_LABEL[catalog.mode], when=item.updated)


def item_links(item: Item) -> discord.ui.View:
    return link_view(("tarkov.dev", item.link or ""), ("Wiki", item.wiki or ""))


def _split_mode(text: str) -> tuple[str, str]:
    words = text.split()
    aliases = {"pve": "pve", "pvp": "regular", "season": "pvp-season"}
    if len(words) > 1 and words[-1].lower() in aliases:
        return " ".join(words[:-1]), aliases[words[-1].lower()]
    return text, "regular"


class Market(commands.Cog):
    def __init__(self, bot: NerdBot) -> None:
        self.bot = bot

    @app_commands.command(name="price", description="Flea, trader and base value for any item")
    @app_commands.describe(item="Start typing an item name", mode="Which market to read (default PvP)")
    @app_commands.choices(mode=MODE_CHOICES)
    async def price(
        self, interaction: discord.Interaction, item: str, mode: app_commands.Choice[str] | None = None
    ) -> None:
        await interaction.response.defer()
        catalog = await catalog_for(self.bot, mode.value if mode else None)

        async def render(it: Item) -> Reply:
            return {"embed": price_embed(it, catalog), "view": item_links(it)}

        await reply_for_item(followup(interaction), interaction.user.id, catalog, item, render)

    @price.autocomplete("item")
    async def _price_items(self, interaction: discord.Interaction, current: str):
        return await item_choices(interaction, current)

    @app_commands.command(name="ammo", description="Ballistics for a round, plus its caliber lineup")
    @app_commands.rename(round_="round")
    @app_commands.describe(round_="Start typing a round, e.g. M995 or BS", mode="Which market to read (default PvP)")
    @app_commands.choices(mode=MODE_CHOICES)
    async def ammo(
        self, interaction: discord.Interaction, round_: str, mode: app_commands.Choice[str] | None = None
    ) -> None:
        await interaction.response.defer()
        catalog = await catalog_for(self.bot, mode.value if mode else None)

        async def render(it: Item) -> Reply:
            return {"embed": ammo_embed(it, catalog), "view": item_links(it)}

        await reply_for_item(
            followup(interaction),
            interaction.user.id,
            catalog,
            round_,
            render,
            where=lambda i: i.ammo is not None and "ammoBox" not in i.types,
            what="round",
        )

    @ammo.autocomplete("round_")
    async def _ammo_rounds(self, interaction: discord.Interaction, current: str):
        return await item_choices(interaction, current, where=lambda i: i.ammo is not None and "ammoBox" not in i.types)

    @commands.command(name="price", aliases=["p"])
    @commands.cooldown(3, 10, commands.BucketType.user)
    async def price_prefix(self, ctx: commands.Context, *, query: str) -> None:
        """!price <item> [pve|season]"""
        text, mode = _split_mode(query)
        catalog = await catalog_for(self.bot, mode)

        async def render(it: Item) -> Reply:
            return {"embed": price_embed(it, catalog), "view": item_links(it)}

        async def send(**kwargs):
            return await ctx.reply(mention_author=False, **kwargs)

        await reply_for_item(send, ctx.author.id, catalog, text, render)


async def setup(bot: NerdBot) -> None:
    await bot.add_cog(Market(bot))
