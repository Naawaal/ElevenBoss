# packages/match_engine/match_engine/substitution_resolve.py
"""Pure in-match injury substitution helpers (Phase 3). No Discord / DB."""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Literal, Sequence

MAX_SUBS_PER_MATCH = 3
PLAY_ON_TIER_UPGRADE_CHANCE = 0.60
COMPROMISED_PHASE_MULT = 0.50
EMERGENCY_GK_DEF_MULT = 0.60

ResolutionKind = Literal["sub", "play_on", "ten_men", "emergency_gk"]

_POSITION_GROUP: dict[str, str] = {
    "GK": "gk",
    "DEF": "defense", "CB": "defense", "LB": "defense", "RB": "defense",
    "LWB": "defense", "RWB": "defense",
    "MID": "midfield", "CM": "midfield", "CDM": "midfield",
    "CAM": "midfield", "LM": "midfield", "RM": "midfield",
    "FWD": "attack", "ST": "attack", "CF": "attack",
    "LW": "attack", "RW": "attack",
}


def _pos(p: Any) -> str:
    raw = p.position if hasattr(p, "position") else p.get("position", "MID")
    return str(raw).upper()


def _ovr(p: Any) -> int:
    return int(p.overall if hasattr(p, "overall") else p.get("overall", 50))


def _cid(p: Any) -> str | None:
    if hasattr(p, "card_id"):
        return str(p.card_id) if p.card_id else None
    if isinstance(p, dict):
        if p.get("id"):
            return str(p["id"])
        if p.get("card_id"):
            return str(p["card_id"])
    return None


def _name(p: Any) -> str:
    return str(p.name if hasattr(p, "name") else p.get("name", "Player"))


def position_group(position: str) -> str:
    return _POSITION_GROUP.get(str(position).upper(), "midfield")


@dataclass
class SubResolution:
    kind: ResolutionKind
    injured_card_id: str | None
    replacement_card_id: str | None = None
    tier: int = 1
    side: str = "home"
    play_on: bool = False


def auto_pick_bench(
    bench: Sequence[Any],
    injured_position: str,
) -> Any | None:
    """Prefer same position group, then highest overall. None if empty."""
    if not bench:
        return None
    want = position_group(injured_position)
    same = [p for p in bench if position_group(_pos(p)) == want]
    pool = same or list(bench)
    return max(pool, key=_ovr)


def apply_sub(
    squad: list,
    bench: list,
    injured_id: str,
    replacement_id: str,
) -> tuple[list, list]:
    """Bring replacement on; remove injured from pitch."""
    injured = next((p for p in squad if _cid(p) == injured_id), None)
    replacement = next((p for p in bench if _cid(p) == replacement_id), None)
    if injured is None or replacement is None:
        return squad, bench
    new_squad = [p for p in squad if _cid(p) != injured_id] + [replacement]
    new_bench = [p for p in bench if _cid(p) != replacement_id]
    return new_squad, new_bench


def apply_ten_men(squad: list, injured_id: str) -> list:
    return [p for p in squad if _cid(p) != injured_id]


def emergency_gk_card(outfield: Sequence[Any]) -> Any | None:
    """Highest-OVR outfield player pressed into GK (caller sets penalty flag)."""
    candidates = [p for p in outfield if position_group(_pos(p)) != "gk"]
    if not candidates:
        return None
    return max(candidates, key=_ovr)


def play_on_tier_upgrade(tier: int, rng: random.Random | None = None) -> int:
    """+60% chance tier += 1, cap Major (3)."""
    r = rng or random.Random()
    t = max(1, min(3, int(tier)))
    if r.random() < PLAY_ON_TIER_UPGRADE_CHANCE and t < 3:
        return t + 1
    return t


def is_gk(player: Any) -> bool:
    return position_group(_pos(player)) == "gk"


def auto_resolve_injury(
    *,
    side: str,
    injured: Any,
    bench: Sequence[Any],
    squad: Sequence[Any],
    subs_used: int,
    tier: int,
    rng: random.Random | None = None,
) -> SubResolution:
    """
    AI / timeout / silent-sim decision:
    - GK + GK on bench → auto-sub that GK
    - GK + no GK → emergency outfield GK
    - Subs left + bench → auto-pick
    - Else → ten men
    """
    injured_id = _cid(injured) or ""

    if is_gk(injured):
        gk_bench = [p for p in bench if is_gk(p)]
        if gk_bench and subs_used < MAX_SUBS_PER_MATCH:
            pick = max(gk_bench, key=_ovr)
            return SubResolution(
                kind="sub",
                injured_card_id=injured_id,
                replacement_card_id=_cid(pick),
                tier=tier,
                side=side,
            )
        em = emergency_gk_card([p for p in squad if _cid(p) != injured_id])
        if em is not None and subs_used < MAX_SUBS_PER_MATCH:
            return SubResolution(
                kind="emergency_gk",
                injured_card_id=injured_id,
                replacement_card_id=_cid(em),
                tier=tier,
                side=side,
            )
        return SubResolution(
            kind="ten_men",
            injured_card_id=injured_id,
            tier=tier,
            side=side,
        )

    if subs_used < MAX_SUBS_PER_MATCH and bench:
        pick = auto_pick_bench(bench, _pos(injured))
        if pick is not None:
            return SubResolution(
                kind="sub",
                injured_card_id=injured_id,
                replacement_card_id=_cid(pick),
                tier=tier,
                side=side,
            )

    return SubResolution(
        kind="ten_men",
        injured_card_id=injured_id,
        tier=tier,
        side=side,
    )


def bench_options_payload(bench: Sequence[Any]) -> list[dict[str, Any]]:
    rows = []
    for p in bench:
        rows.append({
            "card_id": _cid(p),
            "name": _name(p),
            "position": _pos(p),
            "overall": _ovr(p),
            "fatigue": int(
                getattr(p, "fatigue", None)
                or (p.get("fatigue", 100) if isinstance(p, dict) else 100)
            ),
        })
    rows.sort(key=lambda x: (-x["fatigue"], -x["overall"]))
    return rows
