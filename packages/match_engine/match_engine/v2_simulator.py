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

from .match_stats import MatchLiveStats
from .phase_stats import PhaseStat, phase_stat_value
from .substitution_resolve import (
    MAX_SUBS_PER_MATCH,
    SubResolution,
    apply_sub,
    apply_ten_men,
    auto_resolve_injury,
    bench_options_payload,
    is_gk,
)

# Stat gap impact: /55 yields ~75%+ favorite win at +10 OVR (audit target)
_STAT_DIFF_DIVISOR = 55.0
_STAGNATION_MULT = 0.05  # per spec (plan.md NSS section)


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
        "name", "squad", "momentum", "stagnation_counter", "is_home",
        "_avg_attack", "_avg_midfield", "_avg_defense", "_avg_gk",
    )

    def __init__(self, name: str, squad: list, avg_rating: float, is_home: bool = False) -> None:
        self.name = name
        self.squad = squad
        self.momentum: float = 0.0          # ±10 cap
        self.stagnation_counter: int = 0
        self.is_home = is_home

        self._avg_attack = avg_rating
        self._avg_midfield = avg_rating
        self._avg_defense = avg_rating
        self._avg_gk = avg_rating
        self._compute_zone_averages()

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

        overall_fallback = sum(
            p.overall if hasattr(p, "overall") else p.get("overall", 50)
            for p in self.squad
        ) / max(1, len(self.squad))

        self._avg_gk = _avg(buckets["gk"], overall_fallback * 0.9)
        self._avg_defense = _avg(buckets["defense"], overall_fallback)
        self._avg_midfield = _avg(buckets["midfield"], overall_fallback)
        self._avg_attack = _avg(buckets["attack"], overall_fallback)

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

    def phase_attack(self, phase: PhaseStat, tactics_mult: float = 1.0) -> float:
        fallbacks = {
            PhaseStat.MIDFIELD: self._avg_midfield,
            PhaseStat.PASSING: self._avg_midfield,
            PhaseStat.ATTACK: self._avg_attack,
            PhaseStat.SHOOTING: self._avg_attack,
            PhaseStat.PACE: self._avg_attack,
            PhaseStat.DEFENSE: self._avg_defense,
            PhaseStat.GOALKEEPING: self._avg_gk,
        }
        val = phase_stat_value(self.squad, phase, fallbacks[phase])
        if phase in (PhaseStat.ATTACK, PhaseStat.SHOOTING, PhaseStat.PACE) and tactics_mult != 1.0:
            val *= tactics_mult
        return val

    def phase_defense(self) -> float:
        return phase_stat_value(self.squad, PhaseStat.DEFENSE, self._avg_defense)

    def phase_gk(self) -> float:
        return phase_stat_value(self.squad, PhaseStat.GOALKEEPING, self._avg_gk)

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

    Phase 3 injury/sub fields are serializable; asyncio.Event for Discord pause
    is attached as a plain attribute (sub_wait_event) outside Pydantic.
    """
    model_config = {"arbitrary_types_allowed": True}

    home_rating: float
    away_rating: float
    home_score: int = 0
    away_score: int = 0
    minute: int = 0
    momentum: int = 0           # -100..+100 (mapped from internal ±10 float)
    home_tactics_modifier: float = 1.0
    context_tags: list[str] = Field(default_factory=list)
    pending_home_momentum: float = 0.0
    live_stats: MatchLiveStats = Field(default_factory=MatchLiveStats)

    # Phase 3 — in-match injury / subs
    injuries_enabled: bool = False
    interactive_sides: list[str] = Field(default_factory=list)
    bench_home: list = Field(default_factory=list)
    bench_away: list = Field(default_factory=list)
    subs_used_home: int = 0
    subs_used_away: int = 0
    recorded_injuries: list[dict] = Field(default_factory=list)
    compromised_card_ids: list[str] = Field(default_factory=list)
    emergency_gk_ids: list[str] = Field(default_factory=list)
    injury_used_home: bool = False
    injury_used_away: bool = False
    sub_resolution: dict | None = None
    # 016 — shared intensity for injury rolls (human owner's tier in bot matches)
    intensity_tier: int = 1
    # Wave 2 TransitionProfile knobs (defaults = exact NSS v2 behaviour)
    build_up_clock_mult: float = 1.0
    counter_weight: float = 1.0
    set_piece_rate: float = 0.08
    transition_style: str = "balanced"
    counters_triggered: int = 0

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
def _probability_floor(attacker_stat: float, defender_stat: float) -> float:
    """Hard 5% floor so trailing sides still win contested transitions (immersion)."""
    return 0.05


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

    chance = base_chance + (attacker_stat - defender_stat) / 60 + momentum * 0.05 + stagnation * 0.05
    """
    chance = (
        base_chance
        + (attacker_stat - defender_stat) / _STAT_DIFF_DIVISOR
        + momentum * 0.05
        + stagnation * _STAGNATION_MULT
    )
    floor = _probability_floor(attacker_stat, defender_stat)
    chance = max(floor, min(0.95, chance))
    return rng.random() < chance


