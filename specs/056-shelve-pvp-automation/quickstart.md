# Quickstart: Shelve PvP + Automation Fixes

**Feature**: `056-shelve-pvp-automation`  
**Goal**: Validate end state — pre-PvP battle + silent same-version restarts + one reminder per vote window.

## Prerequisites

- Repo on feature worktree with plan implemented
- `DATABASE_URL` / Supabase credentials for schema apply (local or staging)
- Discord test guild with announcement channel configured (or fallback text channel)
- Optional: Top.gg test token for reminder path

## 1. Schema cleanup

```bash
# Apply forward cleanup (pattern matches existing scratch apply scripts)
python scratch/apply_migration_108.py

# Verify — must pass with zero PvP requirements
python scratch/verify_schema_full.py
# or: psql $DATABASE_URL -f supabase/scripts/verify_required_schema.sql
```

**Expected**: Guard lists include `topgg_vote_reminders` + changelog claim RPCs; no `pvp_*` / rivalry / ghost requirements.

## 2. Product grep gate

From repo root, search active tree (exclude `.git`):

```text
pvp_matchmaking, manager_rivalries, battle_pvp_enabled,
join_pvp_queue, finalize_pvp_match, pvp_matchmaker_job, packages.pvp
```

**Expected**: Zero hits in `apps/`, `packages/`, `supabase/`, `tests/` (this feature’s `specs/056-*` docs may still describe cleanup until archived).

## 3. Battle smoke

1. Start bot against cleaned DB.
2. Run `/battle` as a registered manager.
3. **Expected UI**: Bot Battle + Friendly only.
4. Complete one Bot Battle.
5. **Expected**: Original AI/bot flow (no queue, Practice, ghost, rivalry).
6. Complete one Friendly (unchanged success path).

## 4. Changelog — silent restart

1. Ensure `game_config.last_changelog_deployment` already has `posted_at` for current latest `## [version]` in `change_log.md`.
2. Restart bot (optionally on a different git commit with **same** version header).
3. **Expected**: No new changelog message in the announcement channel.

## 5. Changelog — new version once

1. Add a new top section `## [9.9.9] - YYYY-MM-DD` with at least one `### Added` bullet (test only; revert after).
2. Restart bot (once, or two instances if available).
3. **Expected**: Exactly one changelog embed; config records version `9.9.9` as posted.
4. Restart again without further header changes.
5. **Expected**: Silence.
6. Edit a bullet under `9.9.9` only; restart.
7. **Expected**: Silence.

## 6. Vote reminder

1. Seed / use a row in `topgg_vote_reminders` with `next_check_at <= now()`, `reminder_sent_at IS NULL`, valid window key.
2. Trigger `run_topgg_vote_reminders` (wait for 30m job or invoke once in a controlled test).
3. **Expected**: At most one DM when Top.gg says not voted.
4. Simulate `Forbidden`: **Expected** `fallback_pending`; open `/store` → one ephemeral notice → pending cleared; no second DM for that window.

## 7. Academy non-regression

Spot-check Youth Academy scout/growth path still works (095–097 era). No Academy migration files removed.

## 8. Automated tests

```bash
pytest tests/test_deployment_changelog.py tests/test_topgg_vote_reminders.py -q
```

**Expected**: Version-only dedupe cases and reminder window/fallback cases pass; all `tests/test_pvp_*.py` gone.

## Done when

- [ ] Migration 108 applied; verify script green without PvP guards  
- [ ] Grep gate clean  
- [ ] `/battle` = Bot + Friendly only; Bot Battle matches baseline behavior  
- [ ] Same-version restart silent; new header posts once  
- [ ] One vote window ≤ one DM/fallback  
- [ ] Academy intact  
