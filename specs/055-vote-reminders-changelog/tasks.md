# Tasks: Vote Reminders and Deployment Changelog

**Input**: Design documents from `/specs/055-vote-reminders-changelog/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Tests included as requested by verification guidelines in spec.md and quickstart.md.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Database migration and schema guard initialization

- [x] T001 Create migration file `107_vote_reminders_and_changelog.sql` in `supabase/migrations/107_vote_reminders_and_changelog.sql` containing `topgg_vote_reminders` table DDL, `idx_topgg_vote_reminders_due` index, and RPCs (`claim_due_topgg_vote_reminders`, `claim_deployment_changelog`, `complete_deployment_changelog`).
- [x] T002 Extend schema verification script in `supabase/scripts/verify_required_schema.sql` to include `topgg_vote_reminders` table and new RPC definitions.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core vote tracking helpers that MUST be complete before user stories can record or process reminders

- [x] T003 [P] Implement `upsert_vote_reminder_window()` and window key generation (`<discord_user_id>:<next_vote_at>`) in `apps/discord_bot/core/topgg_vote.py`.
- [x] T004 [P] Wire `upsert_vote_reminder_window()` into the store vote claim handler in `apps/discord_bot/cogs/store_cog.py` and top.gg webhook receiver.

---

## Phase 3: User Story 1 - Top.gg Vote Eligibility DM Reminder (Priority: P1) 🎯 MVP

**Goal**: Send a single gentle gold-styled DM reminder with a `[Vote on Top.gg]` button when vote cooldown expires and Top.gg API re-verification confirms status is `not_voted`.

**Independent Test**: Seed a due reminder row in `topgg_vote_reminders`, run `run_topgg_vote_reminders()`, verify Top.gg API `check_topgg_vote()` is called, and confirm DM is delivered with `reminder_sent_at` updated.

### Implementation & Tests for User Story 1

- [x] T005 [P] [US1] Create unit and integration tests for vote reminder eligibility, Top.gg re-verification, and DM dispatch in `tests/test_topgg_vote_reminders.py`.
- [x] T006 [US1] Implement 30-minute APScheduler task `run_topgg_vote_reminders(bot)` in `apps/discord_bot/tasks/topgg_vote_reminder_job.py` using RPC `claim_due_topgg_vote_reminders` and `check_topgg_vote()`.
- [x] T007 [US1] Register `topgg_vote_reminder_job` in `apps/discord_bot/main.py` with 30-90s startup jitter.
- [x] T008 [US1] Implement Top.gg rate-limit (`429`) and server error circuit breaker backoff logic (30m/60m/2h) in `apps/discord_bot/tasks/topgg_vote_reminder_job.py`.

**Checkpoint**: At this point, User Story 1 (DM reminder pipeline) is fully functional and testable independently as an MVP.

---

## Phase 4: User Story 2 - Ephemeral Fallback Notice for Disabled DMs (Priority: P2)

**Goal**: Display an ephemeral vote reminder notice when a manager with closed DMs opens `/store`.

**Independent Test**: Set `fallback_pending = TRUE` in `topgg_vote_reminders`, execute `/store`, and verify an ephemeral notice with a `[Vote on Top.gg]` button is sent and `fallback_pending` is cleared.

### Implementation & Tests for User Story 2

- [x] T009 [P] [US2] Implement shared async helper `maybe_send_pending_vote_notice(interaction, db)` in `apps/discord_bot/core/pending_notices.py`.
- [x] T010 [US2] Integrate `maybe_send_pending_vote_notice` into Store interaction handler in `apps/discord_bot/cogs/store_cog.py`.
- [x] T011 [US2] Add unit tests for ephemeral fallback notice and stale fallback clearing in `tests/test_topgg_vote_reminders.py`.

**Checkpoint**: User Stories 1 AND 2 are complete and work independently.

---

## Phase 5: User Story 3 - Automated Deployment Changelog Announcement (Priority: P3)

**Goal**: Parse `change_log.md` on bot startup, claim deployment key in `game_config`, resolve announcement channel, and post formatted changelog embed.

**Independent Test**: Mock startup ready event with a new version in `change_log.md`, verify atomic claim in `game_config`, and confirm categorized embed is sent to the resolved announcement channel without duplication on restart.

### Implementation & Tests for User Story 3

- [x] T012 [P] [US3] Create changelog embed builder `build_changelog_embed()` in `apps/discord_bot/embeds/changelog_embeds.py`.
- [x] T013 [P] [US3] Implement changelog parser `parse_latest_changelog_entry()` and deployment service `check_and_post_deployment_changelog(bot)` in `apps/discord_bot/core/deployment_changelog.py`.
- [x] T014 [US3] Integrate startup deployment changelog trigger in `apps/discord_bot/main.py` with multi-instance claim lock.
- [x] T015 [US3] Create unit and integration tests for changelog parser, channel resolution, and deployment claims in `tests/test_deployment_changelog.py`.

**Checkpoint**: All 3 user stories are complete and operational.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and documentation checks

- [x] T016 [P] Run schema verification script and full test suite (`pytest tests/test_topgg_vote_reminders.py tests/test_deployment_changelog.py`).
- [x] T017 Execute validation scenarios documented in `specs/055-vote-reminders-changelog/quickstart.md`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion (migration applied).
- **User Story 1 (Phase 3)**: Depends on Phase 2.
- **User Story 2 (Phase 4)**: Depends on Phase 2 & T003/T004; can be implemented in parallel with US1.
- **User Story 3 (Phase 5)**: Depends on Phase 1 & 2; independent of US1 and US2.
- **Polish (Phase 6)**: Depends on US1, US2, and US3 completion.

### Parallel Opportunities

- `T003` and `T004` can be developed in parallel in Phase 2.
- `T005` (US1 tests), `T009` (US2 helper), `T012` (US3 embed), and `T013` (US3 parser) can all run in parallel across user stories.

---

## Implementation Strategy

### MVP First (User Story 1)
1. Complete Phase 1 & 2 (Migration + Vote tracking helper).
2. Complete Phase 3 (US1 DM Reminder Job).
3. Test US1 independently.

### Full Feature Delivery
1. Add US2 (Ephemeral Fallback Notice for `/store`).
2. Add US3 (Automated Deployment Changelog).
3. Run Phase 6 validation suite.
