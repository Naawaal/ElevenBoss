# Data Model: Ranked PvP Matchmaking and Manager Rivalries

**Feature**: `053-pvp-matchmaking-rivalries`  
**Date**: 2026-08-04  
**Migration**: `098_pvp_matchmaking_rivalries.sql` (after head **097**)

---

## Entities

### PvP Queue Entry (`pvp_matchmaking_queue`)

| Field | Type | Notes |
|-------|------|--------|
| `id` | uuid PK | |
| `owner_id` | bigint FK → players | Manager searching |
| `guild_id` | bigint | Guild-local matching key |
| `channel_id` | bigint | Origin channel for stadium spawn |
| `status` | text | `searching` \| `matching` \| `matched` \| `cancelled` \| `expired` |
| `global_division` | text | Snapshot at join |
| `global_lp` | int | Snapshot at join |
| `xi_rating` | numeric | Starting XI mean OVR at join |
| `joined_at` | timestamptz | Wait scoring |
| `expires_at` | timestamptz | Search window / continued search |
| `matched_run_id` | uuid null FK → match_runs | Set on claim |
| `claim_token` | uuid null | Stale `matching` recovery |
| `cancelled_at` | timestamptz null | |
| `created_at` / `updated_at` | timestamptz | |

**Invariants**:
- At most one row per `owner_id` with `status IN ('searching','matching')` (unique partial index).
- Writes via RPC / service role only (RLS: no direct anon mutate).
- Indexes: `(guild_id, status, joined_at)`, `(owner_id, status)`.

**Transitions**:
```text
[join] → searching
searching --claim start--> matching --success--> matched
searching --cancel|expire--> cancelled|expired
matching --stale reclaim / fail--> searching | expired (no charge)
```

---

### Manager Rivalry (`manager_rivalries`)

| Field | Type | Notes |
|-------|------|--------|
| `manager_a_id` | bigint | `least(id1,id2)` |
| `manager_b_id` | bigint | `greatest(id1,id2)` |
| `meetings` | int | Ranked PvP only |
| `a_wins` / `b_wins` / `draws` | int | |
| `a_goals` / `b_goals` | int | |
| `current_streak_owner` | bigint null | |
| `current_streak_count` | int | |
| `longest_streak_owner` | bigint null | |
| `longest_streak_count` | int | |
| `last_winner_id` | bigint null | null on draw |
| `last_result` | text null | optional denorm |
| `activated_at` | timestamptz null | When status → active |
| `last_match_at` | timestamptz | |
| `status` | text | `tracking` \| `active` \| `dormant` |
| `created_at` / `updated_at` | timestamptz | |
| PK | `(manager_a_id, manager_b_id)` | |
| CHECK | `manager_a_id < manager_b_id` | |

**Activation**: `meetings >= 3` with enough meetings inside rolling 30 days (implement as: on each ranked finalize, if 3+ meetings with `last_match_at` span / count-in-window rule per rivalry_math — default: third meeting within 30 days of first in the activation window; pure module documents exact rule). Spec: three ranked meetings within 30 days.

**Dormancy**: no ranked meeting for 60 days → `dormant`; history retained.

**Not stored**: recent match list (query `match_history`).

---

### PvP Block (`pvp_blocks`)

| Field | Type | Notes |
|-------|------|--------|
| `blocker_id` | bigint | |
| `blocked_id` | bigint | |
| `created_at` | timestamptz | |
| PK | `(blocker_id, blocked_id)` | |

Matcher and Friendly invite check **both** directions.

---

### Match Run (extend `match_runs`)

Existing columns already include `home_discord_id`, `away_discord_id`, `guild_id`, `channel_id`, `thread_id`, `sim_seed`, `squad_snapshot`, statuses.

**Changes**:
- `run_type` CHECK adds `'pvp'`, `'practice'`
- Snapshot for PvP must include both XI squads + ratings at claim time (immutable)
- Optional: `completion_key` already supports idempotent settle

**Statuses** (unchanged): `streaming` → `completing` → `completed` | `abandoned` | `failed`

---

### Match Lock (extend)

- `lock_type` CHECK + `acquire_match_lock` allow `'pvp'`, `'practice'`
- Dual PvP: acquire both IDs in ascending order inside `try_match_pvp_queue` / finalize paths

---

### Match History (extend `match_history`)

| Field | Type | Notes |
|-------|------|--------|
| *(existing)* `player_id`, `result`, ratings, goals, coins, points, `run_id`, … | | |
| **NEW** `opponent_owner_id` | bigint null | Human opponent or null for AI |
| **NEW** `match_type` | text not null | `pvp` \| `practice` \| `friendly` \| `league` \| `bot` (legacy) |
| **NEW** `global_lp_delta` | int not null default 0 | Must be 0 unless `match_type='pvp'` |
| **NEW** `rivalry_counted` | boolean not null default false | True only when rivalry row updated for this PvP |

**Invariants** (SQL guards / finalize):
- `match_type IN ('practice','friendly')` ⇒ `global_lp_delta = 0` and `rivalry_counted = false`
- PvP: two rows per `run_id` (one per manager)

---

### Player competitive prefs (extend `players`)

Prefer columns over new tables:

| Field | Type | Notes |
|-------|------|--------|
| `pvp_rivalry_dms` | boolean default true | |
| `pvp_rivalry_callouts` | boolean default true | |
| `pvp_rivalry_lb_visible` | boolean default true | |
| `pvp_badge_keys` | text[] default '{}' | Personal rivalry badges |
| `pvp_requeue_available_at` | timestamptz null | 15s cancel delay |
| `pvp_matches_utc_date` / `pvp_matches_utc_count` | date/int | Or derive from history; prefer ledger columns if hot |
| `practice_rewarded_utc_date` / `practice_rewarded_utc_count` | date/int | Daily Practice cap |

Exact column set may use a small `pvp_daily_ledger` table if players-row churn is undesirable — prefer ledger table only if implement proves necessary (ponytail: start with history COUNT for caps inside RPC; add ledger columns if COUNT is too hot).

---

### Game config keys

See [contracts/pvp-queue-rpcs.md](./contracts/pvp-queue-rpcs.md) — includes `battle_pvp_enabled`, energy costs, multipliers, widening, rivalry thresholds, Practice multipliers.

---

## Relationships

```text
players 1──* pvp_matchmaking_queue
players 1──* match_runs (home/away)
match_runs 1──2 match_history (pvp)
players *──* manager_rivalries (canonical pair)
players *──* pvp_blocks
```

---

## Validation rules (summary)

- Queue join: flag on, registered, not queued, not locked, valid XI, energy ≥ PvP cost, under daily ranked cap, not in requeue delay, guild context present.
- Pair claim: same guild, not blocked, not same id, widening OK, pair cooldown/daily OK, revalidate XI/energy/locks, sorted dual lock, create run + mark matched atomically.
- Finalize PvP: `run_type='pvp'`, idempotent, charge both, rewards both, LP both, rivalry once, release locks.
- Finalize Practice: `run_type='practice'`, LP 0, no rivalry, capped rewards, release lock.
