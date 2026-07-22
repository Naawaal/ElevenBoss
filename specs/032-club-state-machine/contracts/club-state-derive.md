# Contract: Club State Derive

**Feature**: US-42.3

## Pure API (`packages/player_engine/club_state.py`)

```text
ClubKind = Human | AI
SoftLifecycle = Active | Inactive | Abandoned

derive_club_kind(is_ai: bool) -> ClubKind
derive_soft_lifecycle(flags) -> SoftLifecycle   # reuse identity.classify_status
derive_overlays(*, match_locked, seated_season_ids) -> set[str]
can_perform_club_action(soft, kind, overlays, action) -> tuple[bool, str]
```

## Priority / stacking

1. Kind AI → Block human hub mutations / league_join (view optional for ops)
2. Soft Abandoned/Inactive → Block `league_join` only among competitive **entry** actions (matrix)
3. MatchLocked → Block mutations per matrix
4. LeagueSeated → idempotent Allow for same season join (AlreadySeated), does not Block development

## Tests

- Soft thresholds mirror `identity.py` (30/90)
- Inactive × league_join Block; Inactive × store_faucet Allow
- AI × league_join Block
- MatchLocked × match_start Block; view Allow
