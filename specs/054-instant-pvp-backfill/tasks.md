# Tasks: Feature 054 — Instant PvP Backfill and Ghost Managers

**Input**: Design documents from `/specs/054-instant-pvp-backfill/`

**Prerequisites**: [plan.md](file:///d:/Python/Discord%20Bots/ElevenBoss/specs/054-instant-pvp-backfill/plan.md) (required), [spec.md](file:///d:/Python/Discord%20Bots/ElevenBoss/specs/054-instant-pvp-backfill/spec.md) (required for user stories), [research.md](file:///d:/Python/Discord%20Bots/ElevenBoss/specs/054-instant-pvp-backfill/research.md), [data-model.md](file:///d:/Python/Discord%20Bots/ElevenBoss/specs/054-instant-pvp-backfill/data-model.md), [contracts/](file:///d:/Python/Discord%20Bots/ElevenBoss/specs/054-instant-pvp-backfill/contracts/)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (`[US1]`, `[US2]`, `[US3]`)
- Exact file paths included in all descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Verify project paths and package boundaries before implementation.

- [x] T001 Verify active feature directory in `.specify/feature.json` and monorepo structure in `specs/054-instant-pvp-backfill/plan.md`
- [x] T002 Verify `packages/pvp` editable installation and exports in `packages/pvp/pvp/__init__.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core database schema, RPC signatures, and pure models that MUST be complete before ANY user story can be implemented.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T003 Create database migration `supabase/migrations/103_instant_pvp_backfill.sql` defining `pvp_ghost_snapshots` table, `pvp_ghost_encounters` table, `pvp_matchmaking_queue` column extensions (`backfill_after`, `preferred_mode`), and `match_runs`/`match_history` column extensions (`opponent_mode`, `opponent_snapshot_age_seconds`)
- [x] T004 [P] Update schema guard script in `supabase/scripts/verify_required_schema.sql` to include `pvp_ghost_snapshots` and `pvp_ghost_encounters`
- [x] T005 [P] Define Pydantic models for `GhostSnapshot`, `GhostEncounter`, and `OpponentMode` in `packages/pvp/pvp/models.py`
- [x] T006 Define pure opponent selection scoring, search band logic, and mode-based reward multipliers in `packages/pvp/pvp/matchmaking.py`
- [x] T007 [P] Implement RPC Python client wrappers for `refresh_pvp_ghost_snapshot`, `try_match_pvp_queue`, and `finalize_pvp_match` in `apps/discord_bot/core/pvp_rpc.py`

**Checkpoint**: Foundation ready — user story implementation can now begin.

---

## Phase 3: User Story 1 - Instant Ranked Match Search with Ghost Backfill (Priority: P1) 🎯 MVP

**Goal**: Enable searching managers to automatically match against a recent frozen squad snapshot of a real manager (Ghost Manager) after 10 seconds of live searching, guaranteeing match start within 15 seconds.

**Independent Test**: Queue a single manager when no live humans are available. After 10s, `try_match_pvp_queue` creates a ghost match (`opponent_mode = 'ghost'`). Upon completion, only the challenger receives rewards/history with Ghost multipliers (0.85x coins, 0.90x XP, 0.75x pos LP); the offline ghost owner suffers zero losses or notifications.

### Tests for User Story 1

- [x] T008 [P] [US1] Create integration test suite for single-searcher ghost match creation and one-sided finalization in `tests/test_pvp_ghost_backfill.py`

### Implementation for User Story 1

- [x] T009 [US1] Implement stored procedure `refresh_pvp_ghost_snapshot` in `supabase/migrations/103_instant_pvp_backfill.sql` to capture and store 11-card squad snapshots
- [x] T010 [US1] Implement Level 1 (Live Human) and Level 2 (Ghost Manager) matchmaking with atomic row locks (`FOR UPDATE SKIP LOCKED`) in `try_match_pvp_queue` in `supabase/migrations/103_instant_pvp_backfill.sql`
- [x] T011 [US1] Implement one-sided ghost match finalization logic in `finalize_pvp_match` in `supabase/migrations/103_instant_pvp_backfill.sql` (challenger rewards, zero ghost owner impact, no rivalry updates)
- [x] T012 [US1] Generalize stadium runner in `apps/discord_bot/core/pvp_match.py` to execute single-manager stadium streams without pinging offline ghost owners
- [x] T013 [US1] Update APScheduler background job `apps/discord_bot/tasks/pvp_matchmaker_job.py` to trigger queue matching and backfill processing past `backfill_after`

**Checkpoint**: User Story 1 is fully functional and testable independently (MVP ready!).

---

## Phase 4: User Story 2 - Calibrated Ranked AI Fallback (Priority: P2)

**Goal**: Provide a Level 3 fallback using division-calibrated Ranked AI when zero eligible ghost snapshots exist, guaranteeing 100% queue availability.

**Independent Test**: Queue a single manager with zero ghost snapshots in `pvp_ghost_snapshots`. Matchmaker creates a Ranked AI Backfill match (`opponent_mode = 'ai_backfill'`) with calibrated AI rating and AI reward multipliers (0.70x coins, 0.75x XP, 0.50x pos LP).

### Tests for User Story 2

- [x] T014 [P] [US2] Add unit tests for Calibrated AI fallback selection and AI reward scaling in `tests/test_pvp_ghost_backfill.py`

### Implementation for User Story 2

- [x] T015 [US2] Implement Level 3 (Calibrated Ranked AI) opponent construction fallback inside `try_match_pvp_queue` in `supabase/migrations/103_instant_pvp_backfill.sql`
- [x] T016 [US2] Implement one-sided AI backfill finalization and AI reward scaling in `finalize_pvp_match` in `supabase/migrations/103_instant_pvp_backfill.sql`

**Checkpoint**: User Stories 1 AND 2 are both functional independently.

---

## Phase 5: User Story 3 - Battle Hub Transparency and Daily Backfill Limits (Priority: P3)

**Goal**: Update Battle Hub UI with queue stage progress, estimated start timers, opponent mode badges, Match History labels, and daily backfill limit enforcement.

**Independent Test**: View Battle Hub queue status at 0s and 5s, verify `🟢 LIVE`, `👻 GHOST`, or `🤖 AI` badges in embeds, verify Match History entries show opponent mode and snapshot age, and verify daily backfill cap (< 3 per day) is enforced.

### Tests for User Story 3

- [x] T017 [P] [US3] Add unit tests for daily backfill caps and embed formatting in `tests/test_pvp_ghost_backfill.py`
- [x] T018 [P] [US3] Add queue stage progress embeds, estimated start timers, and mode badges (`🟢 LIVE`, `👻 GHOST`, `🤖 RANKED AI`) in `apps/discord_bot/embeds/pvp_embeds.py`
- [x] T019 [US3] Update Battle Hub slash command handlers and Match History rendering in `apps/discord_bot/cogs/battle_cog.py` to display opponent classifications and snapshot age
- [x] T020 [US3] Enforce daily backfill cap (< 3 ghost/AI backfills per manager per UTC day) inside `try_match_pvp_queue` in `supabase/migrations/103_instant_pvp_backfill.sql`

**Checkpoint**: All user stories are fully functional and integrated.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Verification, documentation, and migration execution.

- [x] T021 [P] Document player-facing progression and UX changes in `change_log.md`
- [x] T022 Verify post-migration database guards by executing `supabase/scripts/verify_required_schema.sql`
- [x] T023 Execute full integration test suite `pytest tests/test_pvp_ghost_backfill.py` and run scenarios in `specs/054-instant-pvp-backfill/quickstart.md`
