# apps/discord_bot/core/debug_session_log.py
"""Debug-mode NDJSON logger (session 3124bd). Remove after verification."""
from __future__ import annotations

import json
import time
from pathlib import Path

_LOG = Path(__file__).resolve().parents[3] / "debug-3124bd.log"
_SESSION = "3124bd"


def debug_log(
    hypothesis_id: str,
    location: str,
    message: str,
    data: dict | None = None,
    *,
    run_id: str = "pre-fix",
) -> None:
    # #region agent log
    payload = {
        "sessionId": _SESSION,
        "runId": run_id,
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data or {},
        "timestamp": int(time.time() * 1000),
    }
    try:
        with open(_LOG, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload) + "\n")
    except OSError:
        pass
    # #endregion
