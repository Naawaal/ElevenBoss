# tests/test_nss_engine.py
"""
Debug trace harness for the NSS Match Engine (Markov Chain State Machine).

Constructs two mock squads, runs stream_match() to completion, and prints a
full console trace of every state transition and yielded event.

Validates:
    - All events have required keys (minute, type, score_update, actor, team)
    - Event types are valid EventType values
    - Minutes are monotonically non-decreasing
    - Final event is FULL_TIME at minute 90
    - GOAL events may have an "assister" key
    - No crashes or infinite loops
"""
from __future__ import annotations

import asyncio
import sys
import os

# Windows console encoding fix for emoji output
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure the packages directory is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "match_engine"))

from match_engine.models import MatchPlayerCard, EventType
from match_engine.v2_simulator import MatchState, stream_match
from match_engine.commentary_engine import CommentaryEngine


# ── Valid event types ────────────────────────────────────────────────────────
VALID_EVENT_TYPES = {e.value for e in EventType}
REQUIRED_KEYS = {"minute", "type", "score_update", "actor", "team"}


def build_mock_squad(team_base_rating: int, prefix: str) -> list[MatchPlayerCard]:
    """Build a mock 11-player squad with positional variety."""
    positions = [
        ("GK", f"{prefix} Keeper"),
        ("DEF", f"{prefix} CB1"),
        ("DEF", f"{prefix} CB2"),
        ("DEF", f"{prefix} LB"),
        ("DEF", f"{prefix} RB"),
        ("MID", f"{prefix} CM1"),
        ("MID", f"{prefix} CM2"),
        ("MID", f"{prefix} CAM"),
        ("FWD", f"{prefix} LW"),
        ("FWD", f"{prefix} RW"),
        ("FWD", f"{prefix} ST"),
    ]
    return [
        MatchPlayerCard(
            name=name,
            position=pos,
            overall=team_base_rating + (i % 5 - 2),  # slight variation
        )
        for i, (pos, name) in enumerate(positions)
    ]


async def run_trace() -> None:
    """Run a full match and print the debug trace."""

    # Build squads
    home_squad = build_mock_squad(78, "Eagle")
    away_squad = build_mock_squad(75, "Hawk")

    home_name = "Eagle United"
    away_name = "Hawk Athletic"

    # Init state
    home_rating = sum(p.overall for p in home_squad) / len(home_squad)
    away_rating = sum(p.overall for p in away_squad) / len(away_squad)
    state = MatchState(home_rating=home_rating, away_rating=away_rating)

    # Init commentary engine
    commentary = CommentaryEngine()

    print("=" * 80)
    print(f"  NSS MATCH ENGINE — DEBUG TRACE")
    print(f"  {home_name} (avg {home_rating:.1f}) vs {away_name} (avg {away_rating:.1f})")
    print("=" * 80)
    print()

    events_collected: list[dict] = []
    last_minute = -1
    errors: list[str] = []

    async for ev in stream_match(state, home_squad, away_squad, home_name, away_name):
        events_collected.append(ev)

        # ── Validation ──────────────────────────────────────────────────
        missing = REQUIRED_KEYS - set(ev.keys())
        if missing:
            errors.append(f"  [ERROR] Event at minute {ev.get('minute', '?')} missing keys: {missing}")

        if ev.get("type") not in VALID_EVENT_TYPES:
            errors.append(f"  [ERROR] Invalid event type '{ev.get('type')}' at minute {ev.get('minute', '?')}")

        minute = ev.get("minute", 0)
        if minute < last_minute:
            errors.append(f"  [ERROR] Non-monotonic minute: {minute} < {last_minute}")
        last_minute = minute

        # ── Commentary ──────────────────────────────────────────────────
        variables = {"actor": ev.get("actor", ""), "team": ev.get("team", "")}
        comm = commentary.get_commentary(ev["type"], state.context_tags, variables)

        # ── Pretty print ────────────────────────────────────────────────
        emoji_map = {
            "KICKOFF": "🟢", "GOAL": "⚽", "MISS": "❌", "SAVE": "🧤",
            "CHANCE": "🎯", "FOUL": "💥", "YELLOW_CARD": "🟨",
            "INJURY": "🩹", "FULL_TIME": "🏁",
        }
        emo = emoji_map.get(ev["type"], "⏱️")
        assist_str = f" (assist: {ev['assister']})" if "assister" in ev else ""
        urgency_tag = f" [{comm['urgency'].upper()}]" if comm["urgency"] != "routine" else ""

        print(f"  {emo} {ev['minute']:>3}' [{ev['type']:<12}] {ev['score_update']:<7} "
              f"| {ev['actor']:<25} ({ev['team']}){assist_str}{urgency_tag}")
        print(f"       💬 {comm['text']}")
        print()

    # ── Final Validation ────────────────────────────────────────────────
    print("=" * 80)
    print("  POST-MATCH VALIDATION")
    print("=" * 80)

    if events_collected:
        last_ev = events_collected[-1]
        if last_ev.get("type") != "FULL_TIME":
            errors.append(f"  [ERROR] Last event is not FULL_TIME: {last_ev.get('type')}")
        if last_ev.get("minute") != 90:
            errors.append(f"  [ERROR] Last event minute is not 90: {last_ev.get('minute')}")
    else:
        errors.append("  [ERROR] No events were generated!")

    # Count stats
    goals = [e for e in events_collected if e.get("type") == "GOAL"]
    saves = [e for e in events_collected if e.get("type") == "SAVE"]
    chances = [e for e in events_collected if e.get("type") == "CHANCE"]
    fouls = [e for e in events_collected if e.get("type") == "FOUL"]
    cards = [e for e in events_collected if e.get("type") == "YELLOW_CARD"]
    misses = [e for e in events_collected if e.get("type") == "MISS"]
    injuries = [e for e in events_collected if e.get("type") == "INJURY"]

    print(f"  Total events:     {len(events_collected)}")
    print(f"  ⚽ Goals:          {len(goals)}")
    print(f"  🧤 Saves:          {len(saves)}")
    print(f"  🎯 Chances:        {len(chances)}")
    print(f"  ❌ Misses:         {len(misses)}")
    print(f"  💥 Fouls:          {len(fouls)}")
    print(f"  🟨 Yellow Cards:   {len(cards)}")
    print(f"  🩹 Injuries:       {len(injuries)}")
    print(f"  Final Score:      {state.home_score} - {state.away_score}")
    print(f"  Final Momentum:   {state.momentum}")
    print(f"  Context Tags:     {state.context_tags}")
    print()

    if errors:
        print("  ❌ VALIDATION ERRORS:")
        for e in errors:
            print(f"    {e}")
    else:
        print("  ✅ ALL VALIDATIONS PASSED")

    print()
    print("=" * 80)

    # Return exit code
    return len(errors)


def main():
    exit_code = asyncio.run(run_trace())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
