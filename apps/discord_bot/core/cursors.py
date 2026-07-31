# apps/discord_bot/core/cursors.py
"""Opaque keyset cursor encode/decode (050 contracts/cursor-pagination.md)."""
from __future__ import annotations

import base64
import json
from typing import Any


def encode_cursor(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_cursor(token: str | None) -> dict[str, Any] | None:
    if not token:
        return None
    pad = "=" * (-len(token) % 4)
    try:
        raw = base64.urlsafe_b64decode(token + pad)
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def division_cursor(
    *, league_points: int, goal_difference: int, discord_id: int
) -> str:
    return encode_cursor(
        {
            "k": "div",
            "lp": int(league_points),
            "gd": int(goal_difference),
            "id": int(discord_id),
        }
    )


def global_lp_cursor(*, global_lp: int, discord_id: int) -> str:
    return encode_cursor({"k": "glp", "lp": int(global_lp), "id": int(discord_id)})


def market_cursor(
    *, sort_mode: str, created_at: str | None = None, price_coins: int | None = None, id: str
) -> str:
    payload: dict[str, Any] = {"k": "mkt", "s": sort_mode, "id": str(id)}
    if created_at is not None:
        payload["ca"] = created_at
    if price_coins is not None:
        payload["pc"] = int(price_coins)
    return encode_cursor(payload)
