# Contract: fair recalc math (pure)

**Package**: `packages/player_engine/player_engine/injury_math.py`

## Helpers (add)

```python
def new_total_recovery_days(tier: int, hospital_level: int) -> int:
    """CEIL(base / (1 + 0.2 * H)); same as recovery_days_for_tier."""

def fair_hospital_candidate_eta(
    *,
    admission: datetime,
    tier: int,
    hospital_level: int,
) -> datetime:
    """admission + new_total_recovery_days days."""

def fair_hospital_final_eta(
    *,
    admission: datetime,
    current_eta: datetime,
    tier: int,
    hospital_level: int,
) -> datetime:
    """min(current_eta, candidate)."""

def should_early_discharge(*, now: datetime, final_eta: datetime) -> bool:
    return now >= final_eta

def fair_overflow_remaining_days(
    *,
    tier: int,
    injury_started_at: datetime | None,
    current_remaining: int,
    now: datetime,
) -> int:
    """min(current, max(0, ceil(base - elapsed))); base = BASE_RECOVERY_DAYS[tier]."""
```

Reuse `BASE_RECOVERY_DAYS` and `recovery_days_for_tier` where possible (ponytail: thin wrappers OK).

## Tests (`tests/test_injury_eta_backfill.py`)

- Major H0: new_total = 7; candidate = admission + 7d; LEAST with far ETA shortens.
- Never lengthen: current ETA earlier than candidate → keep current.
- Early discharge: now ≥ final → True.
- Overflow: started 6d ago, Major, current remaining 14 → final remaining 1 (7−6); never increase if current already 0.
- Idempotent: final_eta(final_eta as current) == same.
