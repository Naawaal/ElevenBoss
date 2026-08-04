# Tasks: Ranked PvP Matchmaking and Manager Rivalries

**Input**: Design documents from `/specs/053-pvp-matchmaking-rivalries/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md, GATE.md

**Tests**: Included — plan/quickstart require pytest for matchmaking, rivalry math, reward policy; SQL concurrency for double-pair / duplicate finalize; AGENTS.md runnable checks for non-trivial pure logic.

**Implementation gate**: Feature **052** formal **ACCEPT** required before Phase 2+ coding, migration apply to shared/prod DBs, or production flag enable. Phase 1 audit may run earlier. See [GATE.md](./GATE.md).

**Locked decisions** (research.md / plan.md):
- Guild-local live queue only; no ranked direct challenge; no silent AI
- Migration **098** (repo head **097**); `battle_pvp_enabled=false` default
- Extend `match_runs` / locks with `pvp` + `practice` — no second run table
- Coins via `apply_club_economy`; XP via existing match XP pipe; only `pvp` → non-zero Global LP
- Badges: `players.pvp_badge_keys` (no new badge table)
- Cite **US-42.4 / US-42.7 / US-42.9**; no new top-level slash
- Slice 1 = US1+US2+US3+US4+US7; Slice 2 = US5+US6

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: US1–US7 maps to spec user stories
- Exact file paths required

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm live battle/Friendly/LP contracts before coding against assumed signatures

- [x] T001 Audit `/battle` hub, Bot Battle, and Friendly call paths in `apps/discord_bot/cogs/battle_cog.py`; append drift notes to `specs/053-pvp-matchmaking-rivalries/research.md` if needed
- [x] T002 [P] Audit match-run lifecycle in `apps/discord_bot/core/match_runs.py` and reward/XP/economy wrappers in `apps/discord_bot/core/match_rewards.py`, `apps/discord_bot/core/match_xp.py`, `apps/discord_bot/core/economy_rpc.py`
- [x] T003 [P] Audit locks in `apps/discord_bot/middleware/match_lock.py` + `acquire_match_lock` SQL; Global LP helpers in `packages/leagues/leagues/match_points.py`; scheduler registration in `apps/discord_bot/main.py`
- [x] T004 Confirm migration head is still **097** (or renumber 098) and record touch-list parity vs `specs/053-pvp-matchmaking-rivalries/plan.md` source tree in `specs/053-pvp-matchmaking-rivalries/research.md`

**Checkpoint**: No implementation against stale signatures; 052 gate still respected for Phase 2+

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Pure `packages/pvp` spine + migration **098** schema/config + queue join/cancel scaffolding — **MUST land before user-story wiring**

**⚠️ CRITICAL**: No US1–US7 Discord/RPC story work until package exports, 098 tables/CHECK extensions, and join/cancel exist. Do not apply 098 to production until 052 ACCEPT.

- [x] T005 Create package layout `packages/pvp/pvp/__init__.py`, `packages/pvp/pvp/models.py` (queue snapshot, pair candidate, rivalry event, reward policy result Pydantic models)
- [x] T006 [P] Implement search-range widening + pair scoring stubs in `packages/pvp/pvp/matchmaking.py` per `contracts/pvp-queue-rpcs.md`
- [x] T007 [P] Implement canonical pair ordering + activation/dormancy helpers in `packages/pvp/pvp/rivalry_math.py`
- [x] T008 [P] Implement LP/coin/Practice zero-LP rules in `packages/pvp/pvp/reward_policy.py` (only `pvp` → non-zero LP)
- [x] T009 Export public API from `packages/pvp/pvp/__init__.py`; add editable install / workspace packaging entry if required by repo convention
- [x] T010 [P] Add `tests/test_pvp_matchmaking.py`, `tests/test_pvp_rivalry_math.py`, `tests/test_pvp_reward_policy.py` covering widening, pair order, activation 3/30d, dormant 60d, Practice LP always 0
- [x] T011 Create `supabase/migrations/098_pvp_matchmaking_rivalries.sql` spine: tables `pvp_matchmaking_queue`, `manager_rivalries`, `pvp_blocks`; extend `match_runs.run_type` + `match_locks`/`acquire_match_lock` for `pvp`/`practice`; extend `match_history` (`opponent_owner_id`, `match_type`, `global_lp_delta`, `rivalry_counted`); player pref/badge columns per `data-model.md`; insert `game_config` keys with `battle_pvp_enabled=false`; RLS + schema guard DO block
- [x] T012 [P] Extend `supabase/scripts/verify_required_schema.sql` for 098 tables/columns/functions/policies
- [x] T013 Add `scratch/apply_migration_098.py` mirroring prior apply scripts; do not flip PvP flag
- [x] T014 Implement `join_pvp_queue` + `cancel_pvp_queue` + queue expiry helper in `098_pvp_matchmaking_rivalries.sql` (no energy debit on join; 15s requeue delay on cancel)
- [x] T015 Implement skeleton `try_match_pvp_queue` in `098_pvp_matchmaking_rivalries.sql` (SKIP LOCKED, create `run_type='pvp'` run, mark matched) — fairness exclusions completed in US4
- [x] T016 [P] Extend `apps/discord_bot/core/match_runs.py` for `pvp`/`practice` engine config keys; extend `apps/discord_bot/core/economy_rpc.py` energy/coin helpers for `pvp`/`practice`
- [x] T017 [P] Map new RPC errors in `apps/discord_bot/core/api_errors.py`

**Checkpoint**: Foundation ready — stories can share one queue/schema law

---

## Phase 3: User Story 4 — Fair guild-local matchmaking (Priority: P1)

**Goal**: Same-guild pairing only, widening bands, same-pair cooldown/daily caps, daily ranked cap, authoritative revalidation at claim, bidirectional blocks excluded

**Independent Test**: Cross-guild no pair; blocked pairs excluded; cooldown/daily pair limits; after 5 ranked/day cannot requeue; squad change invalidates at claim

**Contracts**: [pvp-queue-rpcs.md](./contracts/pvp-queue-rpcs.md)

### Tests for User Story 4

- [x] T018 [P] [US4] Extend `tests/test_pvp_matchmaking.py` for guild mismatch, widening steps, cooldown/pair-daily/manager-daily exclusions, block both directions
- [x] T019 [US4] Add DB concurrency notes/harness (scratch or tests) proving two searching rows → one run under parallel `try_match_pvp_queue`

### Implementation for User Story 4

- [x] T020 [US4] Complete widening + exclusion + revalidation + sorted dual `acquire_match_lock(..., 'pvp')` inside `try_match_pvp_queue` in `supabase/migrations/098_pvp_matchmaking_rivalries.sql`
- [x] T021 [US4] Enforce same-pair cooldown (30m), same-pair daily (2), manager daily ranked cap (5) and join rejection when capped in queue RPCs in `098_pvp_matchmaking_rivalries.sql`
- [x] T022 [P] [US4] Keep pure scoring in sync with SQL bands in `packages/pvp/pvp/matchmaking.py`

**Checkpoint**: Matcher is fair and atomic before stadium UX

---

## Phase 4: User Story 1 — Find and play a ranked human opponent (Priority: P1) 🎯 MVP

**Goal**: `/battle` Find Opponent → search UX → pair → shared stadium → live match; timeout offers Continue / AI Practice / Cancel; pre-kickoff failure charges nothing

**Independent Test**: Two same-guild managers queue, share one thread, complete one match path (rewards may still be stubbed until US2); never silent AI

**Contracts**: [battle-hub-surfaces.md](./contracts/battle-hub-surfaces.md), [pvp-queue-rpcs.md](./contracts/pvp-queue-rpcs.md)

### Implementation for User Story 1

- [x] T023 [US1] Implement `get_battle_hub_state` RPC in `supabase/migrations/098_pvp_matchmaking_rivalries.sql` per contract
- [x] T024 [P] [US1] Create search/found/timeout embeds in `apps/discord_bot/embeds/pvp_embeds.py`
- [x] T025 [P] [US1] Create `apps/discord_bot/views/pvp_queue_view.py` (Cancel, Continue Search, explicit AI Practice fallback — no auto-AI)
- [x] T026 [US1] Redesign Battle hub in `apps/discord_bot/cogs/battle_cog.py` / `ArenaHubView`: Find Opponent, Friendly, AI Practice, Rivalries placeholder, Match History; defer immediately; respect `battle_pvp_enabled`
- [x] T027 [US1] Wire Find Opponent → `join_pvp_queue` + queue view in `apps/discord_bot/cogs/battle_cog.py`; compatibility guidance on `/battle bot` when PvP enabled
- [x] T028 [US1] Create `apps/discord_bot/tasks/pvp_matchmaker_job.py` (interval from config, expire rows, recover stale `matching`, dispatch matched runs)
- [x] T029 [US1] Register matchmaker in `apps/discord_bot/main.py`; trigger immediate `try_match_pvp_queue` after successful join
- [x] T030 [US1] Extract shared stadium orchestration into `apps/discord_bot/core/pvp_match.py` from Friendly patterns in `apps/discord_bot/cogs/battle_cog.py` (thread, mentions, snapshots, V3 stream, pitch/commentary; watch-only — no dual touchline)
- [x] T031 [US1] On match found: create stadium; on thread failure before kickoff abandon run, release locks, no energy; wire playback end to finalize hook (US2) or safe no-op stub with clear TODO only if US2 unfinished in same PR
- [x] T032 [US1] Ensure both manager locks remain held through playback; add Match History mode labels for PvP rows in hub history path in `apps/discord_bot/cogs/battle_cog.py` (or dedicated helper)

**Checkpoint**: US1 MVP — humans can queue and play a shared live PvP match (finalize rewards in US2)

---

## Phase 5: User Story 2 — Global LP only via Ranked PvP (Priority: P1)

**Goal**: Atomic `finalize_pvp_match` applies coins/XP/fatigue/injuries/LP/career once per side; Practice/Friendly cannot write LP; provisional LP protection

**Independent Test**: One PvP changes LP; Practice and Friendly leave LP and competitive PvP records unchanged; duplicate finalize idempotent

**Contracts**: [pvp-finalize.md](./contracts/pvp-finalize.md), [ai-practice-policy.md](./contracts/ai-practice-policy.md)

### Tests for User Story 2

- [x] T033 [P] [US2] Extend `tests/test_pvp_reward_policy.py` for provisional LP, coin multipliers, and non-pvp → 0 LP
- [x] T034 [US2] Add duplicate-finalization / economy idempotency coverage (scratch SQL or test harness) for `finalize_pvp_match`

### Implementation for User Story 2

- [x] T035 [US2] Extend `packages/leagues/leagues/match_points.py` (and SQL mirror) for provisional loss reduction + relative-rating LP used by finalize
- [x] T036 [US2] Implement `finalize_pvp_match` in `098_pvp_matchmaking_rivalries.sql`: dual economy via `apply_club_economy`, XP pipe, fitness/injuries, career PvP stats, LP both sides, two `match_history` rows, complete run, release locks; SQL guards reject non-pvp LP writes
- [x] T037 [US2] Wire `apps/discord_bot/core/pvp_match.py` full-time path to `finalize_pvp_match`; present two-sided reward/LP embeds via `apps/discord_bot/embeds/pvp_embeds.py`
- [x] T038 [US2] Confirm Friendly path in `apps/discord_bot/cogs/battle_cog.py` still awards zero coins/XP/LP and does not call PvP finalize; league fixtures untouched
- [x] T039 [P] [US2] Add SQL guards rejecting `match_type` practice/friendly with non-zero `global_lp_delta` in `098_pvp_matchmaking_rivalries.sql`

**Checkpoint**: Only Ranked PvP moves Global LP; finalize is once-only

---

## Phase 6: User Story 3 — AI Practice without competitive progress (Priority: P1)

**Goal**: Rename/convert Bot Battle to AI Practice (`run_type=practice`); capped rewards; zero LP/rivalry/PvP record; rollback path behind flag

**Independent Test**: Practice finalize never changes `global_lp` or rivalries; daily rewarded Practice cap; embed states No Global LP

**Contracts**: [ai-practice-policy.md](./contracts/ai-practice-policy.md), [battle-hub-surfaces.md](./contracts/battle-hub-surfaces.md)

### Tests for User Story 3

- [x] T040 [P] [US3] Tests in `tests/test_pvp_reward_policy.py` (and/or SQL harness) proving Practice cannot change LP or rivalries

### Implementation for User Story 3

- [x] T041 [US3] Implement `finalize_ai_practice_match` in `098_pvp_matchmaking_rivalries.sql` (energy/coins/XP capped; `global_lp_delta=0`; no rivalry; no PvP career; idempotent)
- [x] T042 [US3] Convert live hub Bot Battle path to Practice in `apps/discord_bot/cogs/battle_cog.py` + `apps/discord_bot/core/match_rewards.py` when `battle_pvp_enabled`; keep legacy LP bot path only for flag-off rollback
- [x] T043 [US3] Apply new/established Practice multipliers + daily rewarded cap from `game_config`; update Practice result embed in `apps/discord_bot/embeds/pvp_embeds.py` (**No Global LP**)
- [x] T044 [US3] Timeout / hub AI Practice buttons call Practice path only (never escalate to `pvp`) in `apps/discord_bot/views/pvp_queue_view.py` and `apps/discord_bot/cogs/battle_cog.py`

**Checkpoint**: AI Practice cannot produce competitive points

---

## Phase 7: User Story 7 — Recover safely across restarts (Priority: P1)

**Goal**: Queue survives restart; PvP runs recover/resume or deterministic complete-once; `completing` retry; no duplicate rewards; orphan lock reconcile

**Independent Test**: Restart while queued; restart mid-run; duplicate finalize; abandon pre-kickoff

### Implementation for User Story 7

- [x] T045 [US7] Persist/restore queue visibility in hub via `get_battle_hub_state` + expire cleanup in `apps/discord_bot/tasks/pvp_matchmaker_job.py` / `apps/discord_bot/cogs/battle_cog.py`
- [x] T046 [US7] Add active PvP run recovery in `apps/discord_bot/core/pvp_match.py` (reuse seed/snapshots; complete-once finalize)
- [x] T047 [US7] Retry `completing` runs idempotently from matchmaker/recovery job; extend `reconcile_orphaned_match_locks` usage for dual PvP locks in `apps/discord_bot/core/match_runs.py` / matchmaker
- [x] T048 [P] [US7] Add structured queue/match metrics logs in `apps/discord_bot/tasks/pvp_matchmaker_job.py`

**Checkpoint**: Restarts cannot duplicate coins/XP/LP or leak energy

---

## Phase 8: User Story 5 — Manager rivalries (Priority: P2) — Slice 2

**Goal**: Track ranked meetings; activate after 3 in 30 days; dormancy 60 days; presentation-only callouts; Rivalries hub + server board; badge keys; Friendly Rematch

**Independent Test**: Third ranked meeting activates rivalry; Practice/Friendly never count; sim odds unchanged; Rematch is Friendly-only

**Contracts**: [rivalry-presentation.md](./contracts/rivalry-presentation.md)

### Tests for User Story 5

- [x] T049 [P] [US5] Extend `tests/test_pvp_rivalry_math.py` for lead change, streak, revenge, milestones, badge eligibility

### Implementation for User Story 5

- [x] T050 [US5] Upsert rivalry + detect events + badge keys inside `finalize_pvp_match` when `pvp_rivalries_enabled` in `098_pvp_matchmaking_rivalries.sql`; add `get_manager_rivalries` + `get_rivalry_detail` RPCs
- [x] T051 [P] [US5] Pre-match and full-time rivalry fields in `apps/discord_bot/embeds/pvp_embeds.py` / `apps/discord_bot/core/pvp_match.py` (presentation only)
- [x] T052 [US5] Create `apps/discord_bot/views/rivalries_view.py` list + detail (H2H, last 5 from history, streaks, badges, Friendly Rematch)
- [x] T053 [US5] Wire Rivalries button in `apps/discord_bot/cogs/battle_cog.py`; server rivalry leaderboard under Rivalries (and optional `/leaderboard` if flagged)
- [x] T054 [US5] Ensure Practice/Friendly paths never call rivalry update (grep + SQL guards)

**Checkpoint**: Repeated PvP meetings create accurate rivalry stories without sim buffs

---

## Phase 9: User Story 6 — Privacy, blocking, preferences (Priority: P2)

**Goal**: Block managers; rivalry DM/callout/LB prefs; no presence/login alerts; Friendly respects blocks

**Independent Test**: Block stops ranked pair + Friendly invite; prefs mute surfaces; no rival-online feature exists

### Implementation for User Story 6

- [x] T055 [US6] Implement `set_pvp_block` RPC in `098_pvp_matchmaking_rivalries.sql`; ensure matcher already excludes blocks (US4)
- [x] T056 [US6] Reject Friendly challenges when blocked either direction in `apps/discord_bot/cogs/battle_cog.py`
- [x] T057 [US6] Rivalry detail actions: Block + notification/visibility prefs updating `players` columns via RPC/helpers in `apps/discord_bot/views/rivalries_view.py`
- [x] T058 [US6] Rate-limited rivalry result DMs respecting prefs in `apps/discord_bot/core/pvp_match.py` (or small notifier helper); explicitly do **not** add login/presence notifications
- [x] T059 [P] [US6] Privacy/block tests in `tests/test_pvp_matchmaking.py` (and Friendly block unit/integration as practical)

**Checkpoint**: Managers can opt out of presentation and avoid specific opponents

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Ops, soak, SDD sync, changelog — after desired stories

- [x] T060 [P] Create `scratch/check_053_pvp_ready.py` and `scratch/pvp_soak_report.py`
- [x] T061 Document rollback + soak stages in `specs/053-pvp-matchmaking-rivalries/quickstart.md` (align with flag stages)
- [x] T062 Run pure PvP pytest suite + schema verify after 098 apply on clone
- [ ] T063 Internal-guild soak: enable PvP → rewards → rivalries per rollout stages; keep rollback path ≥ one soak window
- [x] T064 [P] Update `change_log.md` player-facing copy for Ranked PvP / AI Practice / Rivalries
- [x] T065 Reconcile `.specify/specs/v1.0.0/spec.md` + `plan.md` for Battle PvP behavior
- [x] T066 Grep cleanup: no leftover Practice→LP paths; no `discord` imports under `packages/pvp/`; all new RPCs have call sites
- [ ] T067 Complete acceptance record / archive notes for Feature 053 when soak clears (mirror 052 pattern)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup**: Allowed before 052 ACCEPT (read-only audit)
- **Phase 2 Foundational**: Depends on Setup; **blocked for shared/prod apply until 052 ACCEPT**; blocks all stories
- **Phase 3 US4**: Depends on Foundational — fairness before public queue UX
- **Phase 4 US1**: Depends on US4 (safe matcher) — MVP stadium loop
- **Phase 5 US2**: Depends on US1 playback end hook
- **Phase 6 US3**: Depends on Foundational + hub from US1; can parallelize with US2 after hub exists if careful of `battle_cog.py` conflicts
- **Phase 7 US7**: Depends on US1+US2 (runs + finalize)
- **Phase 8 US5**: Depends on US2 finalize (slice 2)
- **Phase 9 US6**: Depends on US5 surfaces + US4 block exclusions
- **Phase 10 Polish**: After desired stories

### User Story Dependencies

```text
Setup → Foundational → US4 → US1 → US2 → US7
                         ↘ US3 (after hub)
