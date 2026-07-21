# tests/test_assistant_lineup_priority.py
from __future__ import annotations

from leagues.assistant_lineup import repair_lineup, select_lineup_plan


def _pool(n: int = 14) -> list[str]:
    return [f"p{i}" for i in range(n)]


def test_submitted_beats_saved():
    pool = _pool()
    plan = select_lineup_plan(
        submitted_starters=pool[:11],
        saved_starters=pool[1:12],
        eligible_pool=pool,
        formation="4-3-3",
        tactics={"press": "high"},
    )
    assert plan.source == "submitted"
    assert plan.legal
    assert plan.formation == "4-3-3"
    assert plan.tactics.get("press") == "high"


def test_saved_when_no_submitted():
    pool = _pool()
    plan = select_lineup_plan(
        submitted_starters=None,
        saved_starters=pool[:11],
        eligible_pool=pool,
    )
    assert plan.source == "saved"
    assert len(plan.starter_ids) == 11


def test_repair_replaces_ineligible_preserves_tactics():
    pool = _pool()
    plan = repair_lineup(
        ["injured"] + pool[:10],
        pool,
        formation="4-4-2",
        tactics={"style": "counter"},
    )
    assert plan.legal
    assert plan.source == "repaired"
    assert "injured" not in plan.starter_ids
    assert plan.tactics.get("style") == "counter"


def test_forfeit_when_pool_too_small():
    plan = select_lineup_plan(
        submitted_starters=None,
        saved_starters=None,
        eligible_pool=["a", "b", "c"],
    )
    assert plan.legal is False
    assert plan.source == "forfeit"


def test_emergency_from_pool_only():
    pool = _pool()
    plan = select_lineup_plan(
        submitted_starters=["x"] * 11,  # all ineligible → repair/emergency
        saved_starters=None,
        eligible_pool=pool,
    )
    assert plan.legal
    assert plan.source in ("repaired", "emergency", "submitted")
