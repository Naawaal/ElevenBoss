# packages/match_engine/match_engine/v3/decisions.py
"""DecisionInbox — validate → collapse → apply (immediate or DecisionWindows)."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

DECISION_WINDOWS = (15, 30, 45, 60, 75, 85)


class DecisionIntent(BaseModel):
    side: Literal["home", "away"] = "home"
    kind: str = "set_tactic"  # set_tactic | sub_resolution | play_on
    payload: dict[str, Any] = Field(default_factory=dict)
    requested_at_minute: int = 0
    source: Literal["human", "ai", "auto"] = "human"


def windows_crossed(prev_minute: int, minute: int) -> tuple[int, ...]:
    """Windows W where prev < W <= minute (handles clock jumps)."""
    return tuple(w for w in DECISION_WINDOWS if prev_minute < w <= minute)


class DecisionInbox:
    """
    Live: at most one pending tactic intent per side (collapse spam).
    Recovery: optional ordered schedule applied when minute reaches apply point.
    """

    def __init__(self) -> None:
        self._pending: dict[str, DecisionIntent] = {}
        self._scheduled: list[DecisionIntent] = []

    def push(self, intent: DecisionIntent) -> None:
        if intent.kind == "set_tactic":
            self._pending[intent.side] = intent
        else:
            key = f"{intent.side}:{intent.kind}"
            self._pending[key] = intent

    def schedule(self, intents: list[DecisionIntent]) -> None:
        self._scheduled = sorted(
            list(intents),
            key=lambda i: (int(i.requested_at_minute), i.kind, i.side),
        )

    def pop_ready(
        self,
        *,
        minute: int,
        enforce_windows: bool = False,
        terminal: bool = False,
        prev_minute: int | None = None,
    ) -> list[DecisionIntent]:
        """
        Phase 0 / schema 1: enforce_windows=False → apply when minute >= requested.
        Wave 1 / schema 2+: enforce_windows=True → apply at DecisionWindows
        (including when the clock jumps across a window).
        """
        if terminal:
            self._pending.clear()
            self._scheduled.clear()
            return []

        if enforce_windows:
            prev = prev_minute if prev_minute is not None else minute
            crossed = windows_crossed(prev, minute)
            on_window = minute in DECISION_WINDOWS or bool(crossed)
            if not on_window and minute < 90:
                return []

        out: list[DecisionIntent] = []
        remain: list[DecisionIntent] = []
        for intent in self._scheduled:
            if intent.requested_at_minute <= minute:
                out.append(intent)
            else:
                remain.append(intent)
        self._scheduled = remain

        if self._pending:
            for intent in list(self._pending.values()):
                if intent.requested_at_minute <= minute:
                    out.append(intent)
            self._pending.clear()

        return out

    def peek(self) -> list[DecisionIntent]:
        return list(self._pending.values()) + list(self._scheduled)

    def nearest_window(self, minute: int) -> int | None:
        for w in DECISION_WINDOWS:
            if w >= minute:
                return w
        return None


def stance_modifier_for_tactic(tactic: str) -> float:
    t = (tactic or "balanced").lower()
    if t in ("attack", "attacking"):
        return 1.3
    if t in ("defend", "defending"):
        return 0.7
    if t == "high_press":
        return 1.15
    return 1.0


def apply_intent_to_modifiers(
    intent: DecisionIntent,
) -> tuple[str, float]:
    if intent.kind != "set_tactic":
        return "balanced", 1.0
    name = str(intent.payload.get("tactic") or intent.payload.get("style") or "balanced")
    return name, stance_modifier_for_tactic(name)


def intents_from_decision_events(rows: list[dict[str, Any]]) -> list[DecisionIntent]:
    out: list[DecisionIntent] = []
    for row in rows:
        et = str(row.get("event_type") or row.get("type") or "")
        if et != "TACTICAL_DECISION":
            continue
        payload = row.get("payload") or {}
        if isinstance(payload, str):
            continue
        side = row.get("side") or payload.get("side") or "home"
        if side not in ("home", "away"):
            side = "home"
        # Replay at the minute the decision was applied (durable event minute)
        apply_min = int(row.get("minute") or payload.get("requested_at_minute") or 0)
        out.append(
            DecisionIntent(
                side=side,  # type: ignore[arg-type]
                kind="set_tactic",
                payload={
                    "tactic": payload.get("tactic") or payload.get("style") or "balanced",
                    "stance_modifier": payload.get("stance_modifier"),
                },
                requested_at_minute=apply_min,
                source=(
                    "ai"
                    if payload.get("source") == "ai"
                    else ("auto" if payload.get("source") == "auto" else "human")
                ),
            )
        )
    return out
