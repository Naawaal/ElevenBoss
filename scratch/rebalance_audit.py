from __future__ import annotations

import json
import time
from dataclasses import asdict, is_dataclass


LOG_PATH = "debug-465916.log"
SESSION_ID = "465916"


def _now_ms() -> int:
    return int(time.time() * 1000)


def _to_jsonable(x):
    if is_dataclass(x):
        return asdict(x)
    if isinstance(x, (str, int, float, bool)) or x is None:
        return x
    if isinstance(x, dict):
        return {str(k): _to_jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_to_jsonable(v) for v in x]
    return str(x)


def log(hypothesis_id: str, location: str, message: str, data: dict, *, run_id: str = "baseline") -> None:
    payload = {
        "sessionId": SESSION_ID,
        "runId": run_id,
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": _to_jsonable(data),
        "timestamp": _now_ms(),
    }
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload) + "\n")
    except Exception:
        pass


def main() -> None:
    # Hypotheses (baseline measurement):
    # A: drills feel bad because drill XP is low vs early XP-per-level and further reduced by diminishing returns.
    # B: bot battle energy feels punishing because 20 energy at 1 per 6 min implies long downtime per battle.
    # C: relative rewards are off: bot match XP per energy is not materially better than drills (or is too variable).
    # D: cooldown walls: evolution start is hard-coded 10h, independent of config.
    # E: there are UX/config mismatches (hardcoded UI text / python defaults diverge from game_config seeds).

    from player_engine.progression import (
        xp_needed_for_level,
        drill_xp_reward,
        match_xp_reward,
        fusion_xp_reward,
    )
    from economy.flows import EconomyConfig, DEFAULTS as ECON_DEFAULTS

    eco = EconomyConfig()
    # game_config seed (028_economy_foundation.sql): energy_regen_per_min = 0.1666667 (~1 per 6 min)
    regen_per_min = 1.0 / 6.0
    minutes_per_energy = 1.0 / regen_per_min if regen_per_min > 0 else None

    log(
        "B",
        "scratch/rebalance_audit.py:main",
        "energy baseline (python-side constants + defaults)",
        {
            "energy_max_default": 100,
            "regen_per_min_python": regen_per_min,
            "minutes_per_energy_python": minutes_per_energy,
            "match_energy_bot_python": ECON_DEFAULTS.get("match_energy_bot"),
            "match_energy_friendly_python": ECON_DEFAULTS.get("match_energy_friendly"),
            "match_energy_league_python": ECON_DEFAULTS.get("match_energy_league"),
            "eco_defaults_match_energy_bot": getattr(eco, "match_energy_bot", None),
            "eco_defaults_match_energy_friendly": getattr(eco, "match_energy_friendly", None),
            "eco_defaults_match_energy_league": getattr(eco, "match_energy_league", None),
            "econ_defaults_dict_match_energy_bot": ECON_DEFAULTS.get("match_energy_bot"),
            "econ_defaults_dict_match_energy_friendly": ECON_DEFAULTS.get("match_energy_friendly"),
            "econ_defaults_dict_match_energy_league": ECON_DEFAULTS.get("match_energy_league"),
        },
    )

    levels = [1, 10, 25]
    xp_needed = {lvl: xp_needed_for_level(lvl) for lvl in levels}
    log(
        "A",
        "scratch/rebalance_audit.py:main",
        "xp curve snapshot",
        {"xp_needed_for_level": xp_needed},
    )

    # Drill XP snapshots. game_config seeds: basic=30, advanced=80; diminishing returns formula is in player_engine.
    drill_tiers = {"basic": 30, "advanced": 80}
    drill_xp = {
        tier: {lvl: drill_xp_reward(base, lvl, age=None, training_ground_level=1) for lvl in levels}
        for tier, base in drill_tiers.items()
    }
    log(
        "A",
        "scratch/rebalance_audit.py:main",
        "drill xp snapshot (base=30/80, TG=1, no age mult)",
        {"drill_xp": drill_xp},
    )

    # Match XP range snapshots (90 minutes, varying rating) with caps + bonuses.
    # Keep it simple: no goals/assists/MOTM, just ratings and result bonus; then add one "good performance" case.
    ratings = [5.5, 6.0, 7.0, 8.0]
    match_types = ["bot", "league"]
    results = ["loss", "draw", "win"]

    match_xp = {}
    for mt in match_types:
        match_xp[mt] = {}
        for res in results:
            match_xp[mt][res] = {
                str(r): match_xp_reward(
                    minutes_played=90,
                    match_rating=r,
                    match_type=mt,
                    goals=0,
                    assists=0,
                    motm=False,
                    result=res,
                    age=None,
                )
                for r in ratings
            }

    good_game = match_xp_reward(
        minutes_played=90,
        match_rating=8.0,
        match_type="bot",
        goals=1,
        assists=1,
        motm=True,
        result="win",
        age=None,
    )

    log(
        "C",
        "scratch/rebalance_audit.py:main",
        "match xp snapshot (90m, no age mult)",
        {"match_xp": match_xp, "example_good_game_bot": good_game},
    )

    # Fusion example: fodder L10, OVR 60 (common mid-game).
    fusion_example = fusion_xp_reward(10, 60)
    log(
        "C",
        "scratch/rebalance_audit.py:main",
        "fusion xp snapshot",
        {"fusion_example_xp": fusion_example, "formula_inputs": {"sacrifice_level": 10, "sacrifice_ovr": 60}},
    )

    # Cooldown wall snapshot (hard-coded in SQL migration 028; not config-driven currently).
    log(
        "D",
        "scratch/rebalance_audit.py:main",
        "cooldown/cap snapshot (from repo audit)",
        {
            "evolution_start_cooldown_hours_sql": 10,
            "max_active_evolutions_sql": 3,
            "fusion_daily_limit_sql": 3,
            "drills_daily_limit_club_sql": 20,
            "drills_daily_limit_per_player_sql": 5,
            "match_xp_daily_cap_per_player_sql": 100,
        },
    )

    # Derived: time-to-afford energy for a typical session.
    if minutes_per_energy is not None:
        time_to_20_energy = 20 * minutes_per_energy
        time_to_15_energy = 15 * minutes_per_energy
        time_to_10_energy = 10 * minutes_per_energy
    else:
        time_to_20_energy = time_to_15_energy = time_to_10_energy = None

    log(
        "B",
        "scratch/rebalance_audit.py:main",
        "derived downtime at current regen",
        {
            "minutes_to_regen_10_energy": time_to_10_energy,
            "minutes_to_regen_15_energy": time_to_15_energy,
            "minutes_to_regen_20_energy": time_to_20_energy,
        },
    )

    print("Wrote baseline audit to", LOG_PATH)


if __name__ == "__main__":
    main()

