# packages/match_engine/match_engine/calibration/dixon_coles_harness.py
"""
Offline Dixon-Coles calibration surface (FR-015 / R7).

Source of truth: `packages/match_engine/match_engine.py` (`simulate_match`).
That module is **not** on the live Discord / NSS v3 import path.

Usage (from repo root, offline only)::

    PYTHONPATH=packages/match_engine python -c "from match_engine import simulate_match"

Or compare NSS golden corpus::

    python -m match_engine.calibration.run_corpus
    python scripts/compare_v2_v3_seeds.py

Never import this from `apps/discord_bot/`.
"""
from __future__ import annotations

from typing import Any


def dixon_coles_module_path() -> str:
    from pathlib import Path

    return str(Path(__file__).resolve().parents[2] / "match_engine.py")


def run_dixon_coles_sample(**_kwargs: Any) -> dict[str, Any]:
    """
    Placeholder report — full interval sampling is via match_engine.py CLI/scripts.
    Keeps calibration package importable without fighting the dual package layout.
    """
    return {
        "engine": "dixon_coles_interval",
        "module_path": dixon_coles_module_path(),
        "status": "offline_only",
        "note": "Use packages/match_engine/match_engine.py simulate_match under PYTHONPATH=packages/match_engine",
    }


if __name__ == "__main__":
    print(run_dixon_coles_sample())
