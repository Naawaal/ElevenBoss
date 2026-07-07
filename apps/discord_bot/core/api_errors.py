# apps/discord_bot/core/api_errors.py
from __future__ import annotations

import ast

from postgrest.exceptions import APIError

_FRIENDLY: dict[str, str] = {
    "Insufficient action energy": (
        "Not enough **action energy**. Regenerates +1 every 6 minutes, or buy a refill in `/store`."
    ),
    "Daily drill limit reached": "You've hit today's **club drill limit** (20). Try again tomorrow.",
    "Insufficient coins": "Not enough **coins** for this drill. Play matches or claim daily login in `/store`.",
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
    return _FRIENDLY.get(raw, raw)
