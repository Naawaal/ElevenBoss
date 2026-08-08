# Contract: Cleanup Inventory (PvP Shelve)

**Feature**: `056-shelve-pvp-automation`  
**Purpose**: Exact delete / restore / keep lists for implementers. Source of truth for the grep gate.

## 1. Pre-PvP reference

- Battle baseline commit: `1737df6e806874fe4449b8357835e5112e018c99`
- Academy keep: migrations `095`–`097`
- Automation keep: migration `107`, Feature 055 modules

## 2. Delete dedicated product files

```text
packages/pvp/                                          # entire package
apps/discord_bot/core/pvp_match.py
apps/discord_bot/core/pvp_rpc.py
apps/discord_bot/embeds/pvp_embeds.py
apps/discord_bot/views/pvp_queue_view.py
apps/discord_bot/views/rivalries_view.py
apps/discord_bot/tasks/pvp_matchmaker_job.py
```

Also remove `packages/pvp` from `requirements.txt` / editable installs if listed.

## 3. Delete migrations (repo) + replace with forward cleanup

**Delete from repo**:
```text
supabase/migrations/098_pvp_matchmaking_rivalries.sql
supabase/migrations/099_pvp_matchmaking_fairness.sql
supabase/migrations/100_pvp_finalize_rpcs.sql
supabase/migrations/101_pvp_rivalries_blocks_recovery.sql
supabase/migrations/102_pvp_integrity_remediation.sql
supabase/migrations/103_instant_pvp_backfill.sql
supabase/migrations/104_varied_ai_opponents.sql
supabase/migrations/105_fix_complete_pvp_run_ghost_ai.sql
supabase/migrations/106_fix_ai_snapshot_positions.sql
```

**Keep**:
```text
095_youth_academy_rarity_v2.sql
096_academy_scout_fog_floor.sql
097_academy_season_aging_decay.sql
107_vote_reminders_and_changelog.sql
```

**Add**:
```text
108_shelve_pvp_and_version_changelog.sql
```

`108` MUST:
1. Drop all PvP tables/columns/flags/indexes/policies/RPCs introduced by 098–106 (`IF EXISTS`).
2. Restore shared CHECK constraints and rewritten shared functions to **097 definitions**.
3. Redefine `claim_deployment_changelog` / `complete_deployment_changelog` for version-only keys (see changelog contract).
4. Extend/replace schema guard so **no** PvP objects are required; keep 107 automation guards.

## 4. Shared files — remove PvP hunks only

```text
apps/discord_bot/cogs/battle_cog.py
apps/discord_bot/core/api_errors.py
apps/discord_bot/core/economy_rpc.py
apps/discord_bot/core/match_runs.py
apps/discord_bot/core/match_recovery.py
apps/discord_bot/core/scheduler_jobs.py
apps/discord_bot/main.py
apps/discord_bot/cogs/squad_cog.py          # if PvP prefs/UI remain
packages/leagues/leagues/match_points.py   # if PvP LP hooks remain
requirements.txt
supabase/scripts/verify_required_schema.sql
.specify/specs/v1.0.0/spec.md
.specify/specs/v1.0.0/plan.md
change_log.md                              # player-facing: document shelve + automation fixes
```

### `main.py` scheduler contract after cleanup

| Job | Keep? |
|-----|-------|
| `pvp_matchmaker_job` (5s) | **Remove** |
| `pvp_ghost_refresh_job` (02:30) | **Remove** |
| `run_topgg_vote_reminders` (30m) | **Keep** |
| Startup `check_and_post_deployment_changelog` | **Keep** (version-only) |

## 5. Delete specs / tests / scratch

```text
specs/053-pvp-matchmaking-rivalries/
specs/054-instant-pvp-backfill/

tests/test_pvp_matchmaking.py
tests/test_pvp_reward_policy.py
tests/test_pvp_rivalry_math.py
tests/test_pvp_integrity_remediation.py
tests/test_pvp_ghost_backfill.py
tests/test_pvp_ghost_backfill_e2e.py

scratch/apply_migration_098.py … apply_migration_106.py
scratch/check_053_*
scratch/check_pvp_*
scratch/enable_pvp_flags.py
scratch/reset_pvp_dark_state.py
scratch/pvp_soak_report.py
scratch/patch_practice_mode.py
scratch/test_ai_fix.py
scratch/test_ai_snap.py
scratch/test_ai_variety.py
scratch/test_snap.py
scratch/verify_schema_103.py
```

Do **not** delete Academy 095–097 apply scripts or Feature 051/052 / 055 materials. Keep `scratch/apply_migration_107.py` (and add `108` apply script when implementing).

## 6. `/battle` UI contract

```text
/battle
 ├─ Bot Battle     → original AI/bot match (baseline 1737df6 behavior)
 └─ Friendly       → existing Friendly behavior
```

Absent: Find Opponent, Ranked, Practice-as-PvP, queue states, ghost managers, rivalries.

## 7. Grep gate (must be clean in product tree)

Search tokens (expect zero hits outside git history / this feature’s docs until docs are updated):

```text
pvp_matchmaking
manager_rivalries
pvp_blocks
pvp_ghost
battle_pvp_enabled
pvp_rewards_enabled
pvp_rivalries_enabled
join_pvp_queue
try_match_pvp_queue
finalize_pvp_match
complete_pvp_run
packages.pvp
pvp_matchmaker_job
pvp_ghost_refresh
```

Prefer these over bare `practice` to avoid false positives on unrelated copy.
