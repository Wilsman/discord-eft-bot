"""Interactive components: item disambiguation and paging."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import Any

import discord

from . import style
from .tarkov import Item

Reply = dict[str, Any]  # kwargs for send(): embed, file, view
Render = Callable[[Item], Awaitable[Reply]]


def edit_kwargs(reply: Reply) -> Reply:
    """Translate send() kwargs into edit_message() kwargs."""
    out = {k: v for k, v in reply.items() if k not in ("file", "files")}
    files = reply.get("files") or ([reply["file"]] if reply.get("file") else [])
    out["attachments"] = files
    out.setdefault("view", None)
    return out


def item_option_label(item: Item) -> str:
    return style.truncate(item.name, 100)


def item_option_description(item: Item) -> str:
    bits = [f"Base {style.compact(item.base)}"]
    if item.flea_price:
        bits.append(f"Flea {style.compact(item.flea_price)}")
    if item.ammo:
        bits.append(f"{item.ammo.caliber}  {item.ammo.damage}/{item.ammo.penetration}")
    return style.truncate("  ·  ".join(bits), 100)


class OwnedView(discord.ui.View):
    """A view only the person who ran the command can drive."""

    def __init__(self, owner_id: int, timeout: float = 180) -> None:
        super().__init__(timeout=timeout)
        self.owner_id = owner_id
        self.message: discord.Message | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message(
            "That menu belongs to someone else. Run the command yourself to get your own.",
            ephemeral=True,
        )
        return False

    async def on_timeout(self) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button) and child.url:
                continue  # link buttons keep working
            if isinstance(child, (discord.ui.Button, discord.ui.Select)):
                child.disabled = True
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


class ItemPicker(OwnedView):
    def __init__(self, items: Sequence[Item], render: Render, owner_id: int) -> None:
        super().__init__(owner_id)
        self._items = list(items)[:25]
        self._render = render
        self.select = discord.ui.Select(
            placeholder="Which one did you mean?",
            options=[
                discord.SelectOption(
                    label=item_option_label(item),
                    description=item_option_description(item),
                    value=str(i),
                )
                for i, item in enumerate(self._items)
            ],
        )
        self.select.callback = self._picked
        self.add_item(self.select)

    async def _picked(self, interaction: discord.Interaction) -> None:
        item = self._items[int(self.select.values[0])]
        await interaction.response.defer()
        reply = await self._render(item)
        await interaction.edit_original_response(**edit_kwargs(reply))
        self.stop()


def picker_embed(query: str, items: Sequence[Item]) -> discord.Embed:
    lines = "\n".join(f"`{i + 1}.` {item.name}" for i, item in enumerate(items[:8]))
    return style.embed(
        "A few things match that",
        f"Results for **{style.truncate(query, 80)}**:\n{lines}\n\nPick one below.",
        color=style.MUTED,
    )


class Pager(OwnedView):
    def __init__(self, pages: Sequence[discord.Embed], owner_id: int) -> None:
        super().__init__(owner_id, timeout=300)
        self.pages = list(pages)
        self.index = 0
        self._sync()

    def _sync(self) -> None:
        self.prev.disabled = self.index == 0
        self.next.disabled = self.index >= len(self.pages) - 1
        self.counter.label = f"{self.index + 1} / {len(self.pages)}"

    @discord.ui.button(label="Prev", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        self.index = max(0, self.index - 1)
        self._sync()
        await interaction.response.edit_message(embed=self.pages[self.index], view=self)

    @discord.ui.button(label="1 / 1", style=discord.ButtonStyle.secondary, disabled=True)
    async def counter(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.defer()

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        self.index = min(len(self.pages) - 1, self.index + 1)
        self._sync()
        await interaction.response.edit_message(embed=self.pages[self.index], view=self)


def link_view(*links: tuple[str, str]) -> discord.ui.View:
    view = discord.ui.View()
    for label, url in links:
        if url:
            view.add_item(discord.ui.Button(label=label, url=url))
    return view
