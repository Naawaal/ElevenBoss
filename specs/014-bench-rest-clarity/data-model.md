# Data Model: Bench Rest Clarity

**Feature**: `014-bench-rest-clarity` | **Date**: 2026-07-12

## Entities

### `match_history` (extend)

| Column | Type | Notes |
|--------|------|-------|
| `fatigue_applied_at` | `TIMESTAMPTZ NULL` | Set after successful `apply_post_match_fitness` for this history row. NULL = fatigue/injury post-process still pending. |

Existing `xp_applied_at` remains the XP gate only.

### Unchanged (reference)

| Entity | Role |
|--------|------|
| `player_cards.fatigue` | 0–100; bench rest `+ fatigue_bench_per_match` via RPC |
| `game_config.fatigue_bench_per_match` | Live **25** |
| `apply_match_fatigue(p_owner_id, p_starter_drains, p_bench_ids)` | Atomic drain + bench bump |

### Bench rest candidate set (logical)

- Owned, not retired, `injury_tier IS NULL`
- Not in starting XI for that match
- Ordered by `overall` DESC, take **7**
- Same IDs used for touchline subs hydration today

## State transitions

```text
match_history row created
  → XP applied → xp_applied_at set
  → fitness RPC ok → fatigue_applied_at set
```

Retry after XP-only success: skip XP, still run fitness if `fatigue_applied_at` is null.

## Validation

- Schema guard / `verify_required_schema.sql`: `column:public.match_history.fatigue_applied_at`
- No backfill required for old rows (NULL = historical; do not re-apply)