# ---------------------------------------------------------------------------
# Player selection helpers (thread-safe — use the per-match rng)
# ---------------------------------------------------------------------------
def _pick_player(rng: random.Random, squad: list, prefer_zone: str | None = None) -> object:
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


def _apply_pending_home_momentum(state: MatchState, home: MatchTeamState) -> None:
    if state.pending_home_momentum:
        home.momentum += state.pending_home_momentum
        home.clamp_momentum()
        state.pending_home_momentum = 0.0


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


def _advance_clock(
    rng: random.Random,
    phase: Phase,
    current_minute: int,
    *,
    build_up_clock_mult: float = 1.0,
) -> int:
    lo, hi = _PHASE_MINUTES.get(phase, (2, 5))
    delta = rng.randint(lo, hi)
    if phase == Phase.BUILD_UP and build_up_clock_mult != 1.0:
        delta = max(1, int(round(delta * build_up_clock_mult)))
    return min(90, current_minute + delta)


def _player_card_id(player) -> str | None:
    if player is None:
        return None
    if hasattr(player, "card_id") and player.card_id:
        return str(player.card_id)
    if isinstance(player, dict):
        return str(player.get("id") or player.get("card_id") or "") or None
    return None


def _find_player(squad: list, card_id: str | None):
    if not card_id:
        return None
    for p in squad:
        if _player_card_id(p) == card_id:
            return p
    return None


def _starters_for_injury_roll(squad: list) -> list[dict]:
    rows = []
    for p in squad:
        cid = _player_card_id(p)
        if not cid:
            continue
        fatigue = int(getattr(p, "fatigue", None) or (p.get("fatigue", 100) if isinstance(p, dict) else 100))
        phy = int(getattr(p, "phy", None) or (p.get("phy", 50) if isinstance(p, dict) else 50))
        age = int(getattr(p, "age", None) or (p.get("age", 25) if isinstance(p, dict) else 25))
        rows.append({"id": cid, "fatigue": fatigue, "phy": phy, "age": age})
    return rows


def _bench_for_side(state: MatchState, side: str) -> list:
    return list(state.bench_home if side == "home" else state.bench_away)


def _subs_used(state: MatchState, side: str) -> int:
    return state.subs_used_home if side == "home" else state.subs_used_away


def _set_subs_used(state: MatchState, side: str, value: int) -> None:
    if side == "home":
        state.subs_used_home = value
    else:
        state.subs_used_away = value


def _set_bench(state: MatchState, side: str, bench: list) -> None:
    if side == "home":
        state.bench_home = bench
    else:
        state.bench_away = bench


