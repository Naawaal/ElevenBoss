# Contract: Aging Decline Curve

**Modules**: `packages/player_engine/player_engine/age_manager.py` (`yearly_stat_decline`)  
**SQL**: `process_season_aging` body (migration `053`)  
**Feature**: `007-retirement-lifecycle-fixes`

## Per birthday-year deltas

Applied once per advanced year `A` (when cached age increases). Empty map if `A < 31`.

| Condition | pac | phy | pas | def | dri | sho |
|-----------|-----|-----|-----|-----|-----|-----|
| `31 ≤ A ≤ 32` | −1 | −1 | 0 | 0 | 0 | 0 |
| `33 ≤ A ≤ 34` | −1 | −1 | −1 | −1 | **−1** | 0 |
| `A ≥ 35` | −2 | −2 | −1 | −1 | **−1** | **−1** |

Floor: each attribute `GREATEST(1, value + delta)` (SQL) / `max(1, …)` (Python).

After each year in the SQL loop: `recalculate_card_ovr(card_id)`.

## Python API

```text
yearly_stat_decline(age: int) -> dict[str, int]
```

- Keys present only when non-zero **or** always include the six keys with zeros — prefer **only non-zero keys** for backward-compatible tests, but tests must assert DRI at 33 and SHO at 35.
- Must match the table above for ages 31, 33, 35, 36.

## Non-goals

- Changing retirement_age / warning_age / DOB math
- Declining potential or rarity
- Discord imports
