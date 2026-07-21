# Data Model: League Lifecycle Rulebook V1

**Feature**: `026-league-lifecycle-rulebook` | **Date**: 2026-07-21  
**Migration**: `070_league_lifecycle_v1.sql` (next after `069_topgg_vote_pack.sql`)

## Design principles

1. Separate **permanent membership** from **season registration** and **season participation**.
2. Freeze schedule + ruleset on the season row; never depend on live guild settings mid-season.
3. Every competitive mutation is an **idempotent operation** with an audit journal entry.
4. Discord presentation is an **outbox**, not a side effect inside settle transactions.
5. Grandfather 020/021 rows; V1 columns nullable or defaulted so legacy seasons keep working.

---

## Entities

### GuildConfig (`guild_config` — alter)

| Field | Type | Notes |
|-------|------|-------|
| `league_timezone` | TEXT NULL | IANA e.g. `Asia/Kathmandu`; required before V1 season prepare |
| `league_resolution_hour_local` | SMALLINT NULL | 0–23 local hour; required before V1 prepare |
| `league_lifecycle_v1_enabled` | BOOLEAN NULL | NULL = inherit global; true/false override (Q3 cutover) |
| existing announce / automation columns | — | Reuse channel/role; 021 automation becomes wake-up |

### GameConfig keys (seed)

| Key | Default | Meaning |
|-----|---------|---------|
| `league_lifecycle_v1_enabled` | `false` | Global master cutover flag |
| `league_lifecycle_min_humans` | `4` | Min humans to enter preparing (FR-004) |
| `league_lifecycle_registration_hours` | `48` | Registration phase |
| `league_lifecycle_preparation_hours` | `24` | Preparation phase |
| `league_lifecycle_settlement_hours` | `24` | Settlement phase |
| `league_lifecycle_offseason_hours` | `72` | Offseason before next registration |
| `league_lifecycle_default_resolution_hour` | `20` | Default local hour when guild unset |
| `league_lifecycle_promo_min_eligible_matches` | `7` | Min non-double-forfeit matches for promo eligibility |
| `league_lifecycle_wake_minutes` | `5` | Scheduler wake interval (ops) |

Helper: `league_lifecycle_v1_enabled() RETURNS BOOLEAN`.

### LeagueMembership (evolve `league_members`)

Prefer alter `league_members` over a parallel table (Ponytail):

| Field | Type | Notes |
|-------|------|-------|
| `guild_id`, `player_id` | PK | Existing |
| `seasonal_division_tier` | INT | Existing — maps to current_division_level |
| `status` | TEXT | `active` \| `inactive` \| `banned` (default active) |
| `auto_register` | BOOLEAN | Default false — V1 optional |
| `inactivity_count` | INT | Offseason replacement heuristic |
| `registered_at` / joined | — | Existing |

### LeagueRegistration (`league_registrations` — new)

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID PK | |
| `season_id` | UUID FK → league_seasons | |
| `player_id` | BIGINT FK → players | |
| `registered_at` | TIMESTAMPTZ | |
| `status` | TEXT | `registered` \| `withdrawn` \| `rejected` \| `locked` |
| `eligibility_snapshot` | JSONB | Matches / account age at signup |
| `deposit_status` | TEXT | `pending` \| `charged` \| `refunded` \| `waived` |
| `deposit_amount` | BIGINT | |

UNIQUE `(season_id, player_id)`.

### LeagueSeason (`league_seasons` — alter)

| Field | Type | Notes |
|-------|------|-------|
| `status` | TEXT | Expand check: dormant, registration_open, registration_locked, preparing, active, paused, settling, completed, cancelled, failed |
| `ruleset_version` | TEXT | e.g. `lifecycle-v1` |
| `engine_version` | TEXT | Deployed engine identifier |
| `ruleset_snapshot` | JSONB | Immutable copy of tunables + DST rule text |
| `timezone` | TEXT | Frozen IANA |
| `resolution_hour_local` | SMALLINT | Frozen 0–23 |
| `phase_deadlines` | JSONB | registration/preparation/settlement/offseason ends (UTC) |
| `pause_started_at` | TIMESTAMPTZ NULL | For rebase math |
| `total_paused_seconds` | BIGINT | Accumulator |
| existing | pacing_mode, config_json, threads… | Grandfather Dynamics; V1 seasons set `pacing_mode='lifecycle_v1'` or equivalent check addition |

### LeagueDivision (`league_divisions` — new)

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID PK | |
| `season_id` | UUID FK | |
| `tier` | INT | 1 = top |
| `bot_rating_snapshot` | NUMERIC NULL | Season-start bot strength |

UNIQUE `(season_id, tier)`.

### LeagueParticipant (`league_participants` — alter)

| Field | Type | Notes |
|-------|------|-------|
| `division_id` | UUID NULL FK | Prefer over only `division_tier` long-term; keep `division_tier` synced for hub queries |
| `participant_type` | TEXT | `human` \| `bot` (derive from `players.is_ai` if needed, but store for finals) |
| `seed` | INT NULL | Seating order |
| existing | entry_fee_paid, is_active… | |