def _apply_sub_resolution(
    state: MatchState,
    home: MatchTeamState,
    away: MatchTeamState,
    resolution: SubResolution | dict,
) -> None:
    if isinstance(resolution, dict):
        resolution = SubResolution(
            kind=resolution["kind"],
            injured_card_id=resolution.get("injured_card_id"),
            replacement_card_id=resolution.get("replacement_card_id"),
            tier=int(resolution.get("tier") or 1),
            side=str(resolution.get("side") or "home"),
            play_on=bool(resolution.get("play_on")),
        )
    side = resolution.side
    team = home if side == "home" else away
    bench = _bench_for_side(state, side)
    injured_id = resolution.injured_card_id or ""
    kind = resolution.kind

    if kind == "play_on" or resolution.play_on:
        if injured_id and injured_id not in state.compromised_card_ids:
            state.compromised_card_ids.append(injured_id)
        injured_p = _find_player(team.squad, injured_id)
        if injured_p is not None:
            if hasattr(injured_p, "compromised"):
                injured_p.compromised = True
            elif isinstance(injured_p, dict):
                injured_p["compromised"] = True
        if "played_through_injury" not in state.context_tags:
            state.context_tags.append("played_through_injury")
    elif kind == "sub" and resolution.replacement_card_id:
        team.squad, bench = apply_sub(
            team.squad, bench, injured_id, resolution.replacement_card_id
        )
        team._compute_zone_averages()
        _set_bench(state, side, bench)
        _set_subs_used(state, side, _subs_used(state, side) + 1)
        if "substitution" not in state.context_tags:
            state.context_tags.append("substitution")
    elif kind == "emergency_gk" and resolution.replacement_card_id:
        team.squad = apply_ten_men(team.squad, injured_id)
        em = _find_player(team.squad, resolution.replacement_card_id)
        if em is not None:
            if hasattr(em, "emergency_gk"):
                em.emergency_gk = True
            elif isinstance(em, dict):
                em["emergency_gk"] = True
            if hasattr(em, "position"):
                em.position = "GK"
            elif isinstance(em, dict):
                em["position"] = "GK"
        if resolution.replacement_card_id not in state.emergency_gk_ids:
            state.emergency_gk_ids.append(resolution.replacement_card_id)
        team._compute_zone_averages()
        _set_subs_used(state, side, _subs_used(state, side) + 1)
        if "emergency_goalkeeper" not in state.context_tags:
            state.context_tags.append("emergency_goalkeeper")
    else:  # ten_men
        team.squad = apply_ten_men(team.squad, injured_id)
        team._compute_zone_averages()
        if "down_to_ten_men" not in state.context_tags:
            state.context_tags.append("down_to_ten_men")

    state.recorded_injuries.append({
        "player_card_id": injured_id,
        "tier": resolution.tier,
        "side": side,
        "resolution": kind,
        "minute": state.minute,
        "play_on": kind == "play_on" or resolution.play_on,
    })
    if side == "home":
        state.injury_used_home = True
    else:
        state.injury_used_away = True
    state.sub_resolution = None


def _build_injury_event(
    state: MatchState,
    team: MatchTeamState,
    side: str,
    injured,
    tier: int,
) -> dict:
    bench = _bench_for_side(state, side)
    subs_used = _subs_used(state, side)
    subs_remaining = max(0, MAX_SUBS_PER_MATCH - subs_used)
    minute = state.minute
    gk_emergency = bool(is_gk(injured) and not any(is_gk(p) for p in bench))
    options: list[str] = []
    if minute < 90:
        if subs_remaining > 0 and bench:
            options = ["sub", "play_on"]
        elif gk_emergency:
            options = ["play_on"]  # emergency path still allows play_on; auto may pick emergency
        elif subs_remaining > 0 and not bench:
            options = []  # 10-men auto
        else:
            options = ["play_on"]  # no subs left — play on or auto ten_men via timeout

    interactive = (
        state.injuries_enabled
        and side in state.interactive_sides
        and minute < 90
        and bool(options)
    )

    return {
        "minute": minute,
        "type": "INJURY",
        "score_update": f"{state.home_score} - {state.away_score}",
        "actor": _get_name(injured),
        "team": team.name,
        "interactive": interactive,
        "side": side,
        "injured_card_id": _player_card_id(injured),
        "injured_name": _get_name(injured),
        "injury_tier": tier,
        "subs_remaining": subs_remaining,
        "bench": bench_options_payload(bench),
        "options": options,
        "gk_emergency": gk_emergency,
    }


