# Contract: Card State Derive

**Feature**: US-42.2

## Pure API (`packages/player_engine/card_state.py`)

```text
derive_primary_state(flags: CardStateFlags) -> PrimaryState
derive_overlay(match_locked: bool) -> set[Overlay]
derive_modifiers(flags) -> set[Modifier]
can_perform_action(primary, overlay, modifiers, action: str) -> tuple[bool, str]
```

`CardStateFlags` (dict or dataclass): retired, in_hospital, injury_tier, in_academy, in_xi, listed, evolving, training_busy, owned_by_viewer.

## Priority

Retired > SoldTransferred > Listed > Hospitalized > Evolving > TrainingBusy > InAcademy > InXI > RosterFree

**Evolving + InXI**: not a conflict (084). Primary label remains `Evolving`; `start_evolution` allowed from `InXI`; `assign_xi` / `match_include` / `bench` allowed while `Evolving` so match tracks can complete.

## Tests

- Each busy flag alone → expected primary  
- InXI + listed conflict detection helper  
- 29d-style N/A — identity lifecycle is 42.1  