### LeagueMatchday (`league_matchdays` — new)

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID PK | |
| `season_id` | UUID FK | |
| `division_id` | UUID FK | Per-division matchday rows **or** season-global number with division scoped fixtures — prefer **season_id + matchday_number** shared calendar across divisions for Discord ritual; fixtures still per division |
| `matchday_number` | INT | 1–14 |
| `window_start` | TIMESTAMPTZ | UTC precomputed |
| `window_end` | TIMESTAMPTZ | UTC precomputed (= resolution instant) |
| `status` | TEXT | scheduled \| open \| closing_soon \| locked \| resolving \| completed \| resolution_failed |
| `reminder_sent_at` | TIMESTAMPTZ NULL | |

UNIQUE `(season_id, matchday_number)`.

### LeagueFixture (`league_fixtures` — alter)

| Field | Type | Notes |
|-------|------|-------|
| `matchday_id` | UUID NULL FK | Link to league_matchdays |
| `status` | TEXT | scheduled \| available \| running \| settling \| settled \| forfeit \| void \| failed_retryable |
| `result_type` | TEXT NULL | `settled` \| `forfeit` \| `double_forfeit` \| `void` |
| `match_seed` | TEXT/BYTEA NULL | Reproducibility |
| `engine_version` | TEXT NULL | |
| `ruleset_version` | TEXT NULL | |
| `squad_snapshot_home` / `away` | JSONB NULL | Or reuse match_runs snapshots |
| `resolved_by` | — | Keep: manual \| auto_sim \| forfeit_engine |
| existing scores / windows / is_played | — | `is_played` true iff terminal sporting |

### LeagueFinalStanding (`league_final_standings` — new)

| Field | Type | Notes |
|-------|------|-------|
| `season_id`, `division_id`, `player_id` | composite unique | Immutable after settle |
| `position`, `played`, `won`, `drawn`, `lost`, `gf`, `ga`, `gd`, `points` | INT | double_forfeit → lost+1, points+0 |
| `movement` | TEXT | `champion` \| `promoted` \| `stayed` \| `relegated` \| `none` |
| `participant_type` | TEXT | human \| bot |

### LeagueTransitionJournal (`league_transition_journal` — new)

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID PK | |
| `season_id` | UUID NULL | |
| `transition` | TEXT | e.g. `REGISTRATION_LOCKED_TO_PREPARING` |
| `operation_key` | TEXT | Matches operation runs |
| `trigger` | TEXT | deadline \| admin \| recovery |
| `occurred_at` | TIMESTAMPTZ | |
| `ruleset_version` | TEXT | |
| `metadata` | JSONB | eligible_humans, bots_required, etc. |

### LeagueOperationRun (`league_operation_runs` — new)

| Field | Type | Notes |
|-------|------|-------|
| `operation_key` | TEXT PK | Exactly-once |
| `status` | TEXT | started \| succeeded \| failed |
| `started_at` / `finished_at` | TIMESTAMPTZ | |
| `error` | TEXT NULL | |
| `worker_id` | TEXT NULL | Lease / debugging |

### LeagueOutbox (`league_outbox` — new)

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID PK | |
| `event_type` | TEXT | registration_open, deadline_reminder, result, promo… |
| `payload` | JSONB | |
| `dedupe_key` | TEXT UNIQUE | |
| `created_at` | TIMESTAMPTZ | |
| `published_at` | TIMESTAMPTZ NULL | |
| `attempts` | INT | |

---

## State transitions

### Season

```text
dormant → registration_open (next_registration_at)
registration_open → registration_locked (deadline)
registration_locked → preparing (humans >= min)
registration_locked → cancelled (humans < min) → offseason scheduling → registration_open
preparing → active (fixtures + matchdays ready)
preparing → failed → preparing (retry)
active ↔ paused (admin / infrastructure)
active → settling (all matchdays completed)
settling → completed (rewards + movement committed)
completed → (offseason timer) → registration_open
admin force-end → cancelled (cancellation settlement; prizes/promo gated)
```

### Matchday

```text
scheduled → open → closing_soon → locked → resolving → completed
resolving → resolution_failed → resolving (retry; never sporting forfeit for infra)
```

### Fixture terminal

```text
… → settled | forfeit | void
double_forfeit stored as result_type=double_forfeit with status terminal (forfeit family)
```

---

## Standings math (double forfeit)

Per club:

| Stat | Delta |
|------|-------|
| MP | +1 |
| W | 0 |
| D | 0 |
| L | +1 |
| GF | 0 |
| GA | 0 |
| GD | 0 |
| Pts | 0 |

Must not increment clean sheets, unbeaten streaks, appearances, or promo-eligibility match counts.

---

## RLS

ENABLE RLS + select/insert/update policies (bot Data API pattern from 032/064) on all new tables. Extend `verify_required_schema.sql` with tables, columns, functions, and policies.

---

## Migration notes

1. Expand status checks carefully; map legacy `registration` → accept as alias or migrate values in place for open regs only when safe.
2. Add `pacing_mode` value `lifecycle_v1` (or reuse dynamics marker + ruleset_version — prefer explicit `lifecycle_v1`).
3. Do not rewrite windows on living Dynamics/legacy seasons.
4. Seed game_config; grant service_role on money RPCs as today.
5. Idempotent APPLY via scratch script pattern.
