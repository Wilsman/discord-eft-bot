from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

import discord
from discord import app_commands

from .. import style
from ..tarkov import MODE_LABEL, Catalog, GameMode, Item
from ..views import ItemPicker, Render, Reply, picker_embed

if TYPE_CHECKING:
    from ..bot import NerdBot

MODE_CHOICES = [app_commands.Choice(name=label, value=mode) for mode, label in MODE_LABEL.items()]
Send = Callable[..., Awaitable[discord.Message | None]]


async def catalog_for(bot: NerdBot, mode: str | None) -> Catalog:
    from ..bot import DataUnavailable

    assert bot.store is not None
    try:
        return await bot.store.get((mode or "regular"))  # type: ignore[arg-type]
    except Exception as exc:
        raise DataUnavailable("Market data isn't loaded yet. Give it a minute and try again.") from exc


def mode_of(interaction: discord.Interaction) -> GameMode:
    value = getattr(interaction.namespace, "mode", None)
    return value if value in MODE_LABEL else "regular"  # type: ignore[return-value]


def choice_label(item: Item) -> str:
    offer = item.cheapest_buy()
    price = item.flea_price or (offer.price_rub if offer else None)
    bits = [item.name]
    if item.base:
        bits.append(f"base {style.compact(item.base)}")
    if price:
        bits.append(f"{style.compact(price)}{style.RUB}")
    return style.truncate("  ·  ".join(bits), 100)


async def item_choices(
    interaction: discord.Interaction,
    current: str,
    where: Callable[[Item], bool] | None = None,
) -> list[app_commands.Choice[str]]:
    bot: NerdBot = interaction.client  # type: ignore[assignment]
    if bot.store is None or len(current.strip()) < 2:
        return []
    catalog = bot.store.peek(mode_of(interaction)) or bot.store.peek("regular")
    if catalog is None:
        return []
    return [
        app_commands.Choice(name=choice_label(item), value=item.id)
        for item, _ in catalog.index.search(current, limit=20, where=where)
    ]


def lookup(
    catalog: Catalog, query: str, where: Callable[[Item], bool] | None = None
) -> tuple[Item | None, list[Item]]:
    """Autocomplete hands us an item id; typed text goes through fuzzy search."""
    item = catalog.by_id.get(query.strip())
    if item is not None:
        return item, []
    return catalog.index.resolve(query, where)


async def reply_for_item(
    send: Send,
    owner_id: int,
    catalog: Catalog,
    query: str,
    render: Render,
    where: Callable[[Item], bool] | None = None,
    what: str = "item",
) -> None:
    item, candidates = lookup(catalog, query, where)
    if item is not None:
        await send(**(await render(item)))
        return
    if not candidates:
        await send(
            embed=style.error(
                f"Couldn't find an {what} matching **{style.truncate(query, 80)}**. "
                "Try the full name, or pick from the suggestions as you type.",
                title="No match",
            )
        )
        return
    view = ItemPicker(candidates, render, owner_id)
    view.message = await send(embed=picker_embed(query, candidates), view=view)


def followup(interaction: discord.Interaction) -> Send:
    async def send(**kwargs) -> discord.Message:
        kwargs.setdefault("wait", True)
        return await interaction.followup.send(**kwargs)

    return send


__all__ = [
    "MODE_CHOICES",
    "Reply",
    "catalog_for",
    "choice_label",
    "followup",
    "item_choices",
    "lookup",
    "mode_of",
    "reply_for_item",
]
