"""Render the Cultist Circle thresholds card (matches the chart on cultistcircle.com)."""

from __future__ import annotations

import io
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .tiers import TIERS, tier_index

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
SCALE = 2  # render at 2x so Discord's downscale stays crisp

WIDTH = 720
PAD = 28
ROW_H = 36
ROW_GAP = 4
FOOTER_H = 52

BG_TOP = (11, 17, 28)
BG_BOTTOM = (15, 23, 38)
PANEL = (13, 16, 22)
PANEL_BORDER = (32, 37, 46)
ROW_ACTIVE = (25, 29, 36)
ROW_ACTIVE_RING = (44, 49, 58)
TEXT_DIM = (156, 163, 175)
TEXT = (243, 244, 246)
FOOTNOTE = (115, 122, 135)
SIX_HOUR_GREEN = (74, 222, 128)
FOURTEEN_GREEN = (59, 131, 100)


def _rgb(color: int) -> tuple[int, int, int]:
    return (color >> 16) & 255, (color >> 8) & 255, color & 255


@lru_cache(maxsize=8)
def _font(size: int, weight: int, italic: bool = False) -> ImageFont.FreeTypeFont:
    name = "GeistMono-Italic-VF.ttf" if italic else "GeistMono-VF.ttf"
    font = ImageFont.truetype(str(FONT_DIR / name), size * SCALE)
    try:
        font.set_variation_by_axes([weight])
    except (OSError, AttributeError):  # FreeType built without variation support
        pass
    return font


def _s(v: float) -> int:
    return round(v * SCALE)


def _gradient(width: int, height: int) -> Image.Image:
    base = Image.new("RGB", (width, height), BG_TOP)
    draw = ImageDraw.Draw(base)
    for y in range(height):
        t = y / max(1, height - 1)
        draw.line(
            [(0, y), (width, y)],
            fill=tuple(round(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOTTOM)),
        )
    return base


@lru_cache(maxsize=16)
def render_thresholds(total: int | None = None) -> bytes:
    """PNG bytes of the thresholds chart.

    With ``total`` the matching tier is highlighted and a header shows the total;
    without it the 400k row is highlighted like the website's default view.
    """
    active = tier_index(total) if total is not None else len(TIERS) - 1
    header_h = 78 if total is not None else 0
    rows_h = len(TIERS) * ROW_H + (len(TIERS) - 1) * ROW_GAP
    panel_h = header_h + 20 + rows_h + 20 + FOOTER_H
    height = panel_h + PAD * 2

    img = _gradient(_s(WIDTH), _s(height))
    draw = ImageDraw.Draw(img)

    px0, py0 = _s(PAD), _s(PAD)
    px1, py1 = _s(WIDTH - PAD), _s(PAD + panel_h)
    draw.rounded_rectangle([px0, py0, px1, py1], radius=_s(14), fill=PANEL, outline=PANEL_BORDER, width=_s(1))

    label_font = _font(15, 600)
    bold_font = _font(15, 700)
    left = PAD + 24
    right = WIDTH - PAD - 24
    y = PAD + 20

    if total is not None:
        head = _font(13, 500)
        draw.text((_s(left), _s(y)), "YOUR SACRIFICE", font=head, fill=FOOTNOTE)
        draw.text((_s(left), _s(y + 18)), f"{total:,}", font=_font(19, 700), fill=TEXT)
        tier = TIERS[active]
        tag = tier.hours
        tw = draw.textlength(tag, font=bold_font)
        draw.text((_s(right) - tw, _s(y + 20)), tag, font=bold_font, fill=_rgb(tier.color))
        nxt = TIERS[active + 1] if active + 1 < len(TIERS) else None
        hint = (
            f"{nxt.minimum - total:,} more for {nxt.hours.split(' or ')[0]}"
            if nxt
            else "Max tier. More value won't raise the 6h chance."
        )
        draw.text((_s(left), _s(y + 46)), hint, font=_font(12, 400), fill=FOOTNOTE)
        y += header_h

    for i, tier in enumerate(TIERS):
        top = y + i * (ROW_H + ROW_GAP)
        mid = _s(top + ROW_H / 2)
        is_active = i == active
        is_last = i == len(TIERS) - 1
        if is_active:
            draw.rounded_rectangle(
                [_s(left - 12), _s(top), _s(right + 12), _s(top + ROW_H)],
                radius=_s(6),
                fill=ROW_ACTIVE,
                outline=ROW_ACTIVE_RING,
                width=_s(1),
            )
        label = f"{tier.range_label} {tier.note}".strip()
        draw.text(
            (_s(left), mid),
            label,
            font=bold_font if is_last else label_font,
            fill=TEXT if (is_active or is_last) else TEXT_DIM,
            anchor="lm",
        )
        if is_last:
            parts = [("6 hours", SIX_HOUR_GREEN), (" or ", TEXT), ("14 hours", FOURTEEN_GREEN)]
            x = _s(right) - sum(draw.textlength(t, font=bold_font) for t, _ in parts)
            for text, color in parts:
                draw.text((x, mid), text, font=bold_font, fill=color, anchor="lm")
                x += draw.textlength(text, font=bold_font)
        else:
            draw.text((_s(right), mid), tier.hours, font=bold_font, fill=_rgb(tier.color), anchor="rm")

    sep_y = y + rows_h + 20
    draw.line([(px0, _s(sep_y)), (px1, _s(sep_y))], fill=PANEL_BORDER, width=_s(1))
    draw.text(
        (_s(WIDTH / 2), _s(sep_y + FOOTER_H / 2)),
        "* Higher thresholds increase the quality and rarity of returned items.",
        font=_font(12, 400, italic=True),
        fill=FOOTNOTE,
        anchor="mm",
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
