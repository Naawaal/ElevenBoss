# packages/match_engine/match_engine/v2_simulator.py
"""
NSS Match Engine — Highlight-Driven State Machine (Markov Chain)

Replaces the linear RNG generator with a discrete-phase Markov chain that
evaluates team strengths per-phase and yields visible events only when the
state machine enters a [VISIBLE] phase.

Thread Safety:
    Each MatchState owns its own random.Random() instance.  No global random
    state is ever touched.

Output Contract (backwards-compatible with battle_cog.py):
    Every yielded dict contains:
        minute:       int   (0-90)
        type:         str   (EventType value: KICKOFF, GOAL, MISS, SAVE, CHANCE, FOUL, YELLOW_CARD, INJURY, FULL_TIME)
        score_update: str   ("H - A")
        actor:        str   (player name)
        team:         str   (team name)
    Optional:
        assister:     str   (player name, on GOAL events only)
"""
from __future__ import annotations

import random
from enum import Enum
from typing import AsyncGenerator

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Phase Enum
# ---------------------------------------------------------------------------
class Phase(str, Enum):
    MIDFIELD = "MIDFIELD"
    BUILD_UP = "BUILD_UP"
    ATTACK = "ATTACK"
    SCORING_OPP = "SCORING_OPP"
    SET_PIECE = "SET_PIECE"
    COUNTER_ATTACK = "COUNTER_ATTACK"


# ---------------------------------------------------------------------------
# MatchTeamState — per-team live wrapper
# ---------------------------------------------------------------------------
class MatchTeamState:
    """Wraps a squad list and tracks live per-team state."""

    __slots__ = (
        "name", "squad", "momentum", "stagnation_counter",
        "_avg_attack", "_avg_midfield", "_avg_defense", "_avg_gk",
    )

    def __init__(self, name: str, squad: list, avg_rating: float) -> None:
        self.name = name
        self.squad = squad
        self.momentum: float = 0.0          # ±10 cap
        self.stagnation_counter: int = 0

        # Compute zone averages from squad, falling back to avg_rating
        self._avg_attack = avg_rating
        self._avg_midfield = avg_rating
        self._avg_defense = avg_rating
        self._avg_gk = avg_rating
        self._compute_zone_averages()

    # -- Zone average computation ------------------------------------------
    _POSITION_ZONES: dict[str, str] = {
        "GK": "gk",
        "DEF": "defense", "CB": "defense", "LB": "defense", "RB": "defense",
        "LWB": "defense", "RWB": "defense",
        "MID": "midfield", "CM": "midfield", "CDM": "midfield",
        "CAM": "midfield", "LM": "midfield", "RM": "midfield",
        "FWD": "attack", "ST": "attack", "CF": "attack",
        "LW": "attack", "RW": "attack",
    }

    def _compute_zone_averages(self) -> None:
        buckets: dict[str, list[float]] = {
            "gk": [], "defense": [], "midfield": [], "attack": [],
        }
        for p in self.squad:
            pos = p.position if hasattr(p, "position") else p.get("position", "MID")
            ovr = p.overall if hasattr(p, "overall") else p.get("overall", 50)
            zone = self._POSITION_ZONES.get(pos.upper(), "midfield")
            buckets[zone].append(float(ovr))

        # Use per-zone averages when populated, else fallback to overall avg
        overall_fallback = sum(
            p.overall if hasattr(p, "overall") else p.get("overall", 50)
            for p in self.squad
        ) / max(1, len(self.squad))

        self._avg_gk = _avg(buckets["gk"], overall_fallback * 0.9)
        self._avg_defense = _avg(buckets["defense"], overall_fallback)
        self._avg_midfield = _avg(buckets["midfield"], overall_fallback)
        self._avg_attack = _avg(buckets["attack"], overall_fallback)

    # -- Convenience zone accessors ----------------------------------------
    @property
    def attack(self) -> float:
        return self._avg_attack

    @property
    def midfield(self) -> float:
        return self._avg_midfield

    @property
    def defense(self) -> float:
        return self._avg_defense

    @property
    def gk(self) -> float:
        return self._avg_gk

    def clamp_momentum(self) -> None:
        self.momentum = max(-10.0, min(10.0, self.momentum))


