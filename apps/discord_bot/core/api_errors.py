# apps/discord_bot/core/api_errors.py
from __future__ import annotations

import ast

from postgrest.exceptions import APIError

_FRIENDLY: dict[str, str] = {
    "Insufficient action energy": (
        "Not enough **action energy**. Regenerates +1 every 4 minutes, or buy a refill in `/store`."
    ),
    "Daily drill limit reached": "You've hit today's **club drill limit** (20). Try again tomorrow.",
    "Daily drill limit reached for this player": (
        "This player has hit today's **per-card drill limit** (5). Pick another card or try tomorrow."
    ),
    "Insufficient coins": "Not enough **coins** for this drill. Play matches or claim daily login in `/store`.",
    "Match XP could not be applied": (
        "Match finished, but **player XP could not be saved**. Coins may already be credited — "
        "try again later or contact an admin if this keeps happening."
    ),
    "Insufficient skill points": "Not enough **skill points** for that mentor transfer (need 5 SP per mentor unit).",
    "Source card has not reached potential ceiling": (
        "Only **potential-maxed** cards can mentor. Keep allocating or pick a maxed legend."
    ),
    "Target card is already maxed": "That player is already at their **potential ceiling** — pick a developing card.",
    "Target cannot receive more XP": "That player is already at **max level** and cannot absorb mentor XP.",
    "Target cannot absorb mentor XP": (
        "That amount would **waste XP** near the level cap. Choose fewer mentor units or another target."
    ),
    "Daily mentor transfer limit (3) reached": (
        "You've used all **3 mentor transfers** for today (UTC). Try again tomorrow."
    ),
    "Source card not found or not owned": "Source card not found on your club.",
    "Target card not found or not owned": "Target card not found on your club.",
    "Source and target must differ": "Pick a **different** player as the mentor target.",
    "Invalid mentor unit amount": "Choose at least **1 mentor unit**.",
    "Player is already fully rested": (
        "That player is already at **full fitness**. Pick someone tired, or wait for match drain."
    ),
    "Player is injured — use Hospital": (
        "That player is **injured** — treat them in **Hospital** via `/profile` → **Manage Hospital**, "
        "not Recovery Session."
    ),
}


def _extract_message(exc: Exception) -> str:
    if isinstance(exc, APIError):
        msg = getattr(exc, "message", None)
        if msg:
            return str(msg)
        if exc.args:
            payload = exc.args[0]
            if isinstance(payload, dict):
                return str(payload.get("message", exc))
            if isinstance(payload, str):
                text = payload.strip()
                if text.startswith("{"):
                    try:
                        parsed = ast.literal_eval(text)
                        if isinstance(parsed, dict) and parsed.get("message"):
                            return str(parsed["message"])
                    except (ValueError, SyntaxError):
                        pass
                return text
    return str(exc)


def api_error_message(exc: Exception) -> str:
    """Turn postgrest/Supabase errors into player-facing copy."""
    raw = _extract_message(exc)
    if raw in _FRIENDLY:
        return _FRIENDLY[raw]
    # Chained XP failures (RuntimeError from apply_match_xp_if_needed)
    if "Match XP could not be applied" in raw:
        return _FRIENDLY["Match XP could not be applied"]
    if "permission denied" in raw.lower() and "player_xp_log" in raw.lower():
        return _FRIENDLY["Match XP could not be applied"]
    # Longest key first so per-card drill limit is not mapped as club limit.
    for key, friendly in sorted(_FRIENDLY.items(), key=lambda kv: len(kv[0]), reverse=True):
        if key in raw:
            return friendly
    return raw
