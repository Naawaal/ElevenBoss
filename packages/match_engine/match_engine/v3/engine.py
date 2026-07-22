# packages/match_engine/match_engine/v3/engine.py
"""SimulationEngine — step / run_to_completion wrapping NSS sporting loop."""
from __future__ import annotations

import random
from typing import Any, Iterator

from match_engine.models import MatchPlayerCard
from match_engine.v2_simulator import MatchState, generate_match_events

from .brain import BotBrain
from .context import DecisionContext, MatchContext, ReplayMeta, StepResult
from .decisions import DecisionInbox, DecisionIntent, apply_intent_to_modifiers
from .digests import deterministic_replay_digest, sporting_digest
from .events import EventCategory, MatchEventV3, from_compat_dict
from .possession import PossessionTracker
from .projectors import project_box_score
from .rng import make_match_rng
from .tactics import apply_profile_to_state, get_transition_profile, phase0_stance_modifier


ENGINE_VERSION = "nss_v3"
# 1 = Phase 0 immediate decisions; 2 = Wave 1 DecisionWindows (+ Wave 2 profiles available)
SIMULATION_SCHEMA_VERSION = 2


class SimulationEngine:
    def __init__(
        self,
        *,
        engine_version: str = ENGINE_VERSION,
        simulation_schema_version: int = SIMULATION_SCHEMA_VERSION,
        brain: BotBrain | None = None,
        enforce_decision_windows: bool | None = None,
    ) -> None:
        self.engine_version = engine_version
        self.simulation_schema_version = simulation_schema_version
        self.brain = brain or BotBrain()
        if enforce_decision_windows is None:
            enforce_decision_windows = simulation_schema_version >= 2
        self.enforce_decision_windows = enforce_decision_windows
        self._gen: Iterator[dict[str, Any]] | None = None
        self._state: MatchState | None = None
        self._inbox = DecisionInbox()
        self._events: list[MatchEventV3] = []
        self._seq = 0
        self._possession = PossessionTracker()
        self._home_name = "Home"
        self._away_name = "Away"
        self._rng: random.Random | None = None
        self._prev_minute = 0

    def initial_context(
        self,
        *,
        home: list[MatchPlayerCard],
        away: list[MatchPlayerCard],
        home_name: str,
        away_name: str,
        home_rating: float,
        away_rating: float,
        seed: int,
        tactics_home: str = "balanced",
        tactics_away: str = "balanced",
        intensity_tier: int = 1,
        injuries_enabled: bool = False,
        interactive_sides: list[str] | None = None,
        bench_home: list | None = None,
        bench_away: list | None = None,
    ) -> MatchContext:
        self._home_name = home_name
        self._away_name = away_name
        self._rng = make_match_rng(seed)
        self._seq = 0
        self._events = []
        self._possession = PossessionTracker()
        self._inbox = DecisionInbox()
        self._prev_minute = 0
        state = MatchState(
            home_rating=home_rating,
            away_rating=away_rating,
            injuries_enabled=injuries_enabled,
            interactive_sides=list(interactive_sides or []),
            intensity_tier=intensity_tier,
            bench_home=list(bench_home or []),
            bench_away=list(bench_away or []),
        )
        home_prof = get_transition_profile(tactics_home)
        apply_profile_to_state(state, home_prof)
        self._state = state
        self._gen = generate_match_events(
            state, list(home), list(away), home_name, away_name, rng=self._rng
        )
        return MatchContext(
            home_rating=home_rating,
            away_rating=away_rating,
            home_name=home_name,
            away_name=away_name,
            home_squad=list(home),
            away_squad=list(away),
            bench_home=list(bench_home or []),
            bench_away=list(bench_away or []),
            tactic_home=tactics_home,
            tactic_away=tactics_away,
            stance_modifier_home=state.home_tactics_modifier,
            stance_modifier_away=phase0_stance_modifier(tactics_away),
            intensity_tier=intensity_tier,
            injuries_enabled=injuries_enabled,
            interactive_sides=list(interactive_sides or []),
            engine_version=self.engine_version,
            simulation_schema_version=self.simulation_schema_version,
        )

    def push_decision(self, intent: DecisionIntent) -> None:
        self._inbox.push(intent)

    def step(
        self,
        context: MatchContext,
        inbox: DecisionInbox | None = None,
    ) -> StepResult:
        if self._state is None or self._gen is None:
            raise RuntimeError("Call initial_context before step")

        box = inbox or self._inbox
        decision_events: list[MatchEventV3] = []

        def _apply_ready(*, minute: int, prev_minute: int) -> None:
            nonlocal context, decision_events
            for intent in box.pop_ready(
                minute=minute,
                enforce_windows=self.enforce_decision_windows,
                terminal=context.terminal,
                prev_minute=prev_minute,
            ):
                if intent.kind != "set_tactic":
                    continue
                name, mod = apply_intent_to_modifiers(intent)
                if intent.side == "home":
                    prof = get_transition_profile(name)
                    apply_profile_to_state(self._state, prof)
                    # Intent stance wins when payload/alias differs from profile default
                    self._state.home_tactics_modifier = mod
                    context = context.model_copy(
                        update={
                            "tactic_home": name,
                            "stance_modifier_home": self._state.home_tactics_modifier,
                        }
                    )
                    team = self._home_name
                    stance = self._state.home_tactics_modifier
                else:
                    context = context.model_copy(
                        update={"tactic_away": name, "stance_modifier_away": mod}
                    )
                    team = self._away_name
                    stance = mod
                self._seq += 1
                ev_d = MatchEventV3(
                    seq=self._seq,
                    minute=minute,
                    type="TACTICAL_DECISION",
                    category=EventCategory.DECISION,
                    side=intent.side,
                    payload={
                        "tactic": name,
                        "stance_modifier": stance,
                        "source": intent.source,
                        "requested_at_minute": intent.requested_at_minute,
                        "window_minute": box.nearest_window(minute),
                        "applied_immediate": not self.enforce_decision_windows,
                        "score_update": f"{self._state.home_score} - {self._state.away_score}",
                        "actor": "Manager",
                        "team": team,
                    },
                )
                self._events.append(ev_d)
                decision_events.append(ev_d)

        # Phase 0 immediate: apply at current minute before sporting tick
        if not self.enforce_decision_windows:
            _apply_ready(minute=context.minute, prev_minute=self._prev_minute)

        dctx = DecisionContext(
            minute=context.minute,
            home_score=self._state.home_score,
            away_score=self._state.away_score,
            own_tactic=context.tactic_away,
            opponent_tactic=context.tactic_home,
            intensity_tier=context.intensity_tier,
            trailing=self._state.away_score < self._state.home_score,
        )
        ai_intent = self.brain.propose(dctx)
        if ai_intent is not None:
            box.push(ai_intent)
            if not self.enforce_decision_windows:
                _apply_ready(minute=context.minute, prev_minute=self._prev_minute)

        possession_ended = False
        try:
            raw = next(self._gen)
        except StopIteration:
            ctx = context.model_copy(
                update={
                    "minute": 90,
                    "home_score": self._state.home_score,
                    "away_score": self._state.away_score,
                    "terminal": True,
                }
            )
            return StepResult(
                events=list(decision_events),
                context=ctx,
                terminal=True,
                replay_meta=ReplayMeta(
                    engine_version=self.engine_version,
                    simulation_schema_version=self.simulation_schema_version,
                    seq_start=self._seq,
                    seq_end=self._seq,
                ),
            )

        prev_min = self._prev_minute
        # Wave 1: apply when clock crosses a DecisionWindow on this tick
        if self.enforce_decision_windows:
            _apply_ready(minute=int(raw.get("minute") or 0), prev_minute=prev_min)

        self._seq += 1
        ev = from_compat_dict(
            raw, seq=self._seq, engine_version=self.engine_version
        )

        if ev.type in ("CHANCE", "GOAL", "MISS", "SAVE", "FOUL"):
            team = str(ev.payload.get("team") or "")
            owner = "home" if team == self._home_name else "away"
            if self._possession.current is None:
                self._possession.start(owner, ev.minute, self._seq)
            elif self._possession.current.owner != owner:
                self._possession.end(ev.minute, "turnover", self._seq)
                possession_ended = True
                self._possession.start(owner, ev.minute, self._seq)
        if ev.type in ("HALF_TIME", "FULL_TIME"):
            if self._possession.current is not None:
                self._possession.end(ev.minute, ev.type.lower(), self._seq)
                possession_ended = True

        self._events.append(ev)
        elapsed = max(0, ev.minute - prev_min)
        self._prev_minute = ev.minute

        awaiting = bool(raw.get("interactive")) and raw.get("type") == "INJURY"
        new_ctx = context.model_copy(
            update={
                "minute": ev.minute,
                "home_score": self._state.home_score,
                "away_score": self._state.away_score,
                "stance_modifier_home": self._state.home_tactics_modifier,
                "possession": self._possession.current,
                "next_seq": self._seq + 1,
                "awaiting_decision": awaiting,
                "awaiting_reason": "injury" if awaiting else None,
                "terminal": ev.type == "FULL_TIME",
                "momentum_home": float(getattr(self._state, "momentum", 0)) / 10.0,
            }
        )
        return StepResult(
            events=list(decision_events) + [ev],
            context=new_ctx,
            elapsed_minutes=elapsed,
            terminal=ev.type == "FULL_TIME",
            awaiting_decision=awaiting,
            legal_actions=list(raw.get("options") or []),
            possession_ended=possession_ended,
            replay_meta=ReplayMeta(
                engine_version=self.engine_version,
                simulation_schema_version=self.simulation_schema_version,
                seq_start=decision_events[0].seq if decision_events else ev.seq,
                seq_end=ev.seq,
            ),
        )

    def run_to_completion(
        self,
        context: MatchContext,
        *,
        decisions: list[DecisionIntent] | None = None,
        auto_resolve_injuries: bool = True,
    ) -> tuple[MatchContext, list[MatchEventV3]]:
        if decisions:
            # Recovery: schedule by requested minute (schema-pinned apply)
            self._inbox.schedule(list(decisions))
        # Silent: clear interactive so generate_match_events auto-resolves
        if auto_resolve_injuries and self._state is not None:
            self._state.interactive_sides = []

        ctx = context
        while not ctx.terminal:
            result = self.step(ctx, self._inbox)
            ctx = result.context
            if result.terminal:
                break
            if not result.events and result.terminal:
                break
        return ctx, list(self._events)

    def digests(self) -> dict[str, str]:
        hs = self._state.home_score if self._state else 0
        aws = self._state.away_score if self._state else 0
        return {
            "sporting": sporting_digest(self._events, home_score=hs, away_score=aws),
            "replay": deterministic_replay_digest(self._events),
        }

    def all_events(self) -> list[MatchEventV3]:
        return list(self._events)

    def box_score(self) -> Any:
        return project_box_score(self._events, home_name=self._home_name)