US2 → US5 → US6
```

### Parallel Opportunities

- T002/T003/T004 after T001 started
- T006/T007/T008 and T010 in parallel during Foundational
- T012, T016, T017 in parallel after T011 spine started
- T024/T025 parallel in US1
- T033/T039 parallel in US2
- US3 vs US7 after US2 if different owners avoid same-file clashes
- T060/T064 parallel in Polish

### Parallel Example: Foundational pure package

```bash
Task: "Implement matchmaking.py widening/scoring"
Task: "Implement rivalry_math.py"
Task: "Implement reward_policy.py"
Task: "Add three pytest files"
```

### Parallel Example: US1 embeds/views

```bash
Task: "Create pvp_embeds.py"
Task: "Create pvp_queue_view.py"
```

---

## Implementation Strategy

### MVP First (Slice 1 core)

1. Phase 1 audit  
2. Phase 2 foundation (after 052 ACCEPT for DB apply)  
3. US4 fairness  
4. US1 queue + stadium  
5. US2 finalize LP/rewards  
6. **STOP and VALIDATE** quickstart §§3–5  
7. Then US3 Practice + US7 recovery before any production guild enable

### Incremental Delivery

1. Setup + Foundational → schema dark  
2. US4 → fair matcher  
3. US1 → playable shared PvP (MVP demo)  
4. US2 → competitive integrity  
5. US3 → Bot Battle retirement  
6. US7 → restart safety  
7. US5 → rivalries  
8. US6 → toxicity controls  
9. Polish → soak + changelog + ACCEPT

### Suggested MVP scope

**US4 + US1 + US2** (fair queue → shared match → dual finalize with LP). US3 required before removing Bot Battle LP from live hubs. US5/US6 are Slice 2.

---

## Notes

- [P] = different files, no incomplete dependencies
- Do not start Phase 2 production apply before 052 ACCEPT
- Prefer extending Friendly stadium extraction over duplicating `battle_cog.py`
- Watch-only PvP: do not enable dual TouchlineView for ranked MVP
- Commit after each task or logical group when user requests commits
- Stop at checkpoints to validate independently
