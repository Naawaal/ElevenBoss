# Data Model: Youth Academy Workflow

**Feature**: `015-youth-academy` | **Date**: 2026-07-12  
**Migration**: `060_youth_academy_workflow.sql` (planned)

## Entity relationship (logical)

```text
players (club)
  ├── youth_academy_level (existing 1–5)
  ├── scouting_finishes_at (NEW, nullable)
  ├── player_cards[]
  │     ├── in_academy = false  → senior (match/drill eligible when assigned)
  │     └── in_academy = true   → academy seat (counts toward slot cap)
  ├── youth_intake_log (existing weekly idempotency)
  └── scouting_reports[] (NEW shortlists)
```

## Table changes

### `player_cards` (extend)

| Column | Type | Notes |
|--------|------|-------|
| `in_academy` | `BOOLEAN NOT NULL DEFAULT FALSE` | Holding phase; grandfather = false |
| `academy_progress` | `INTEGER NOT NULL DEFAULT 0` | 0–99 points toward next OVR tick |
| `academy_seated_at` | `TIMESTAMPTZ` | Set on seat; null for seniors |

**Validation**:
- `in_academy = TRUE` ⇒ must not appear in `squad_assignments` (enforce on assign + promote clears any stray).
- Growth only when `in_academy AND overall < potential AND NOT is_retired`.

**Indexes**:
- Partial: `(owner_id) WHERE in_academy = TRUE` for slot counts and daily job.

### `players` (extend)

| Column | Type | Notes |
|--------|------|-------|
| `scouting_finishes_at` | `TIMESTAMPTZ` | Null = idle; set on dispatch |
| `scouting_active_tier` | `TEXT` | `quick`/`standard`/`deep` while assignment in flight |

### `scouting_reports` (new)

| Column | Type | Notes |
|--------|------|-------|
| `id` | `UUID PK` | |
| `owner_id` | `BIGINT` FK → `players` | |
| `tier` | `TEXT` | `quick` \| `standard` \| `deep` |
| `prospects_json` | `JSONB` | Array of 3 card-shaped objects (full stats) |
| `signed_card_id` | `UUID` nullable | Set when one prospect signed |
| `created_at` | `TIMESTAMPTZ` | Finish/claim-available time |
| `expires_at` | `TIMESTAMPTZ` | Default created_at + 48h |
| `notified_at` | `TIMESTAMPTZ` nullable | DM sent |

**RLS**: ENABLE + policies for `anon, authenticated, service_role` SELECT/INSERT/UPDATE (bot Data API) — follow `030_league_members_rls.sql` pattern.

**Validation**:
- At most one non-expired unsigned report actionable per club (or allow history; UI shows latest claimable).
- Sign at most once (`signed_card_id` not null ⇒ further signs rejected).

### `youth_intake_log` (existing)

Unchanged PK `(owner_id, intake_week)`. Result payload gains seating metadata (see contracts).

### `game_config` keys (new)

| Key | Default | Meaning |
|-----|---------|---------|
| `senior_roster_cap` | `48` | Max non-academy non-retired cards |
| `scout_cost_quick` | `3000` | |
| `scout_cost_standard` | `10000` | |
| `scout_cost_deep` | `25000` | |
| `scout_hours_quick` | `2` | |
| `scout_hours_standard` | `8` | |
| `scout_hours_deep` | `24` | |
| `scout_report_ttl_hours` | `48` | |
| `academy_ready_ovr` | `65` | UI guideline |
| `academy_age_out` | `20` | Force resolve at age ≥ this |

Slot caps stay code constants mirrored in SQL (unless later moved to config).

## State transitions

### Academy prospect lifecycle

```text
[Generated intake/scout]
        │
        ▼
  Seated (in_academy=true) ──release──► Deleted (gone from club)
        │
        │ daily growth (OVR↑ ≤ POT)
        │
        ├── promote (manual or age-out) ──► Senior (in_academy=false)
        │                                      │
        │                                      └─ normal XP/drills/matches
        │
        └── age-out fail (roster full) ──► Deleted + notify
```

### Scouting assignment

```text
Idle ──dispatch (pay coins)──► In progress (scouting_finishes_at = now+duration)
                                      │
                                      ▼ time reached
                               Report ready (row + clear finishes_at)
                                      │
                         ┌────────────┼────────────┐
                         ▼            ▼            ▼
                      Sign 1        Expire       Ignore
                   (seat academy)  (no sign)
```

## Counts & invariants

| Invariant | Rule |
|-----------|------|
| Academy occupancy | `COUNT(*) FILTER (in_academy)` ≤ `academy_slot_cap(youth_academy_level)` |
| Intake seating | Seats `min(generated, free_slots)`; never deletes existing academy rows |
| Senior promote | Senior count &lt; `senior_roster_cap` |
| Scout concurrency | Cannot dispatch if `scouting_finishes_at > now()` or claimable unsigned report still open (implement choice: block dispatch until report resolved/expired — **prefer block** to reduce abandoned reports) |
| Grandfather | Pre-060 cards remain `in_academy = false` |

## RPCs (summary)

| RPC | Mutates |
|-----|---------|
| `process_youth_intake` (replace body) | Insert academy cards; slot-aware |
| `process_daily_academy_growth` | Progress/OVR/stats; age-out promote/delete |
| `promote_academy_player` | Flip flag; clear academy fields; cap check |
| `release_academy_player` | Delete academy card |
| `dispatch_youth_scout` | Coins + `scouting_finishes_at` |
| `claim_youth_scout_report` | Materialize report JSON if due; or sign index into academy |

Exact signatures in `contracts/`.
