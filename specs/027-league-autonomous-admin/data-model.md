# Data Model: Autonomous League Administration Policy

**Feature**: `027-league-autonomous-admin`  
**Depends on**: `070_league_lifecycle_v1.sql` entities from `026`

This feature mostly **reinterprets** existing columns. No new competitive tables are required.

## Entities

### Guild League Time Settings (mutable)

**Storage**: `guild_config` (one row per guild)

| Field | Type | Rules |
|-------|------|-------|
| `guild_id` | TEXT PK | Discord guild |
| `league_timezone` | TEXT NULL | IANA name when set; NULL means “use default” |
| `league_resolution_hour_local` | SMALLINT NULL | 0–23 when set; NULL means “use default” |
| `league_lifecycle_v1_enabled` | BOOLEAN NULL | Cutover override — **not Discord-editable under 027** (operator/DB/`game_config` only) |

**Effective League Time** (derived, not stored):

- timezone = `league_timezone` if set else `'UTC'`
- hour = `league_resolution_hour_local` if set else `0`

**Validation** (on Discord save):

- Timezone MUST resolve via installed tz database
- MUST reject raw offset forms (`UTC+5:45`, `GMT-4`, etc.)
- Hour MUST be integer 0–23 (UI may accept `HH:MM` but only hour component is stored today; keep hour granularity unless product expands minutes later — V1 stores hour as today)

### Season Timing Snapshot (immutable per season)

**Storage**: `league_seasons` (+ child windows)

| Field | Role |
|-------|------|
| `timezone` | Frozen IANA at prepare |
| `resolution_hour_local` | Frozen local hour at prepare |
| `ruleset_snapshot` | JSON including timezone + hour (+ other 026 fields) |
| `phase_deadlines` | UTC phase ends |
| `league_matchdays.window_start` / `window_end` | Precomputed UTC per matchday |
| fixture `window_*` | Copied/aligned per fixture |

**Invariant**: Updates to Guild League Time Settings MUST NOT rewrite these columns for non-terminal living seasons.

### Lifecycle Operation / Journal / Outbox (reuse)

Unchanged from `026` / `070`:

- `league_operation_runs` — idempotency keys
- `league_transition_journal` — audit
- `league_outbox` — presentation retries

Operator recovery creates/uses the same operation keys and journal entries; it MUST NOT invent parallel audit tables.

### Operator Recovery Request (logical)

Not necessarily a new table. V1 representation:

- CLI invocation metadata logged + `league_transition_journal` rows with `trigger = 'operator_recover'` (or equivalent)
- Idempotency via existing `operation_key` unique constraint

Optional later: `league_operator_alerts` — **out of scope** unless logging proves insufficient.

## State / authority transitions (Discord vs engine)

```text
Discord League Time save
  → validates IANA + hour
  → upserts guild_config only
  → does NOT transition season status

Scheduler / operator wake
  → engine.process_due_transitions
  → may open/close/prepare/settle/... per 026
  → outbox publish (non-competitive)

Discord player /league hub
  → register/withdraw only if engine already opened registration
  → lineup prep only if fixture window allows
  → never sets season status
```

## Default notice (optional)

If product wants “defaults active” messaging:

- Detect NULL TZ/hour on guild
- Enqueue outbox event `league_time_defaults_active` (informational)
- MUST NOT gate `process_due_transitions`

V1 may skip outbox and rely on admin preview copy (“using defaults until configured”).

## Migration notes

| Change | Needed? |
|--------|---------|
| New columns for League Time | No — already on `guild_config` |
| Coalesce defaults | App/engine logic |
| Align `game_config` default hour to `0` | Optional `072` |
| Discord-editable cutover removal | Code only (stop writing from modal) |
