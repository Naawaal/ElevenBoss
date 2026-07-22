# Data Model: League Integrity (US-42.5)

**Informative overlay** on existing `026`/`070` tables — no parallel season stack.

## Entities

### LeagueSeason (existing)

| Field (relevant) | Integrity use |
|------------------|---------------|
| `id` | Season key |
| `status` | `active` / `paused` / open registration statuses / `completed` / `cancelled` / `failed` |
| `pause_started_at` | **Required** when entering `paused` for rebase |
| `total_paused_seconds` | Accumulated pause on resume |
| `config_json.promo_applied` | Promo once flag |
| `phase_deadlines` / matchday links | Sporting schedule (`026`) |

**Rules**: Entering `paused` without `pause_started_at` is invalid for integrity. Terminal statuses never receive new prizes.

### LifecycleOperation (`league_operation_runs`)

| Field | Integrity use |
|-------|---------------|
| `operation_key` | Unique lease for one logical transition |
| `status` | started / succeeded / failed |
| Retryable fail | Row deleted so catch-up can re-acquire |

### FixtureResult (`league_fixtures`)

| Field | Integrity use |
|-------|---------------|
| `is_played` | Skip deadline / second Play |
| `result_type` / `resolved_by` | Sporting path (play / forfeit / auto_sim) |
| `window_*` | Rebased on resume for unplayed |

### PrizeSettlement

Logical: one season settlement. Durable: `league_season_awards` + `apply_club_economy` keys `season_prize:{season_id}:{player_id}` (+ refund keys). Humans only (`is_ai = FALSE`).

### LeagueSeat

`league_registrations` / participants — unique season×club; soft lifecycle gate on **new** join (US-42.3). Leave guild does not delete club row.

### SeasonPause (logical)

| Event | Writes |
|-------|--------|
| Pause | `status=paused`, `pause_started_at=now` |
| Resume | Rebase open matchday/fixture windows by delta; clear `pause_started_at`; add to `total_paused_seconds`; `status=active` |

## Relationships

```text
LeagueSeason 1──* LifecycleOperation
LeagueSeason 1──* FixtureResult
LeagueSeason 1──* Prize awards (humans)
Club ──(seat)── LeagueSeason (≤1 active per rules)
```

## Validation rules

1. Pause ⇒ `pause_started_at` NOT NULL while `status=paused` (after fix).
2. Prize economy key unique per season×player.
3. Promo apply short-circuits when `promo_applied`.
4. Fixture resolve requires `is_played=false` (and no active run).
