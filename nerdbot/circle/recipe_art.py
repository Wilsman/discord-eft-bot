"""Draw a recipe as icons: sacrifice -> reward, with counts. Icons come from assets.tarkov.dev."""

from __future__ import annotations

import asyncio
import io
import logging
from collections import OrderedDict
from collections.abc import Iterable
from dataclasses import dataclass

import aiohttp
from PIL import Image, ImageDraw

from .card import BG_BOTTOM, FOOTNOTE, PANEL, PANEL_BORDER, TEXT, TEXT_DIM, _font, _gradient, _s

log = logging.getLogger("nerdbot.recipes")

TILE = 84
GAP = 10
PAD = 20
ARROW_W = 44
LABEL_H = 22
MAX_TILES = 6  # per side; more than this collapses into "+N"
TILE_BG = (24, 28, 36)
COUNT_BG = (8, 10, 14)
AMBER = (234, 179, 8)

_CACHE: OrderedDict[str, Image.Image | None] = OrderedDict()
_CACHE_SIZE = 400


@dataclass(frozen=True, slots=True)
class Tile:
    count: int
    name: str
    url: str | None


async def _fetch(session: aiohttp.ClientSession, url: str) -> Image.Image | None:
    if url in _CACHE:
        _CACHE.move_to_end(url)
        return _CACHE[url]
    img = None
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=6)) as resp:
            if resp.status == 200:
                img = Image.open(io.BytesIO(await resp.read())).convert("RGBA")
    except Exception:
        log.debug("Icon fetch failed for %s", url, exc_info=True)
    _CACHE[url] = img
    while len(_CACHE) > _CACHE_SIZE:
        _CACHE.popitem(last=False)
    return img


async def load_icons(session: aiohttp.ClientSession, tiles: Iterable[Tile]) -> dict[str, Image.Image | None]:
    urls = list(dict.fromkeys(t.url for t in tiles if t.url))
    images = await asyncio.gather(*(_fetch(session, u) for u in urls))
    return dict(zip(urls, images))


def _draw_name(draw: ImageDraw.ImageDraw, x: int, y: int, name: str) -> None:
    """No icon: write the item name, wrapped to fit the tile."""
    font = _font(11, 600)
    lines: list[str] = []
    for word in name.split():
        if lines and draw.textlength(f"{lines[-1]} {word}", font=font) <= _s(TILE - 12):
            lines[-1] = f"{lines[-1]} {word}"
        else:
            lines.append(word)
    if len(lines) > 4:
        lines = lines[:3] + ["..."]
    step = 14
    top = y + TILE / 2 - (len(lines) - 1) * step / 2
    for i, line in enumerate(lines):
        draw.text((_s(x + TILE / 2), _s(top + i * step)), line, font=font, fill=TEXT_DIM, anchor="mm")


def _draw_tile(img: Image.Image, x: int, y: int, tile: Tile, icon: Image.Image | None) -> None:
    draw = ImageDraw.Draw(img)
    box = [_s(x), _s(y), _s(x + TILE), _s(y + TILE)]
    draw.rounded_rectangle(box, radius=_s(8), fill=TILE_BG, outline=PANEL_BORDER, width=_s(1))
    inner = _s(TILE - 12)
    if icon is not None:
        pic = icon.copy()
        pic.thumbnail((inner, inner), Image.LANCZOS)
        if max(pic.size) < inner:  # small icons get scaled up so they fill the tile
            ratio = inner / max(pic.size)
            pic = icon.resize((max(1, round(icon.width * ratio)), max(1, round(icon.height * ratio))), Image.LANCZOS)
        px = _s(x) + (_s(TILE) - pic.width) // 2
        py = _s(y) + (_s(TILE) - pic.height) // 2
        img.alpha_composite(pic, (px, py))
    else:
        _draw_name(draw, x, y, tile.name)
    if tile.count > 1:
        label = f"{tile.count}x"
        font = _font(13, 700)
        w = draw.textlength(label, font=font)
        bx1, by1 = _s(x + TILE - 4), _s(y + TILE - 4)
        draw.rounded_rectangle([bx1 - w - _s(10), by1 - _s(20), bx1, by1], radius=_s(5), fill=COUNT_BG)
        draw.text((bx1 - _s(5), by1 - _s(10)), label, font=font, fill=AMBER, anchor="rm")


def _side(tiles: list[Tile]) -> tuple[list[Tile], int]:
    if len(tiles) <= MAX_TILES:
        return tiles, 0
    return tiles[: MAX_TILES - 1], len(tiles) - (MAX_TILES - 1)


def _row_width(n: int) -> int:
    return n * TILE + max(0, n - 1) * GAP


def render_recipe(
    inputs: list[Tile], rewards: list[Tile], icons: dict[str, Image.Image | None], random: bool = False
) -> bytes:
    left, left_more = _side(inputs)
    right, right_more = _side(rewards)
    n_left = len(left) + (1 if left_more else 0)
    n_right = max(1, len(right) + (1 if right_more else 0))
    width = PAD * 2 + _row_width(n_left) + ARROW_W + _row_width(n_right)
    height = PAD * 2 + LABEL_H + TILE

    img = _gradient(_s(width), _s(height)).convert("RGBA")
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle(
        [0, 0, _s(width) - 1, _s(height) - 1], radius=_s(12), fill=PANEL, outline=PANEL_BORDER, width=_s(1)
    )
    label_font = _font(11, 600)
    y = PAD + LABEL_H

    def row(x: int, tiles: list[Tile], more: int, title: str) -> int:
        draw.text((_s(x), _s(PAD)), title, font=label_font, fill=FOOTNOTE)
        for t in tiles:
            _draw_tile(img, x, y, t, icons.get(t.url or ""))
            x += TILE + GAP
        if more:
            box = [_s(x), _s(y), _s(x + TILE), _s(y + TILE)]
            draw.rounded_rectangle(box, radius=_s(8), fill=BG_BOTTOM, outline=PANEL_BORDER, width=_s(1))
            draw.text((_s(x + TILE / 2), _s(y + TILE / 2)), f"+{more}", font=_font(18, 700), fill=TEXT_DIM, anchor="mm")
            x += TILE + GAP
        return x - GAP

    x = row(PAD, left, left_more, "SACRIFICE")
    ax, ay = x + ARROW_W / 2, y + TILE / 2
    draw.line([(_s(ax - 12), _s(ay)), (_s(ax + 10), _s(ay))], fill=AMBER, width=_s(3))
    draw.polygon([(_s(ax + 14), _s(ay)), (_s(ax + 5), _s(ay - 7)), (_s(ax + 5), _s(ay + 7))], fill=AMBER)
    rx = x + ARROW_W
    if right or right_more:
        row(rx, right, right_more, "RANDOM REWARD" if random else "REWARD")
    else:
        draw.text((_s(rx), _s(PAD)), "REWARD", font=label_font, fill=FOOTNOTE)
        draw.text((_s(rx + TILE / 2), _s(y + TILE / 2)), "?", font=_font(28, 700), fill=TEXT_DIM, anchor="mm")

    out = io.BytesIO()
    img.convert("RGB").save(out, format="PNG", optimize=True)
    return out.getvalue()
