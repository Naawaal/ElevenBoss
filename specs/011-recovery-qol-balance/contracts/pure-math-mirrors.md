# Contract: pure math mirrors

**Package**: `packages/player_engine`

## `fatigue.py`

| Symbol | New default | Notes |
|--------|-------------|-------|
| `FATIGUE_BASE_DRAIN` | `18` | Used by `match_fatigue_drain` → Discord match path |
| `FATIGUE_PASSIVE_BASE` | `25` | `passive_recovery_amount` |
| `FATIGUE_PASSIVE_TG_PER_LEVEL` | `5` | unchanged |
| `FATIGUE_BENCH_PER_MATCH` | `25` | `apply_bench_rest` default |
| `FATIGUE_PASSIVE_PER_DAY` | `30` | Deprecated alias = base + 1×TG |

Update docstring example for `match_fatigue_drain` to PHY70 / attack / intensity → **21**.

## `injury_math.py`

| Symbol | New value |
|--------|-----------|
| `BASE_RECOVERY_DAYS` | `{1: 1, 2: 4, 3: 7}` |

## Tests (`tests/test_fatigue_injury_math.py`)

Must assert:

- `match_fatigue_drain(70, stance="attack", intensity=True) == 21`
- `passive_recovery_amount(1) == 30`, `(3) == 40`, `(5) == 50`
- `FATIGUE_BENCH_PER_MATCH == 25` (or bench rest from 80 → 100)
- `recovery_days_for_tier(1, 0) == 1`
- `recovery_days_for_tier(2, 3) == 3`  # ceil(4/1.6)
- `recovery_days_for_tier(3, 0) == 7`

## Discord

No cog changes required unless copy hardcodes old numbers (current audit: none). Drain ships via bot deploy of updated package.
