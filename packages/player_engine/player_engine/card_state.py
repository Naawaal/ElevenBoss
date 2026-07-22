"""US-42.2 player-card primary state derive + action matrix (pure)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

PrimaryState = Literal[
    "RosterFree",
    "InXI",
    "Listed",
    "Evolving",
    "Hospitalized",
    "TrainingBusy",
    "InAcademy",
    "Retired",
    "SoldTransferred",
]

Overlay = Literal["MatchLocked"]
Modifier = Literal["InjuryPlayOn", "FatigueBand", "ContractGate"]

ActionCode = Literal[
    "view_profile",
    "assign_xi",
    "bench",
    "match_include",
    "drill",
    "fusion",
    "allocate",
    "recover_fatigue",
    "start_evolution",
    "claim_evolution",
    "cancel_evolution",
    "admit_hospital",
    "discharge_hospital",
    "list_transfer",
    "cancel_listing",
    "agent_sell",
    "academy_seat",
    "academy_promote",
    "academy_release",
    "retire",
]

# Spec §B.5 — primaries that Allow each action (View counted as Allow for gating).
_ALLOWED: dict[str, frozenset[str]] = {
    "view_profile": frozenset(
        {
            "RosterFree",
            "InXI",
            "Listed",
            "Evolving",
            "Hospitalized",
            "TrainingBusy",
            "InAcademy",
            "Retired",
        }
    ),
    "assign_xi": frozenset({"RosterFree"}),
    "bench": frozenset({"InXI"}),
    "match_include": frozenset({"RosterFree", "InXI"}),
    "drill": frozenset({"RosterFree", "InXI"}),
    "fusion": frozenset({"RosterFree"}),
    "allocate": frozenset({"RosterFree", "InXI"}),
    "recover_fatigue": frozenset({"RosterFree", "InXI"}),
    "start_evolution": frozenset({"RosterFree"}),
    "claim_evolution": frozenset({"Evolving"}),
    "cancel_evolution": frozenset({"Evolving"}),
    "admit_hospital": frozenset({"RosterFree"}),
    "discharge_hospital": frozenset({"Hospitalized"}),
    "list_transfer": frozenset({"RosterFree"}),
    "cancel_listing": frozenset({"Listed"}),
    "agent_sell": frozenset({"RosterFree"}),
    "academy_seat": frozenset({"RosterFree"}),
    "academy_promote": frozenset({"InAcademy"}),
    "academy_release": frozenset({"InAcademy"}),
    "retire": frozenset({"RosterFree", "InXI"}),
}

_MUTATIONS = frozenset(a for a in _ALLOWED if a != "view_profile")

_BUSY_EXCLUSIVE = (
    "listed",
    "in_hospital",
    "evolving",
    "training_busy",
    "in_academy",
    "retired",
)


@dataclass(frozen=True)
class CardStateFlags:
    retired: bool = False
    in_hospital: bool = False
    injury_tier: int | None = None
    in_academy: bool = False
    in_xi: bool = False
    listed: bool = False
    evolving: bool = False
    training_busy: bool = False
    owned_by_viewer: bool = True
    fatigue: int = 100


def derive_primary_state(flags: CardStateFlags) -> PrimaryState:
    """Classify primary exclusive state (priority order; ignores conflict for label)."""
    if flags.retired:
        return "Retired"
    if not flags.owned_by_viewer:
        return "SoldTransferred"
    if flags.listed:
        return "Listed"
    if flags.in_hospital:
        return "Hospitalized"
    if flags.evolving:
        return "Evolving"
    if flags.training_busy:
        return "TrainingBusy"
    if flags.in_academy:
        return "InAcademy"
    if flags.in_xi:
        return "InXI"
    return "RosterFree"


def exclusive_busy_proofs(flags: CardStateFlags) -> list[str]:
    """Busy exclusive labels present (excluding InXI / Sold)."""
    out: list[str] = []
    if flags.retired:
        out.append("Retired")
    if flags.listed:
        out.append("Listed")
    if flags.in_hospital:
        out.append("Hospitalized")
    if flags.evolving:
        out.append("Evolving")
    if flags.training_busy:
        out.append("TrainingBusy")
    if flags.in_academy:
        out.append("InAcademy")
    return out


def has_exclusive_conflict(flags: CardStateFlags) -> bool:
    """True when mutually exclusive busy proofs coexist (or busy + InXI)."""
    proofs = exclusive_busy_proofs(flags)
    if len(proofs) > 1:
        return True
    if proofs and flags.in_xi:
        return True
    return False


def detect_exclusive_conflict(flags: CardStateFlags) -> str | None:
    """Return conflict reason or None."""
    if not has_exclusive_conflict(flags):
        return None
    proofs = exclusive_busy_proofs(flags)
    if flags.in_xi:
        proofs = [*proofs, "InXI"]
    return "state_conflict:" + "+".join(proofs)


def derive_overlay(*, match_locked: bool) -> set[Overlay]:
    return {"MatchLocked"} if match_locked else set()


def derive_modifiers(flags: CardStateFlags) -> set[Modifier]:
    mods: set[Modifier] = set()
    if flags.injury_tier is not None and not flags.in_hospital:
        mods.add("InjuryPlayOn")
    # ponytail: fatigue band is informational; matrix does not Block list on fatigue alone
    if flags.fatigue < 100:
        mods.add("FatigueBand")
    return mods


def can_perform_action(
    primary: PrimaryState,
    *,
    match_locked: bool = False,
    injury_tier: int | None = None,
    in_hospital: bool = False,
    action: str,
    conflict: bool = False,
) -> tuple[bool, str]:
    """
    Matrix gate. Returns (allowed, reason).
    reason is '' when allowed; otherwise a stable family string.
    """
    if conflict:
        return False, "state_conflict"

    if primary == "SoldTransferred" and action != "view_profile":
        return False, "CARD_STATE: SoldTransferred blocks " + action
    if primary == "SoldTransferred" and action == "view_profile":
        return False, "CARD_STATE: SoldTransferred blocks view_profile"

    if match_locked and action in _MUTATIONS:
        return False, "CARD_STATE: MatchLocked blocks " + action

    allowed = _ALLOWED.get(action)
    if allowed is None:
        # Default: Block if busy exclusive or MatchLocked; else only RosterFree/InXI
        if primary in (
            "Listed",
            "Hospitalized",
            "Evolving",
            "TrainingBusy",
            "InAcademy",
            "Retired",
            "SoldTransferred",
        ):
            return False, f"CARD_STATE: {primary} blocks {action}"
        if primary in ("RosterFree", "InXI"):
            return True, ""
        return False, f"CARD_STATE: {primary} blocks {action}"

    if primary not in allowed:
        return False, f"CARD_STATE: {primary} blocks {action}"

    # Injury modifier — list / agent sell (align 017); hospital already blocks via primary
    if action in ("list_transfer", "agent_sell"):
        if injury_tier is not None or in_hospital:
            return False, "CARD_STATE: injury blocks " + action

    return True, ""


def can_perform_action_from_flags(
    flags: CardStateFlags,
    *,
    match_locked: bool = False,
    action: str,
) -> tuple[bool, str]:
    """Convenience: conflict → primary → matrix."""
    conflict_reason = detect_exclusive_conflict(flags)
    primary = derive_primary_state(flags)
    return can_perform_action(
        primary,
        match_locked=match_locked,
        injury_tier=flags.injury_tier,
        in_hospital=flags.in_hospital,
        action=action,
        conflict=conflict_reason is not None,
    )
