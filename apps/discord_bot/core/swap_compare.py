# apps/discord_bot/core/swap_compare.py
"""Side-by-side OUT/IN card compare image for squad swap UX."""
from __future__ import annotations

import asyncio
import io
from typing import Any

import discord
from PIL import Image, ImageDraw, ImageFont

from apps.discord_bot.core.pitch_generator import _ASSETS_DIR, _RENDER_SEM

_ATTR_KEYS = ("pac", "sho", "pas", "dri", "def", "phy")
_RARITY_COLORS = {
    "Legendary": (255, 215, 0, 255),
    "Epic": (163, 73, 164, 255),
    "Rare": (0, 162, 232, 255),
    "Common": (192, 192, 192, 255),
}


async def generate_swap_compare_image(
    out_card: dict[str, Any] | None,
    in_card: dict[str, Any] | None,
) -> discord.File:
    font_bold = str(_ASSETS_DIR / "fonts" / "Roboto-Bold.ttf")
    font_reg = str(_ASSETS_DIR / "fonts" / "Roboto-Regular.ttf")
    async with _RENDER_SEM:
        return await asyncio.to_thread(
            _render_swap_compare, out_card, in_card, font_bold, font_reg
        )


def _load_fonts(
    bold_path: str, reg_path: str
) -> tuple[ImageFont.ImageFont, ImageFont.ImageFont, ImageFont.ImageFont, ImageFont.ImageFont]:
    try:
        return (
            ImageFont.truetype(bold_path, 22),
            ImageFont.truetype(bold_path, 28),
            ImageFont.truetype(bold_path, 16),
            ImageFont.truetype(reg_path, 14),
        )
    except OSError:
        d = ImageFont.load_default()
        return d, d, d, d


def _draw_panel(
    draw: ImageDraw.ImageDraw,
    *,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    title: str,
    card: dict[str, Any] | None,
    placeholder: str,
    font_title: ImageFont.ImageFont,
    font_ovr: ImageFont.ImageFont,
    font_name: ImageFont.ImageFont,
    font_sub: ImageFont.ImageFont,
) -> None:
    rarity = (card or {}).get("rarity", "Common") if card else "Common"
    border = _RARITY_COLORS.get(str(rarity), _RARITY_COLORS["Common"])
    if not card:
        border = (120, 130, 145, 255)

    draw.rounded_rectangle(
        [x0, y0, x1, y1],
        radius=10,
        fill=(28, 34, 46, 255),
        outline=border,
        width=2,
    )
    draw.text((x0 + 14, y0 + 10), title, fill=border, font=font_title)

    if not card:
        draw.text((x0 + 14, y0 + 90), placeholder, fill=(150, 160, 175, 255), font=font_name)
        return

    ovr = str(card.get("overall", "?"))
    draw.text((x0 + 14, y0 + 44), ovr, fill=border, font=font_ovr)
    draw.text((x0 + 14, y0 + 78), "OVR", fill=(150, 160, 175, 255), font=font_sub)

    pos = str(card.get("position") or "???")
    draw.text((x0 + 90, y0 + 52), pos, fill=border, font=font_name)

    name = str(card.get("name") or "Unknown")
    if len(name) > 16:
        name = name[:14] + ".."
    draw.text((x0 + 14, y0 + 110), name, fill=(255, 255, 255, 255), font=font_name)

    attrs = []
    for key in _ATTR_KEYS:
        if key in card and card[key] is not None:
            attrs.append(f"{key.upper()} {int(card[key])}")
    if attrs:
        line1 = "  ".join(attrs[:3])
        line2 = "  ".join(attrs[3:6])
        draw.text((x0 + 14, y0 + 150), line1, fill=(180, 190, 205, 255), font=font_sub)
        if line2:
            draw.text((x0 + 14, y0 + 172), line2, fill=(180, 190, 205, 255), font=font_sub)


def _render_swap_compare(
    out_card: dict[str, Any] | None,
    in_card: dict[str, Any] | None,
    font_bold_path: str,
    font_reg_path: str,
) -> discord.File:
    width, height = 640, 280
    img = Image.new("RGBA", (width, height), (18, 22, 28, 255))
    draw = ImageDraw.Draw(img)
    font_title, font_ovr, font_name, font_sub = _load_fonts(font_bold_path, font_reg_path)

    gap = 20
    panel_w = (width - gap * 3) // 2
    y0, y1 = 20, height - 20
    left = (gap, y0, gap + panel_w, y1)
    right = (gap * 2 + panel_w, y0, gap * 2 + panel_w * 2, y1)

    _draw_panel(
        draw,
        x0=left[0],
        y0=left[1],
        x1=left[2],
        y1=left[3],
        title="OUT",
        card=out_card,
        placeholder="Select starter…",
        font_title=font_title,
        font_ovr=font_ovr,
        font_name=font_name,
        font_sub=font_sub,
    )
    _draw_panel(
        draw,
        x0=right[0],
        y0=right[1],
        x1=right[2],
        y1=right[3],
        title="IN",
        card=in_card,
        placeholder="Select reserve…",
        font_title=font_title,
        font_ovr=font_ovr,
        font_name=font_name,
        font_sub=font_sub,
    )

    output = io.BytesIO()
    img.convert("RGB").save(output, format="PNG")
    output.seek(0)
    return discord.File(fp=output, filename="swap_compare.png")
