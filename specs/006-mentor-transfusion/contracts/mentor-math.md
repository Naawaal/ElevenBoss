# Contract: Mentor Math (pure)

**Module**: `packages/player_engine/player_engine/mentor_math.py`  
**Feature**: `006-mentor-transfusion`

## Constants

| Name | Value |
|------|-------|
| `SP_PER_MENTOR_UNIT` | `5` |
| `XP_PER_MENTOR_UNIT` | `500` |
| `MENTOR_TRANSFERS_DAILY_LIMIT` | `3` |

Must match SQL RPC body literals.

## Functions (expected)

### `sp_to_mentor_units(skill_points: int) -> int`

`max(0, skill_points // 5)`.

### `mentor_units_to_sp(units: int) -> int` / `mentor_units_to_xp(units: int) -> int`

`units * 5` / `units * 500` for `units >= 0`; invalid negative → treat as 0 or raise in typed helper (prefer clamp for UI, raise for RPC mirror tests).

### `is_mentor_source(overall: int, potential: int, skill_points: int) -> bool`

`overall >= potential and skill_points >= 5`.

### `is_mentor_target(overall: int, potential: int, level: int, *, source_id, target_id) -> bool`

`target_id != source_id and overall < potential and level < L_MAX` (import `L_MAX` from progression).

### `xp_headroom_to_max(current_xp: int) -> int`

`max(0, cumulative_xp_for_level(L_MAX) - current_xp)`.

### `mentor_max_units(source_sp: int, target_xp: int) -> int`

`min(sp_to_mentor_units(source_sp), xp_headroom_to_max(target_xp) // XP_PER_MENTOR_UNIT)`.

### `preview_mentor_transfer(source_sp, target_xp, units) -> preview`

Uses `simulate_apply_card_xp(target_xp, units * 500)`. If `units < 1` or `units > mentor_max_units(...)` or result `xp_wasted > 0`, mark invalid.

## Non-goals

- No Discord imports
- No DB IO
- Does not allocate stats or call allocate gates (separate concern)