def _avg(vals: list[float], fallback: float) -> float:
    return sum(vals) / len(vals) if vals else fallback


# ---------------------------------------------------------------------------
# MatchState — the engine's mutable state (Pydantic for battle_cog compat)
# ---------------------------------------------------------------------------
class MatchState(BaseModel):
    """
    Public match state exposed to battle_cog.py handlers.

    Backwards-compatible fields:
        home_rating, away_rating, home_score, away_score, minute, momentum,
        home_tactics_modifier, context_tags

    New internal fields are prefixed with underscore or stored outside this
    model in the stream_match() closure.
    """
    home_rating: float
    away_rating: float
    home_score: int = 0
    away_score: int = 0
    minute: int = 0
    momentum: int = 0           # -100..+100 (mapped from internal ±10 float)
    home_tactics_modifier: float = 1.0
    context_tags: list[str] = Field(default_factory=list)

    def update_tags(self) -> None:
        tags: list[str] = []
        if self.minute <= 15:
            tags.append("early")
        elif self.minute >= 75:
            tags.append("late")
        if self.home_score == self.away_score:
            tags.append("tied")
        elif self.home_score > self.away_score:
            tags.append("home_leading")
        else:
            tags.append("away_leading")
        if self.momentum >= 50:
            tags.append("high_momentum")
        elif self.momentum <= -50:
            tags.append("low_momentum")
        self.context_tags = tags


# ---------------------------------------------------------------------------
# Core probability engine
# ---------------------------------------------------------------------------
def _roll_chance(
    rng: random.Random,
    base_chance: float,
    attacker_stat: float,
    defender_stat: float,
    momentum: float,
    stagnation: int,
) -> bool:
    """
    Central probability formula.

    chance = base_chance + (attacker_stat - defender_stat) / 100 + momentum * 0.05 + stagnation * 0.10

    Returns True if the roll succeeds.
    """
    chance = (
        base_chance
        + (attacker_stat - defender_stat) / 100.0
        + momentum * 0.05
        + stagnation * 0.10
    )
    chance = max(0.05, min(0.95, chance))   # hard clamp
    return rng.random() < chance


# ---------------------------------------------------------------------------
# Player selection helpers (thread-safe — use the per-match rng)
# ---------------------------------------------------------------------------
def _pick_player(rng: random.Random, squad: list, prefer_zone: str | None = None) -> object:
    """
    Pick a player from the squad, preferring a zone if specified.
    Falls back to any player if the zone is empty.
    """
    if prefer_zone and squad:
        zone_players = [
            p for p in squad
            if MatchTeamState._POSITION_ZONES.get(
                (p.position if hasattr(p, "position") else p.get("position", "MID")).upper(),
                "midfield"
            ) == prefer_zone
        ]
        if zone_players:
            return rng.choice(zone_players)
    return rng.choice(squad) if squad else None


def _get_name(player) -> str:
    if player is None:
        return "Unknown Player"
    return player.name if hasattr(player, "name") else player.get("name", "Unknown Player")


# ---------------------------------------------------------------------------
# Momentum application
# ---------------------------------------------------------------------------
def _apply_momentum_goal(scorer_team: MatchTeamState, conceder_team: MatchTeamState) -> None:
    scorer_team.momentum += 3.0
    conceder_team.momentum -= 2.0
    scorer_team.clamp_momentum()
    conceder_team.clamp_momentum()


def _apply_momentum_save(defending_team: MatchTeamState) -> None:
    defending_team.momentum += 1.0
    defending_team.clamp_momentum()