def _try_authoritative_injury(
    state: MatchState,
    team: MatchTeamState,
    side: str,
    rng: random.Random,
) -> dict | None:
    """A+C mid-match roll; at most one injury per side per match."""
    if not state.injuries_enabled:
        return None
    if side == "home" and state.injury_used_home:
        return None
    if side == "away" and state.injury_used_away:
        return None
    if not team.squad:
        return None
    from player_engine import select_post_match_injury

    hit = select_post_match_injury(
        _starters_for_injury_roll(team.squad),
        rng=rng,
        intensity_tier=int(getattr(state, "intensity_tier", 1) or 1),
    )
    if not hit:
        return None
    injured = _find_player(team.squad, hit.player_card_id)
    if injured is None:
        return None
    return _build_injury_event(state, team, side, injured, hit.tier)


def _consume_injury_after_yield(
    state: MatchState,
    home: MatchTeamState,
    away: MatchTeamState,
    injury_ev: dict,
    rng: random.Random,
) -> None:
    """After Discord/auto consumer sets sub_resolution (or fallback auto)."""
    if state.sub_resolution:
        _apply_sub_resolution(state, home, away, state.sub_resolution)
        return
    side = injury_ev.get("side") or "home"
    team = home if side == "home" else away
    injured = _find_player(team.squad, injury_ev.get("injured_card_id"))
    if injured is None:
        # Already gone — still record
        state.recorded_injuries.append({
            "player_card_id": injury_ev.get("injured_card_id"),
            "tier": int(injury_ev.get("injury_tier") or 1),
            "side": side,
            "resolution": "ten_men",
            "minute": state.minute,
            "play_on": False,
        })
        if side == "home":
            state.injury_used_home = True
        else:
            state.injury_used_away = True
        return
    res = auto_resolve_injury(
        side=side,
        injured=injured,
        bench=_bench_for_side(state, side),
        squad=team.squad,
        subs_used=_subs_used(state, side),
        tier=int(injury_ev.get("injury_tier") or 1),
        rng=rng,
    )
    _apply_sub_resolution(state, home, away, res)


