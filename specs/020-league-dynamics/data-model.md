# Data Model: League Dynamics

**Feature**: `020-league-dynamics` | **Date**: 2026-07-15  
**Migration**: `064_league_dynamics.sql`

## Entities

### LeagueSeason (`league_seasons` — alter)

| Field | Type | Notes |
|-------|------|-------|
| `pacing_mode` | TEXT NOT NULL DEFAULT `'legacy'` | `legacy` \| `dynamics`; set at insert; immutable mid-season |
| `duration_days` | INT | Dynamics starts force **14** |
| `total_matchdays` | INT | Dynamics / 8-club double RR → **14** |
| `current_matchday` | INT | Shared across all division tiers in the season |
| `config_json` | JSONB | May mirror `dynamics: true`, `divisions: N` for ops |

**Backfill**: `UPDATE … SET pacing_mode = 'legacy' WHERE pacing_mode IS NULL` (or default on ADD COLUMN).

**Constraint**: `CHECK (pacing_mode IN ('legacy', 'dynamics'))`.

### LeagueParticipant (`league_participants` — alter)

| Field | Type | Notes |
|-------|------|-------|
| `division_tier` | INTEGER NOT NULL DEFAULT 1 | 1 = top tier; fixtures only vs same tier |

**Index**: `(season_id, division_tier)`.

**Validation**: At start, every tier used has exactly 8 participants (humans + AI).

### LeagueFixture (`league_fixtures` — alter)

| Field | Type | Notes |
|-------|------|-------|
| `resolved_by` | TEXT NULL | NULL while unplayed; `manual` \| `auto_sim` when `is_played` |

**Constraint**: `CHECK (resolved_by IS NULL OR resolved_by IN ('manual', 'auto_sim'))`.  
**Invariant**: `is_played = false` ⇒ `resolved_by IS NULL`.

Both clubs in a fixture MUST share the same `division_tier` (enforced at insert by seating, not DB trigger — YAGNI).

### LeagueMember (`league_members` — alter)

| Field | Type | Notes |
|-------|------|-------|
| `seasonal_division_tier` | INTEGER NOT NULL DEFAULT 1 | Seed for next Dynamics season; updated by promo/releg at season end |

Distinct from `players.division` (weekly rank name string).

### ManagerOfTheMatchdayAward (`league_matchday_manager_awards` — new)

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID PK | `gen_random_uuid()` |
| `season_id` | UUID FK → `league_seasons` | ON DELETE CASCADE |
| `matchday` | INTEGER | |
| `player_id` | BIGINT FK → `players` | Awarded club |
| `fixture_id` | UUID FK → `league_fixtures` | Winning fixture |
| `margin` | INTEGER | `|HS−AS|` |
| `goals_for` | INTEGER | Winner GF |
| `coins_awarded` | BIGINT | Snapshot of paid amount |
| `created_at` | TIMESTAMPTZ | Default now() |

**Constraints**: `UNIQUE (season_id, matchday)`.

**RLS**: ENABLE + SELECT/INSERT policies for `anon, authenticated, service_role` (bot Data API), mirror `030`/`062` pattern. Prefer writes via RPC.

**Indexes**: `(season_id, matchday)`, `(player_id, created_at DESC)`.

### GameConfig keys (seed)

| Key | Default | Meaning |
|-----|---------|---------|
| `league_dynamics_enabled` | `false` | Master flag — new seasons use Dynamics when true |
| `league_momd_coins` | `2000` | MoMD bonus |
| `league_dynamics_clubs_per_division` | `8` | Hard seating size |
| `league_dynamics_promo_spots` | `2` | Top/bottom swap count |
| `league_dynamics_default_duration_days` | `14` | Forced on Dynamics start |

Helper (optional): `league_dynamics_enabled() RETURNS BOOLEAN`.

Wire existing unused `league_window_hours` **not required** — Dynamics uses midnight math instead.

### Economy ledger

| Source | Idempotency key | Notes |
|--------|-----------------|-------|
| `league_momd` | `momd:{season_id}:{matchday}` | Credit only |

Season prizes keep existing sources/keys; extend to include tier in meta JSON (`division_tier`).

---

## Relationships

```text
leagues 1──* league_seasons
league_seasons 1──* league_participants (division_tier)
league_seasons 1──* league_fixtures (intra-tier pairs)
league_seasons 1──* league_matchday_manager_awards
league_members (guild roster) ── seasonal_division_tier seeds seating
players.division ── WEEKLY rank only (untouched)
```

---

## State transitions

### Season pacing

```text
[admin_start]
  flag off → pacing_mode=legacy (rolling windows)
  flag on  → pacing_mode=dynamics (UTC midnight windows, 14d, tier seating)
[active] → [paused] → [active]   (tick skips paused)
[active] → [completed]           (last MD settled → prizes → promo/releg persist)
```

### Fixture resolution

```text
unplayed (resolved_by NULL)
  ├─ human play before window_end → played + resolved_by=manual
  └─ tick / auto-sim after window_end → played + resolved_by=auto_sim
```

### Matchday settlement (Dynamics)

```text
all fixtures on current_matchday is_played
  → optional notify_matchday_complete
  → award_manager_of_the_matchday (may no-op)
  → advance current_matchday OR complete season
```

### Division tier (cross-season)

```text
season complete
  → per adjacent tiers: bottom 2 humans Div N ↔ top 2 humans Div N+1
  → UPDATE league_members.seasonal_division_tier
  → next season seating reads those values
```

---

## Migration notes (active seasons)

1. ADD columns with safe defaults (`pacing_mode='legacy'`, `division_tier=1`, `resolved_by` NULL, `seasonal_division_tier=1`).
2. Do **not** rewrite `window_start`/`window_end` of active seasons.
3. Flag default false → first Dynamics season only after ops enable + next `admin_start_season`.

Exact SQL sketches live in contracts + implement tasks; this doc is the schema contract.