def _decay_momentum(team: MatchTeamState) -> None:
    """Decay towards 0 by 0.5."""
    if team.momentum > 0:
        team.momentum = max(0.0, team.momentum - 0.5)
    elif team.momentum < 0:
        team.momentum = min(0.0, team.momentum + 0.5)


# ---------------------------------------------------------------------------
# Time pacing helpers
# ---------------------------------------------------------------------------
_PHASE_MINUTES: dict[Phase, tuple[int, int]] = {
    Phase.MIDFIELD:       (4, 8),
    Phase.BUILD_UP:       (1, 3),
    Phase.ATTACK:         (1, 2),
    Phase.SCORING_OPP:    (1, 2),
    Phase.SET_PIECE:      (2, 4),
    Phase.COUNTER_ATTACK: (1, 2),
}


def _advance_clock(rng: random.Random, phase: Phase, current_minute: int) -> int:
    lo, hi = _PHASE_MINUTES.get(phase, (2, 5))
    return min(90, current_minute + rng.randint(lo, hi))


# ---------------------------------------------------------------------------
# stream_match — the async generator consumed by battle_cog.py
# ---------------------------------------------------------------------------
async def stream_match(
    state: MatchState,
    home_squad: list,
    away_squad: list,
    home_name: str,
    away_name: str,
) -> AsyncGenerator[dict, None]:
    """
    Async generator that drives the Markov-chain match simulation.

    Yields event dicts with the exact keys expected by IMatchOutputHandler:
        minute, type, score_update, actor, team  (+optional assister)
    """
    # Thread-safe RNG — never touches global random state
    rng = random.Random()

    # Build team state wrappers
    home = MatchTeamState(home_name, home_squad, state.home_rating)
    away = MatchTeamState(away_name, away_squad, state.away_rating)

    # Engine state
    phase = Phase.MIDFIELD
    attacking: MatchTeamState = home       # who currently has the ball
    defending: MatchTeamState = away
    last_decay_minute = 0
    halftime_yielded = False

    state.update_tags()

    # ── KICKOFF ──────────────────────────────────────────────────────────
    yield {
        "minute": 0,
        "type": "KICKOFF",
        "score_update": "0 - 0",
        "actor": "The referee",
        "team": home_name,
    }

    # ── MAIN MARKOV LOOP ────────────────────────────────────────────────
    while state.minute < 90:
        # Check if we should insert half-time first
        if state.minute >= 45 and not halftime_yielded:
            state.minute = 45
            halftime_yielded = True
            state.update_tags()
            yield {
                "minute": 45,
                "type": "HALF_TIME",
                "score_update": f"{state.home_score} - {state.away_score}",
                "actor": "The referee",
                "team": home_name,
            }
            phase = Phase.MIDFIELD
            continue
        # Apply tactics modifier to home attack rating
        effective_home_attack = home.attack * state.home_tactics_modifier

        # Momentum decay every ~10 in-game minutes
        if state.minute - last_decay_minute >= 10:
            _decay_momentum(home)
            _decay_momentum(away)
            last_decay_minute = state.minute

        # Sync public state
        state.momentum = int(home.momentum * 10)  # ±10 → ±100
        state.update_tags()

        # ── PHASE EVALUATION ────────────────────────────────────────────
        if phase == Phase.MIDFIELD:
            # Hidden phase — compare midfield vs midfield + momentum
            atk_mid = attacking.midfield + (attacking.momentum * 2)
            def_mid = defending.midfield + (defending.momentum * 2)

            # Foul sub-roll (~8% per midfield phase)
            if rng.random() < 0.08:
                state.minute = _advance_clock(rng, phase, state.minute)
                phase = Phase.SET_PIECE
                # Foul committed by defending team
                fouler = _pick_player(rng, defending.squad, "defense")
                fouler_name = _get_name(fouler)
                yield {
                    "minute": state.minute,
                    "type": "FOUL",
                    "score_update": f"{state.home_score} - {state.away_score}",
                    "actor": fouler_name,
                    "team": defending.name,
                }
                # Yellow card sub-roll (~30% of fouls)
                if rng.random() < 0.30:
                    yield {
                        "minute": state.minute,
                        "type": "YELLOW_CARD",
                        "score_update": f"{state.home_score} - {state.away_score}",
                        "actor": fouler_name,
                        "team": defending.name,
                    }
                continue

            state.minute = _advance_clock(rng, phase, state.minute)
            if state.minute >= 90:
                break

            midfield_base = 0.55 if attacking.name == home_name else 0.50
            if _roll_chance(rng, midfield_base, atk_mid, def_mid, attacking.momentum, 0):
                phase = Phase.BUILD_UP
                # Attacking side keeps possession — no transition of sides
            else:
                phase = Phase.BUILD_UP
                # Opponent wins midfield — swap sides
                attacking, defending = defending, attacking

        elif phase == Phase.BUILD_UP:
            # Hidden phase — compare passing vs defense
            atk_pass = attacking.midfield  # passing ≈ midfield quality
            def_def = defending.defense

            state.minute = _advance_clock(rng, phase, state.minute)
            if state.minute >= 90:
                break

            if _roll_chance(rng, 0.45, atk_pass, def_def, attacking.momentum,
                            attacking.stagnation_counter):
                phase = Phase.ATTACK
            else:
                # Failed build-up → opponent counter-attack
                phase = Phase.COUNTER_ATTACK
                attacking, defending = defending, attacking

        elif phase == Phase.ATTACK:
            # [VISIBLE] — compare creativity (attack) vs defense
            atk_stat = attacking.attack
            if attacking.name == home_name:
                atk_stat = effective_home_attack
            def_stat = defending.defense

            state.minute = _advance_clock(rng, phase, state.minute)
            if state.minute >= 90:
                break

            actor = _pick_player(rng, attacking.squad, "attack")
            actor_name = _get_name(actor)

            yield {
                "minute": state.minute,
                "type": "CHANCE",
                "score_update": f"{state.home_score} - {state.away_score}",
                "actor": actor_name,
                "team": attacking.name,
            }

            if _roll_chance(rng, 0.40, atk_stat, def_stat, attacking.momentum,
                            attacking.stagnation_counter):
                phase = Phase.SCORING_OPP
                # Keep same attacking/defending sides
            else:
                attacking.stagnation_counter += 1
                phase = Phase.MIDFIELD

        elif phase == Phase.SCORING_OPP:
            # [VISIBLE] — compare shooting vs GK
            atk_shot = attacking.attack
            if attacking.name == home_name:
                atk_shot = effective_home_attack
            def_gk = defending.gk

            state.minute = _advance_clock(rng, phase, state.minute)

            scorer = _pick_player(rng, attacking.squad, "attack")
            scorer_name = _get_name(scorer)

            # Reset stagnation — a shot has occurred
            attacking.stagnation_counter = 0

            roll = rng.random()
            chance = max(0.05, min(0.95,
                0.45 + (atk_shot - def_gk) / 100.0 + attacking.momentum * 0.05
            ))

            if roll < chance:
                # ── GOAL ────────────────────────────────────────────────
                if attacking.name == home_name:
                    state.home_score += 1
                else:
                    state.away_score += 1

                event: dict = {
                    "minute": state.minute,
                    "type": "GOAL",
                    "score_update": f"{state.home_score} - {state.away_score}",
                    "actor": scorer_name,
                    "team": attacking.name,
                }

                # Assist roll (~70%)
                if rng.random() < 0.70:
                    other_players = [
                        p for p in attacking.squad
                        if _get_name(p) != scorer_name
                    ]
                    if other_players:
                        assister = _pick_player(rng, other_players, "midfield")
                        event["assister"] = _get_name(assister)

                yield event

                _apply_momentum_goal(attacking, defending)

                # Injury sub-roll on goal celebrations (~1%)
                if rng.random() < 0.01 and len(attacking.squad) > 0:
                    injury_player = _pick_player(rng, attacking.squad)
                    yield {
                        "minute": state.minute,
                        "type": "INJURY",
                        "score_update": f"{state.home_score} - {state.away_score}",
                        "actor": _get_name(injury_player),
                        "team": attacking.name,
                    }

                phase = Phase.MIDFIELD

            elif roll < chance + (1 - chance) * 0.45:
                # ── SAVE ────────────────────────────────────────────────
                goalkeeper = _pick_player(rng, defending.squad, "gk")
                yield {
                    "minute": state.minute,
                    "type": "SAVE",
                    "score_update": f"{state.home_score} - {state.away_score}",
                    "actor": _get_name(goalkeeper),
                    "team": defending.name,
                }
                _apply_momentum_save(defending)
                phase = Phase.SET_PIECE
                # Set piece goes to the attacking side (corner)
                # attacking/defending stay the same

            else:
                # ── MISS ────────────────────────────────────────────────
                yield {
                    "minute": state.minute,
                    "type": "MISS",
                    "score_update": f"{state.home_score} - {state.away_score}",
                    "actor": scorer_name,
                    "team": attacking.name,
                }
                phase = Phase.MIDFIELD

        elif phase == Phase.SET_PIECE:
            # [VISIBLE] — set piece (corner / free kick)
            state.minute = _advance_clock(rng, phase, state.minute)
            if state.minute >= 90:
                break

            actor = _pick_player(rng, attacking.squad, "midfield")
            actor_name = _get_name(actor)

            yield {
                "minute": state.minute,
                "type": "CHANCE",
                "score_update": f"{state.home_score} - {state.away_score}",
                "actor": actor_name,
                "team": attacking.name,
            }

            # Set piece → scoring opportunity (~35%) or cleared
            if _roll_chance(rng, 0.35, attacking.attack, defending.defense,
                            attacking.momentum, 0):
                phase = Phase.SCORING_OPP
            else:
                phase = Phase.MIDFIELD

        elif phase == Phase.COUNTER_ATTACK:
            # [VISIBLE] — fast break, high risk/reward
            atk_speed = attacking.attack
            if attacking.name == home_name:
                atk_speed = effective_home_attack
            def_recovery = defending.defense

            state.minute = _advance_clock(rng, phase, state.minute)
            if state.minute >= 90:
                break

            actor = _pick_player(rng, attacking.squad, "attack")
            actor_name = _get_name(actor)

            yield {
                "minute": state.minute,
                "type": "CHANCE",
                "score_update": f"{state.home_score} - {state.away_score}",
                "actor": actor_name,
                "team": attacking.name,
            }

            # Counter-attack: higher reward (skip build-up) but lower base chance
            if _roll_chance(rng, 0.30, atk_speed, def_recovery,
                            attacking.momentum, 0):
                phase = Phase.SCORING_OPP
            else:
                attacking.stagnation_counter += 1
                phase = Phase.MIDFIELD

            # Injury sub-roll on counter-attacks (~2%)
            if rng.random() < 0.02 and len(defending.squad) > 0:
                injury_player = _pick_player(rng, defending.squad, "defense")
                yield {
                    "minute": state.minute,
                    "type": "INJURY",
                    "score_update": f"{state.home_score} - {state.away_score}",
                    "actor": _get_name(injury_player),
                    "team": defending.name,
                }

    # ── FULL TIME ────────────────────────────────────────────────────────
    state.minute = 90
    state.momentum = int(home.momentum * 10)
    state.update_tags()

    yield {
        "minute": 90,
        "type": "FULL_TIME",
        "score_update": f"{state.home_score} - {state.away_score}",
        "actor": "The referee",
        "team": home_name,
    }