# ---------------------------------------------------------------------------
# generate_match_events — sync sporting loop (NSS v2)
# stream_match — async wrapper for battle_cog live pacing
# ---------------------------------------------------------------------------
def generate_match_events(
    state: MatchState,
    home_squad: list,
    away_squad: list,
    home_name: str,
    away_name: str,
    rng: random.Random | None = None,
):
    """Synchronous event generator — shared by v2 async wrapper and v3 engine."""
    if rng is None:
        rng = random.Random()

    def _tick(ph: Phase) -> int:
        return _advance_clock(
            rng, ph, state.minute, build_up_clock_mult=float(state.build_up_clock_mult or 1.0)
        )

    set_piece_p = float(state.set_piece_rate if state.set_piece_rate is not None else 0.08)
    cw = float(state.counter_weight if state.counter_weight is not None else 1.0)

    home = MatchTeamState(home_name, home_squad, state.home_rating, is_home=True)
    away = MatchTeamState(away_name, away_squad, state.away_rating, is_home=False)

    phase = Phase.MIDFIELD
    attacking: MatchTeamState = home
    defending: MatchTeamState = away
    last_decay_minute = 0
    halftime_yielded = False
    stats = state.live_stats

    state.update_tags()

    yield {
        "minute": 0,
        "type": "KICKOFF",
        "score_update": "0 - 0",
        "actor": "The referee",
        "team": home_name,
    }

    while state.minute < 90:
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
            # Stoppage: optional A+C injury for either side
            for side, team in (("home", home), ("away", away)):
                if rng.random() < 0.15:
                    inj = _try_authoritative_injury(state, team, side, rng)
                    if inj:
                        yield inj
                        _consume_injury_after_yield(state, home, away, inj, rng)
            phase = Phase.MIDFIELD
            continue

        _apply_pending_home_momentum(state, home)
        tactics = state.home_tactics_modifier if attacking.is_home else 1.0

        if state.minute - last_decay_minute >= 10:
            _decay_momentum(home)
            _decay_momentum(away)
            last_decay_minute = state.minute

        state.momentum = int(home.momentum * 10)
        state.update_tags()

        if phase == Phase.MIDFIELD:
            atk_mid = attacking.phase_attack(PhaseStat.MIDFIELD) + (attacking.momentum * 2)
            def_mid = defending.phase_attack(PhaseStat.MIDFIELD) + (defending.momentum * 2)

            if rng.random() < set_piece_p:
                state.minute = _tick(phase)
                phase = Phase.SET_PIECE
                # Set-piece side keeps the ball — count possession (was missing → 0% ghosts)
                stats.record_possession(attacking.is_home)
                fouler = _pick_player(rng, defending.squad, "defense")
                fouler_name = _get_name(fouler)
                yield {
                    "minute": state.minute,
                    "type": "FOUL",
                    "score_update": f"{state.home_score} - {state.away_score}",
                    "actor": fouler_name,
                    "team": defending.name,
                }
                if rng.random() < 0.30:
                    yield {
                        "minute": state.minute,
                        "type": "YELLOW_CARD",
                        "score_update": f"{state.home_score} - {state.away_score}",
                        "actor": fouler_name,
                        "team": defending.name,
                    }
                # Stoppage injury check on defending side
                if rng.random() < 0.12:
                    side = "home" if defending.is_home else "away"
                    inj = _try_authoritative_injury(state, defending, side, rng)
                    if inj:
                        yield inj
                        _consume_injury_after_yield(state, home, away, inj, rng)
                continue

            state.minute = _tick(phase)
            if state.minute >= 90:
                break

            midfield_base = 0.55 if attacking.is_home else 0.50
            won_midfield = _roll_chance(rng, midfield_base, atk_mid, def_mid, attacking.momentum, 0)
            if won_midfield:
                stats.record_possession(attacking.is_home)
                # Wave 2: counter styles may skip build-up into a direct counter break
                direct_counter_p = 0.12 * max(0.0, cw - 1.0)
                if direct_counter_p > 0 and rng.random() < direct_counter_p:
                    phase = Phase.COUNTER_ATTACK
                    state.counters_triggered += 1
                else:
                    phase = Phase.BUILD_UP
            else:
                stats.record_possession(defending.is_home)
                phase = Phase.BUILD_UP
                attacking, defending = defending, attacking
                tactics = state.home_tactics_modifier if attacking.is_home else 1.0

        elif phase == Phase.BUILD_UP:
            atk_pass = attacking.phase_attack(PhaseStat.PASSING)
            def_def = defending.phase_defense()

            state.minute = _tick(phase)
            if state.minute >= 90:
                break

            if _roll_chance(rng, 0.45, atk_pass, def_def, attacking.momentum,
                            attacking.stagnation_counter):
                phase = Phase.ATTACK
            else:
                # Wave 2: possession styles (cw < 1) may recycle to midfield instead of counter
                if cw < 1.0 and rng.random() > cw:
                    phase = Phase.MIDFIELD
                    attacking, defending = defending, attacking
                    tactics = state.home_tactics_modifier if attacking.is_home else 1.0
                else:
                    phase = Phase.COUNTER_ATTACK
                    state.counters_triggered += 1
                    attacking, defending = defending, attacking
                    tactics = state.home_tactics_modifier if attacking.is_home else 1.0
                    # Countering side wins the ball — was uncounted → 0% with chances
                    stats.record_possession(attacking.is_home)
        elif phase == Phase.ATTACK:
            atk_stat = attacking.phase_attack(PhaseStat.ATTACK, tactics)
            def_stat = defending.phase_defense()

            state.minute = _tick(phase)
            if state.minute >= 90:
                break

            actor = _pick_player(rng, attacking.squad, "attack")
            actor_name = _get_name(actor)
            stats.record_chance(attacking.is_home)

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
            else:
                attacking.stagnation_counter += 1
                phase = Phase.MIDFIELD

        elif phase == Phase.SCORING_OPP:
            atk_shot = attacking.phase_attack(PhaseStat.SHOOTING, tactics)
            def_gk = defending.phase_gk()

            state.minute = _tick(phase)

            scorer = _pick_player(rng, attacking.squad, "attack")
            scorer_name = _get_name(scorer)
            attacking.stagnation_counter = 0
            stats.record_shot(attacking.is_home)

            roll = rng.random()
            diff = atk_shot - def_gk
            chance = 0.45 + diff / _STAT_DIFF_DIVISOR + attacking.momentum * 0.05
            floor = _probability_floor(atk_shot, def_gk)
            chance = max(floor, min(0.95, chance))

            if roll < chance:
                if attacking.is_home:
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

                assister_name = None
                if rng.random() < 0.70:
                    other_players = [
                        p for p in attacking.squad
                        if _get_name(p) != scorer_name
                    ]
                    if other_players:
                        assister = _pick_player(rng, other_players, "midfield")
                        assister_name = _get_name(assister)
                        event["assister"] = assister_name

                stats.record_goal(scorer_name, assister_name)
                yield event

                _apply_momentum_goal(attacking, defending)

                if rng.random() < 0.03:
                    side = "home" if attacking.is_home else "away"
                    inj = _try_authoritative_injury(state, attacking, side, rng)
                    if inj:
                        yield inj
                        _consume_injury_after_yield(state, home, away, inj, rng)

                phase = Phase.MIDFIELD

            elif roll < chance + (1 - chance) * 0.45:
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
                if rng.random() < 0.08:
                    side = "home" if defending.is_home else "away"
                    inj = _try_authoritative_injury(state, defending, side, rng)
                    if inj:
                        yield inj
                        _consume_injury_after_yield(state, home, away, inj, rng)

            else:
                yield {
                    "minute": state.minute,
                    "type": "MISS",
                    "score_update": f"{state.home_score} - {state.away_score}",
                    "actor": scorer_name,
                    "team": attacking.name,
                }
                phase = Phase.MIDFIELD

        elif phase == Phase.SET_PIECE:
            state.minute = _tick(phase)
            if state.minute >= 90:
                break

            actor = _pick_player(rng, attacking.squad, "midfield")
            actor_name = _get_name(actor)
            stats.record_chance(attacking.is_home)

            yield {
                "minute": state.minute,
                "type": "CHANCE",
                "score_update": f"{state.home_score} - {state.away_score}",
                "actor": actor_name,
                "team": attacking.name,
            }

            if _roll_chance(rng, 0.35, attacking.phase_attack(PhaseStat.ATTACK, tactics),
                            defending.phase_defense(), attacking.momentum, 0):
                phase = Phase.SCORING_OPP
            else:
                phase = Phase.MIDFIELD

        elif phase == Phase.COUNTER_ATTACK:
            atk_speed = attacking.phase_attack(PhaseStat.PACE, tactics)
            def_recovery = defending.phase_defense()

            state.minute = _tick(phase)
            if state.minute >= 90:
                break

            actor = _pick_player(rng, attacking.squad, "attack")
            actor_name = _get_name(actor)
            stats.record_chance(attacking.is_home)

            yield {
                "minute": state.minute,
                "type": "CHANCE",
                "score_update": f"{state.home_score} - {state.away_score}",
                "actor": actor_name,
                "team": attacking.name,
            }

            if _roll_chance(rng, 0.30, atk_speed, def_recovery,
                            attacking.momentum, 0):
                phase = Phase.SCORING_OPP
            else:
                attacking.stagnation_counter += 1
                phase = Phase.MIDFIELD

            if rng.random() < 0.04:
                side = "home" if defending.is_home else "away"
                inj = _try_authoritative_injury(state, defending, side, rng)
                if inj:
                    yield inj
                    _consume_injury_after_yield(state, home, away, inj, rng)

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


async def stream_match(
    state: MatchState,
    home_squad: list,
    away_squad: list,
    home_name: str,
    away_name: str,
    rng: random.Random | None = None,
) -> AsyncGenerator[dict, None]:
    for ev in generate_match_events(
        state, home_squad, away_squad, home_name, away_name, rng=rng
    ):
        yield ev


async def collect_match_events(
    state: MatchState,
    home_squad: list,
    away_squad: list,
    home_name: str,
    away_name: str,
    sim_seed: int,
) -> tuple[MatchState, list[dict]]:
    """Run match to completion without Discord delays (recovery / fast-forward)."""
    # Silent sims never prompt — clear interactive sides so events auto-resolve
    state.interactive_sides = []
    rng = random.Random(sim_seed)
    events = list(
        generate_match_events(state, home_squad, away_squad, home_name, away_name, rng=rng)
    )
    return state, events
