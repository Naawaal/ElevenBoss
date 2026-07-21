# packages/leagues/leagues/assistant_lineup.py
"""Assistant-manager lineup priority and repair (026) — pure, no Discord."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence


@dataclass(frozen=True)
class LineupPlan:
    source: str  # submitted | saved | repaired | emergency | forfeit
    starter_ids: list[str]
    bench_ids: list[str]
    formation: str | None
    tactics: dict[str, Any] = field(default_factory=dict)
    legal: bool = True
    notes: tuple[str, ...] = ()


def _valid_xi(starter_ids: Sequence[str], *, min_starters: int = 11) -> bool:
    ids = [str(x) for x in starter_ids if x]
    return len(ids) >= min_starters and len(set(ids)) == len(ids)


def repair_lineup(
    preferred_starters: Sequence[str],
    eligible_pool: Sequence[str],
    *,
    formation: str | None = None,
    tactics: dict[str, Any] | None = None,
    min_starters: int = 11,
) -> LineupPlan:
    """
    Fill to ``min_starters`` from eligible pool without inventing new tactics.
    Preserves preferred order; appends best remaining eligible ids.
    """
    tactics = dict(tactics or {})
    preferred = [str(x) for x in preferred_starters if x]
    pool = [str(x) for x in eligible_pool if x]
    pool_set = set(pool)
    starters: list[str] = []
    notes: list[str] = []
    for pid in preferred:
        if pid in pool_set and pid not in starters:
            starters.append(pid)
        elif pid not in pool_set:
            notes.append(f"replaced_ineligible:{pid}")
    for pid in pool:
        if len(starters) >= min_starters:
            break
        if pid not in starters:
            starters.append(pid)
            notes.append(f"filled:{pid}")
    bench = [p for p in pool if p not in starters]
    legal = len(starters) >= min_starters
    source = "repaired" if legal else "forfeit"
    return LineupPlan(
        source=source if legal else "forfeit",
        starter_ids=starters[:min_starters] if legal else starters,
        bench_ids=bench,
        formation=formation,
        tactics=tactics,
        legal=legal,
        notes=tuple(notes),
    )


def select_lineup_plan(
    *,
    submitted_starters: Sequence[str] | None,
    saved_starters: Sequence[str] | None,
    eligible_pool: Sequence[str],
    formation: str | None = None,
    tactics: dict[str, Any] | None = None,
    min_starters: int = 11,
) -> LineupPlan:
    """
    Priority: submitted → saved → repaired → emergency → forfeit.
    """
    tactics = dict(tactics or {})
    pool = [str(x) for x in eligible_pool if x]

    if submitted_starters and _valid_xi(submitted_starters, min_starters=min_starters):
        # Still drop ineligible
        cleaned = [s for s in submitted_starters if str(s) in set(pool)]
        if _valid_xi(cleaned, min_starters=min_starters):
            return LineupPlan(
                source="submitted",
                starter_ids=[str(s) for s in cleaned][:min_starters],
                bench_ids=[p for p in pool if p not in cleaned],
                formation=formation,
                tactics=tactics,
                legal=True,
            )
        return repair_lineup(
            cleaned, pool, formation=formation, tactics=tactics, min_starters=min_starters
        )

    if saved_starters and _valid_xi(saved_starters, min_starters=min_starters):
        cleaned = [s for s in saved_starters if str(s) in set(pool)]
        if _valid_xi(cleaned, min_starters=min_starters):
            return LineupPlan(
                source="saved",
                starter_ids=[str(s) for s in cleaned][:min_starters],
                bench_ids=[p for p in pool if p not in cleaned],
                formation=formation,
                tactics=tactics,
                legal=True,
            )
        return repair_lineup(
            cleaned, pool, formation=formation, tactics=tactics, min_starters=min_starters
        )

    # Emergency: best available from pool only
    emergency = repair_lineup([], pool, formation=formation, tactics=tactics, min_starters=min_starters)
    if emergency.legal:
        return LineupPlan(
            source="emergency",
            starter_ids=emergency.starter_ids,
            bench_ids=emergency.bench_ids,
            formation=formation,
            tactics=tactics,
            legal=True,
            notes=emergency.notes + ("emergency_xi",),
        )
    return LineupPlan(
        source="forfeit",
        starter_ids=[],
        bench_ids=[],
        formation=formation,
        tactics=tactics,
        legal=False,
        notes=("no_legal_team",),
    )
