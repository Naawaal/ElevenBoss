# Contract: Academy Growth Math

**Feature**: `015-youth-academy`  
**Pure module**: `packages/player_engine/player_engine/youth_math.py`  
**RPC mirror**: `process_daily_academy_growth`

## Constants

| Name | Value |
|------|-------|
| `POINTS_PER_OVR` | 100 |
| `READY_OVR_DEFAULT` | 65 |
| `AGE_OUT_DEFAULT` | 20 |

## Functions (pure)

### `academy_daily_points(academy_level: int, potential: int) -> int`

```text
level = clamp(academy_level, 1, 5)
return 10 + (5 * level) + (potential // 25)
```

### `apply_academy_tick(overall, potential, progress, academy_level, stats, position) -> GrowthResult`

- Add `academy_daily_points` to `progress`.
- While `progress >= 100` and `overall < potential`: `overall += 1`, `progress -= 100`, apply one weighted stat bump (PAC/SHO/PAS/DRI/DEF/PHY) using existing position weight spirit; each stat capped at `potential`.
- Return new overall, progress, stats, `ovr_gained`, `is_ready` (`overall >= ready_ovr`).

### `star_band(potential: int) -> int`

| POT | Stars |
|-----|-------|
| &lt; 75 | 1 |
| 75–79 | 2 |
| 80–84 | 3 |
| 85–89 | 4 |
| ≥ 90 | 5 |

### `is_promotion_ready(overall: int, ready_ovr: int = 65) -> bool`

### `should_age_out(age: int, age_out: int = 20) -> bool`

## Non-goals

- Must **not** call or emulate `apply_card_xp`.
- Must **not** grant `skill_points` during academy.

## Tests

- Monotonic: L5 daily points &gt; L1 for same POT.
- Cap: never `overall > potential`.
- Ready flag at 65.
- Age-out at 20 true, at 19 false.
