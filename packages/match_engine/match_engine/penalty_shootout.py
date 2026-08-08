# packages/match_engine/match_engine/penalty_shootout.py
"""Pure penalty shootout resolver for Competitive Bot Match (Feature 057)."""
from __future__ import annotations

import random
from typing import Any, Sequence

from .competitive_models import PenaltyKickEvent, PenaltyShootoutState

P_GOAL_MIN = 0.58
P_GOAL_MAX = 0.90


def derived_composure(consistency: float, morale: float | None = None) -> float:
    c = float(consistency)
    if morale is None:
        return c
    return c * 0.70 + float(morale) * 0.30


def _attr(player: Any, *names: str, default: float = 50.0) -> float:
    for n in names:
        if isinstance(player, dict) and n in player and player[n] is not None:
            return float(player[n])
        v = getattr(player, n, None)
        if v is not None:
            return float(v)
    return float(default)


def _pid(player: Any) -> str:
    for n in ("card_id", "id", "player_id", "player_card_id"):
        if isinstance(player, dict) and player.get(n) is not None:
            return str(player[n])
        v = getattr(player, n, None)
        if v is not None:
            return str(v)
    return str(id(player))


def _pname(player: Any) -> str:
    for n in ("name", "display_name"):
        if isinstance(player, dict) and player.get(n):
            return str(player[n])
        v = getattr(player, n, None)
        if v:
            return str(v)
    return "Unknown"


def _is_gk(player: Any) -> bool:
    pos = ""
    if isinstance(player, dict):
        pos = str(player.get("position") or player.get("role") or "")
    else:
        pos = str(getattr(player, "position", "") or getattr(player, "role", "") or "")
    return pos.upper() in ("GK", "GOALKEEPER")


def _fitness(player: Any) -> float:
    if isinstance(player, dict):
        if "fitness" in player and player["fitness"] is not None:
            return float(player["fitness"])
        if "fatigue" in player and player["fatigue"] is not None:
            # MatchPlayerCard.fatigue is remaining fitness (high = fresh)
            return float(player["fatigue"])
    if getattr(player, "fitness", None) is not None:
        return float(player.fitness)
    if getattr(player, "fatigue", None) is not None:
        return float(player.fatigue)
    return 80.0


def _morale(player: Any) -> float | None:
    if isinstance(player, dict) and "morale" in player and player["morale"] is not None:
        return float(player["morale"])
    v = getattr(player, "morale", None)
    return float(v) if v is not None else None


def penalty_taker_score(player: Any, rng: random.Random) -> float:
    sho = _attr(player, "sho", "shooting", "overall")
    cons = _attr(player, "consistency", default=50.0)
    composure = derived_composure(cons, _morale(player))
    fit = _fitness(player)
    jitter = rng.uniform(-1.5, 1.5)
    return sho * 0.55 + composure * 0.30 + fit * 0.10 + cons * 0.05 + jitter


def order_penalty_takers(eligible: Sequence[Any], rng: random.Random) -> list[Any]:
    scored = [(penalty_taker_score(p, rng), i, p) for i, p in enumerate(eligible)]
    scored.sort(key=lambda t: (-t[0], t[1]))
    return [p for _, _, p in scored]


def conversion_probability(taker: Any, keeper: Any) -> float:
    sho = _attr(taker, "sho", "shooting", "overall")
    cons_t = _attr(taker, "consistency", default=50.0)
    composure = derived_composure(cons_t, _morale(taker))
    fitness_t = _fitness(taker)

    defense = _attr(keeper, "def_stat", "defense", "def", "overall")
    reflexes = defense
    cons_k = _attr(keeper, "consistency", default=50.0)
    fitness_k = _fitness(keeper)

    taker_q = sho * 0.55 + composure * 0.30 + cons_t * 0.10 + fitness_t * 0.05
    keeper_q = defense * 0.40 + reflexes * 0.40 + cons_k * 0.10 + fitness_k * 0.10
    gap = (taker_q - keeper_q) / 100.0
    p = 0.74 + gap * 0.35
    return max(P_GOAL_MIN, min(P_GOAL_MAX, p))


def resolve_kick(
    taker: Any,
    keeper: Any,
    *,
    sequence: int,
    club_side: str,
    shootout_seed: int,
) -> PenaltyKickEvent:
    kick_rng = random.Random(int(shootout_seed) ^ (sequence * 0x9E3779B9) & 0x7FFFFFFF)
    p_goal = conversion_probability(taker, keeper)
    roll = kick_rng.random()
    if roll < p_goal:
        outcome = "goal"
    else:
        sho = _attr(taker, "sho", "shooting", "overall")
        composure = derived_composure(_attr(taker, "consistency", default=50.0), _morale(taker))
        defense = _attr(keeper, "def_stat", "defense", "def", "overall")
        if defense + kick_rng.uniform(0, 10) > sho * 0.5 + composure * 0.5:
            outcome = "saved"
        else:
            outcome = "missed"
    return PenaltyKickEvent(
        sequence=sequence,
        club_side=club_side,
        player_id=_pid(taker),
        player_name=_pname(taker),
        goalkeeper_id=_pid(keeper),
        goalkeeper_name=_pname(keeper),
        outcome=outcome,
        seed_key=f"{shootout_seed}:{sequence}",
    )


