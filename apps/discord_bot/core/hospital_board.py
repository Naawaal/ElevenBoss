# apps/discord_bot/core/hospital_board.py
"""Hospital admitted-patient board overlay on assets/admited.png."""
from __future__ import annotations

import asyncio
import io
import logging
from typing import Any

import discord
from PIL import Image, ImageDraw, ImageFont

from apps.discord_bot.core.pitch_generator import _ASSETS_DIR, _RENDER_SEM
from player_engine import TIER_NAMES

logger = logging.getLogger(__name__)

HOSPITAL_VISUAL_SLOTS = 6
# Row text baselines as fraction of image height (admited.png lined content area).
_ROW_Y_FRAC = (0.30, 0.40, 0.50, 0.60, 0.70, 0.80)
_ROW_X_FRAC = 0.16


def patient_overlay_rows(
    patients: list[dict[str, Any]],
    *,
    max_slots: int = HOSPITAL_VISUAL_SLOTS,
) -> list[dict[str, Any]]:
    """First max_slots admitted patients normalized for overlay (overflow excluded)."""
    rows: list[dict[str, Any]] = []
    for p in patients[: max(0, int(max_slots))]:
        nested = p.get("player_cards")
        card = nested if isinstance(nested, dict) else p
        name = str((card or {}).get("name") or p.get("name") or "Player")
        tier = p.get("injury_tier")
        if tier is None and isinstance(card, dict):
            tier = card.get("injury_tier")
        rows.append({"name": name, "injury_tier": tier})
    return rows


async def generate_hospital_board(patients: list[dict[str, Any]]) -> discord.File | None:
    """Render admitted names onto the hospital clipboard asset, or None if asset missing."""
    asset_path = _ASSETS_DIR / "admited.png"
    font_bold = _ASSETS_DIR / "fonts" / "Roboto-Bold.ttf"
    font_reg = _ASSETS_DIR / "fonts" / "Roboto-Regular.ttf"
    if not asset_path.is_file():
        # ponytail: missing asset → text-only hospital panel (FR-014); no raise on hub open
        return None
    rows = patient_overlay_rows(patients)
    async with _RENDER_SEM:
        return await asyncio.to_thread(
            _render_hospital_board,
            str(asset_path),
            rows,
            str(font_bold),
            str(font_reg),
        )


def _render_hospital_board(
    asset_path: str,
    rows: list[dict[str, Any]],
    font_bold_path: str,
    font_reg_path: str,
) -> discord.File | None:
    try:
        img = Image.open(asset_path).convert("RGBA")
    except OSError:
        logger.warning("Hospital board asset unreadable: %s", asset_path)
        return None

    draw = ImageDraw.Draw(img)
    width, height = img.size
    try:
        font = ImageFont.truetype(font_bold_path, max(18, height // 36))
        font_sub = ImageFont.truetype(font_reg_path, max(14, height // 48))
    except OSError:
        font = ImageFont.load_default()
        font_sub = font

    x = int(width * _ROW_X_FRAC)
    for idx, row in enumerate(rows[:HOSPITAL_VISUAL_SLOTS]):
        y = int(height * _ROW_Y_FRAC[idx])
        name = str(row.get("name") or "Player")
        if len(name) > 28:
            name = name[:26] + ".."
        draw.text((x, y), name, fill=(30, 40, 50, 255), font=font)
        tier = row.get("injury_tier")
        if tier is not None:
            try:
                label = TIER_NAMES.get(int(tier), "Injured")
            except (TypeError, ValueError):
                label = "Injured"
            draw.text((x, y + max(20, height // 40)), label, fill=(80, 100, 110, 255), font=font_sub)

    output = io.BytesIO()
    img.convert("RGB").save(output, format="PNG")
    output.seek(0)
    return discord.File(fp=output, filename="hospital_board.png")
