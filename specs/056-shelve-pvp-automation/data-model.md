# Data Model: Shelve PvP and Fix Surviving Automations

**Feature**: `056-shelve-pvp-automation`  
**Date**: 2026-08-08

## 1. Entities retained / corrected

### Changelog Version Record (`game_config.last_changelog_deployment`)

Stores the last claimed/posted changelog **version** (not commit-scoped deployment).

| Field (JSON) | Type | Rules |
|--------------|------|--------|
| `deployment_key` | text | **Equals the version string** (e.g. `1.5.0`). Primary identity for claim/already_posted. |
| `version` | text | Same as key; written on complete. |
| `commit` | text | Optional ops metadata only; MUST NOT affect claim equality. |
| `claimed_at` | timestamptz | Set on claim; claims older than 10 minutes may be taken over if not posted. |
| `posted_at` | timestamptz | Set only after successful channel send. |
| `channel_id` | bigint | Channel where posted. |
| `instance_id` | text | Claiming process id / instance label. |

**Transitions**:
1. No row / different version + no active claim → **claim**
2. Same version + `posted_at` set → **already_posted** (silent restart)
3. Same version + fresh claim (&lt;10m) without post → **already_claimed**
4. Claim without successful send → claim expires → retryable

**Validation**: Latest header from `change_log.md` must match `## [X.Y.Z]` parser; body edits under same header do not change identity.

### Vote Reminder Window (`topgg_vote_reminders`)

Unchanged table from migration 107. Authority field: `reminder_window_key`.

| Field | Role after hardening |
|-------|----------------------|
| `reminder_window_key` | Unique completion identity for one cooldown interval |
| `next_vote_at` | Prefer Top.gg-provided value when upserting |
| `reminder_sent_at` | Set when DM sent **or** Forbidden handled (window closed) |
| `fallback_pending` | True only after Forbidden; cleared when Store shows notice once |
| `reminder_claimed_at` | Batch claim; stale after 15 minutes |

**Transitions**: due → claimed → (Top.gg check) → sent | forbidden+fallback | backoff | already-voted (reschedule).

## 2. Entities removed (PvP Artifact Set)

Dropped by forward migration `108` (and deleted from repo migrations 098–106):

| Kind | Examples |
|------|----------|
| Tables | `pvp_matchmaking_queue`, `manager_rivalries`, `pvp_blocks`, `pvp_ghost_snapshots`, `pvp_ghost_encounters`, related backfill/state tables |
| Config keys | `battle_pvp_enabled`, `pvp_rewards_enabled`, `pvp_rivalries_enabled`, PvP energy/search tunables |
| Columns | PvP prefs/badges on `players`; PvP-only `match_history` columns introduced in 098+ |
| Match type values | `pvp`, `practice` removed from shared CHECKs; restore 097-era sets |
| RPCs | Queue/match/finalize/ghost/rivalry/block helpers (`join_pvp_queue`, `try_match_pvp_queue`, `finalize_pvp_match`, `complete_pvp_run`, …) |

**Preserved Academy entities**: schemas/RPCs from `095`–`097` unchanged.

**Preserved automation entities**: `topgg_vote_reminders` + claim RPC from `107` unchanged in shape (behavior tightened in app + any small RPC notes in contracts).

## 3. Battle product model (post-cleanup)

| Mode | Present | Notes |
|------|---------|--------|
| Bot Battle | Yes | Pre-PvP AI/bot path |
| Friendly | Yes | Existing Friendly path |
| Ranked / Find Opponent / Practice / Queue / Rivalry | No | Deleted |

`match_runs` / `match_locks` allowed types return to pre-PvP sets (bot, friendly, league, … as defined at 097).

## 4. Relationships

```text
change_log.md (latest ## [version])
        │
        ▼
claim_deployment_changelog(version) ──► game_config.last_changelog_deployment
        │
        ▼ (on successful Discord post)
complete_deployment_changelog(version, optional commit meta)

Top.gg vote / store claim
        │
        ▼
topgg_vote_reminders (window key)
        │
        ▼
claim_due_topgg_vote_reminders → DM or Store fallback (once per window)
```