def _early_winner(state: PenaltyShootoutState) -> str | None:
    h_taken, a_taken = state.home_kicks_taken, state.away_kicks_taken
    h_s, a_s = state.home_penalties_scored, state.away_penalties_scored
    if state.sudden_death:
        if h_taken == a_taken and h_taken > 0 and h_s != a_s:
            return "home" if h_s > a_s else "away"
        return None
    h_left = max(0, 5 - h_taken)
    a_left = max(0, 5 - a_taken)
    if h_s > a_s + a_left:
        return "home"
    if a_s > h_s + h_left:
        return "away"
    return None


def pick_goalkeeper(squad: Sequence[Any]) -> Any:
    for p in squad:
        if _is_gk(p):
            return p
    return squad[0] if squad else {
        "id": "gk", "name": "Keeper", "def_stat": 50, "overall": 50,
        "consistency": 50, "fitness": 70, "position": "GK",
    }


def _player_map(players: Sequence[Any]) -> dict[str, Any]:
    return {_pid(p): p for p in players}


def run_shootout(
    *,
    home_eligible: Sequence[Any],
    away_eligible: Sequence[Any],
    home_gk: Any,
    away_gk: Any,
    shootout_seed: int,
    existing: PenaltyShootoutState | None = None,
    max_kicks: int = 40,
) -> PenaltyShootoutState:
    """Run or resume a shootout until completion. Deterministic for shootout_seed."""
    order_rng = random.Random(int(shootout_seed))
    state = existing.model_copy(deep=True) if existing else PenaltyShootoutState()

    home_list = list(home_eligible)
    away_list = list(away_eligible)
    if not home_list or not away_list:
        state.completed = True
        state.winner_side = "home" if home_list else "away"
        return state

    if not state.home_taker_order:
        home_order = order_penalty_takers(home_list, order_rng)
        away_order = order_penalty_takers(away_list, order_rng)
        state.home_taker_order = [_pid(p) for p in home_order]
        state.away_taker_order = [_pid(p) for p in away_order]
        state.home_taker_names = {_pid(p): _pname(p) for p in home_order}
        state.away_taker_names = {_pid(p): _pname(p) for p in away_order}

    home_map = _player_map(home_list)
    away_map = _player_map(away_list)

    def _taker(side: str) -> Any:
        order = state.home_taker_order if side == "home" else state.away_taker_order
        idx = state.home_taker_index if side == "home" else state.away_taker_index
        pid = order[idx % len(order)]
        if side == "home":
            state.home_taker_index = idx + 1
        else:
            state.away_taker_index = idx + 1
        fallback = {
            "id": pid,
            "name": (state.home_taker_names if side == "home" else state.away_taker_names).get(
                pid, "Unknown"
            ),
            "sho": 50,
            "overall": 50,
            "consistency": 50,
            "fitness": 70,
        }
        return (home_map if side == "home" else away_map).get(pid) or fallback

    def _take(side: str) -> None:
        seq = len(state.events) + 1
        taker = _taker(side)
        gk = away_gk if side == "home" else home_gk
        ev = resolve_kick(
            taker, gk, sequence=seq, club_side=side, shootout_seed=shootout_seed
        )
        state.events.append(ev)
        if side == "home":
            state.home_kicks_taken += 1
            if ev.outcome == "goal":
                state.home_penalties_scored += 1
        else:
            state.away_kicks_taken += 1
            if ev.outcome == "goal":
                state.away_penalties_scored += 1

    while not state.completed and len(state.events) < max_kicks:
        if state.home_kicks_taken >= 5 and state.away_kicks_taken >= 5:
            if (
                state.home_kicks_taken == state.away_kicks_taken
                and state.home_penalties_scored != state.away_penalties_scored
            ):
                state.winner_side = (
                    "home" if state.home_penalties_scored > state.away_penalties_scored else "away"
                )
                state.completed = True
                break
            state.sudden_death = True

        # Home kick if still in first five or sudden death needs home next
        need_home = (
            (not state.sudden_death and state.home_kicks_taken < 5)
            or (
                state.sudden_death
                and state.home_kicks_taken <= state.away_kicks_taken
            )
        )
        if need_home:
            _take("home")
            winner = _early_winner(state)
            if winner:
                state.winner_side = winner
                state.completed = True
                break

        need_away = (
            (not state.sudden_death and state.away_kicks_taken < 5)
            or (
                state.sudden_death
                and state.away_kicks_taken < state.home_kicks_taken
            )
        )
        if need_away and not state.completed:
            _take("away")
            winner = _early_winner(state)
            if winner:
                state.winner_side = winner
                state.completed = True
                break

    if not state.completed:
        state.winner_side = (
            "home" if state.home_penalties_scored >= state.away_penalties_scored else "away"
        )
        state.completed = True

    return state


def shootout_events_as_compat(
    state: PenaltyShootoutState,
    *,
    home_name: str,
    away_name: str,
    minute: int = 100,
) -> list[dict[str, Any]]:
    """Discord-compat event dicts for stadium streaming (no football score change)."""
    out: list[dict[str, Any]] = []
    score = "0 - 0"  # placeholder; caller overlays football score
    for ev in state.events:
        team = home_name if ev.club_side == "home" else away_name
        out.append({
            "minute": minute,
            "type": "PENALTY_KICK",
            "score_update": score,
            "actor": ev.player_name,
            "team": team,
            "outcome": ev.outcome,
            "sequence": ev.sequence,
            "club_side": ev.club_side,
            "home_penalties": state.home_penalties_scored,
            "away_penalties": state.away_penalties_scored,
        })
    return out
