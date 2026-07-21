# packages/match_engine/match_engine/squad_validation.py
"""Squad lineup validation helpers (pure logic)."""
from __future__ import annotations

from typing import Any

from .formation_positions import get_slot_role


def reserve_fits_formation_slot(formation: str, slot: int, position: str) -> bool:
    """Return True when a reserve's broad position matches the formation slot role."""
    return position == get_slot_role(formation, slot)


def _card_id(card: dict[str, Any]) -> Any:
    return card["id"]


def _sort_by_ovr(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(cards, key=lambda c: int(c.get("overall", 0)), reverse=True)


def reassign_formation_slots(
    formation: str,
    current_assignments: dict[int, dict[str, Any]],
    all_eligible_cards: list[dict[str, Any]],
) -> dict[int, dict[str, Any]]:
    """Preserve current starters where possible; bench fills only empty slots."""
    starter_ids = {_card_id(c) for c in current_assignments.values()}
    used: set[Any] = set()
    result: dict[int, dict[str, Any]] = {}

    # Keep starters in the same slot when they still fit the new formation.
    for slot in range(1, 12):
        card = current_assignments.get(slot)
        if not card or _card_id(card) in used:
            continue
        if slot == 1 and card.get("position") != "GK":
            continue
        if reserve_fits_formation_slot(formation, slot, str(card.get("position") or "")):
            result[slot] = card
            used.add(_card_id(card))

    unused_starters = [
        c for c in all_eligible_cards if _card_id(c) in starter_ids and _card_id(c) not in used
    ]
    bench = [c for c in all_eligible_cards if _card_id(c) not in starter_ids]

    def _pick(pool: list[dict[str, Any]], slot: int) -> dict[str, Any] | None:
        if slot == 1:
            gks = [c for c in pool if c.get("position") == "GK" and _card_id(c) not in used]
            if not gks:
                return None
            pick = _sort_by_ovr(gks)[0]
            used.add(_card_id(pick))
            return pick
        role_matches = [
            c
            for c in pool
            if _card_id(c) not in used
            and reserve_fits_formation_slot(formation, slot, str(c.get("position") or ""))
        ]
        if role_matches:
            pick = _sort_by_ovr(role_matches)[0]
            used.add(_card_id(pick))
            return pick
        remaining = [c for c in pool if _card_id(c) not in used]
        if not remaining:
            return None
        pick = _sort_by_ovr(remaining)[0]
        used.add(_card_id(pick))
        return pick

    for slot in range(1, 12):
        if slot in result:
            continue
        pick = _pick(unused_starters, slot)
        if pick:
            result[slot] = pick

    for slot in range(1, 12):
        if slot in result:
            continue
        pick = _pick(bench, slot)
        if pick:
            result[slot] = pick

    return result
