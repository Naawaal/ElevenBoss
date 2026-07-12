# Contract: Fatigue recovery pure math

**Feature**: `009-fatigue-recovery`  
**Module**: `packages/player_engine/player_engine/fatigue.py`

## Constants (defaults; SQL/`game_config` are runtime authority)

| Name | Value |
|------|-------|
| `FATIGUE_PASSIVE_BASE` | 15 |
| `FATIGUE_PASSIVE_TG_PER_LEVEL` | 5 |
| `FATIGUE_RECOVERY_SESSION` | 40 |
| `FATIGUE_HOSPITAL_PER_DAY` | 45 (unchanged) |
| `FATIGUE_BENCH_PER_MATCH` | 15 (unchanged) |
| `FATIGUE_PASSIVE_PER_DAY` | Deprecated alias — prefer `passive_recovery_amount(1) == 20` for TG1 |

## Functions

### `passive_recovery_amount(tg_level: int) -> int`

```text
max(0, FATIGUE_PASSIVE_BASE + max(tg_level, 0) * FATIGUE_PASSIVE_TG_PER_LEVEL)
```

UI/tests may clamp display TG to 1–5 to match schema.

### `apply_passive_recovery(current, *, in_hospital=False, tg_level=1) -> int`

- Hospital: `+ FATIGUE_HOSPITAL_PER_DAY`
- Else: `+ passive_recovery_amount(tg_level)`
- Result clamped to `[0, 100]`

### `apply_recovery_session(current, amount: int = FATIGUE_RECOVERY_SESSION) -> int`

`clamp_fatigue(current + amount)` — no XP side effects (pure).

## Invariants

- Module must not import `discord` or perform IO
- Must not reference `action_energy` (existing fatigue test)
- Bench / drain helpers unchanged

## Tests (`tests/test_fatigue_injury_math.py`)

- `passive_recovery_amount(1) == 20`, `(5) == 40`
- `apply_passive_recovery(0, tg_level=5) == 40`
- `apply_passive_recovery(50, in_hospital=True)` ignores TG (still +45 → 95)
- `apply_recovery_session(70) == 100` (clamp)
- `apply_recovery_session(50) == 90`
