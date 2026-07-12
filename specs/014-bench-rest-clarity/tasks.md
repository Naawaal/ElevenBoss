# Tasks: Bench Rest Clarity

**Input**: Design documents from `/specs/014-bench-rest-clarity/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Required — pure bench selection + reward fatigue-gate unit tests (plan.md).

**Reporter evidence (locks defect)**:
- Match type: **bot** (×2)
- Cards: **fatigue = 0**, player **on bench**
- Cap-100 / “already fresh” **ruled out** — +25 must be visible if fitness ran for that card
- Live `fatigue_bench_per_match = 25` already on DB

**Locked decisions** (research.md / plan.md):
- Add `match_history.fatigue_applied_at`; gate fitness separately from `xp_applied_at` (bot + league)
- Keep max **7** rested; order by **`overall` DESC**
- Match-end bench-rest copy + non-silent fitness failure signal
- Friendlies stay sandbox; no +25 retune; no rest-all-unused in MVP
- Migration **`059_fatigue_applied_at.sql`**

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [x] T001 Grep `xp_applied_at`, `apply_post_match_fitness`, `fetch_bench_ids`, `post-match fatigue`, `apply_bot_match_rewards`, `league_rewards`; confirm touch list matches `plan.md`; note reporter case (fatigue 0 + bench + bot)

---

## Phase 2: Foundational — Schema gate (blocks US2/US3 wiring)

**Goal**: Crash-safe column exists before reward helpers change

**Independent Test**: Migration applies; `verify_required_schema.sql` passes for new column

- [x] T002 Create `supabase/migrations/059_fatigue_applied_at.sql`: `ALTER TABLE match_history ADD COLUMN IF NOT EXISTS fatigue_applied_at TIMESTAMPTZ`; end-of-file / extend guard per `data-model.md`
- [x] T003 Extend `supabase/scripts/verify_required_schema.sql` with `column:public.match_history.fatigue_applied_at` (and any guard pattern used by peers)
- [x] T004 [P] Add `scratch/apply_migration_059.py` (same pattern as `058`)

**Checkpoint**: Column ready on target DB before bot deploy that writes it

---

## Phase 3: US2 — Fitness actually applies after bot/league (P1) 🎯 MVP

**Goal**: Fatigue/injury post-process runs even when XP already marked; bench at 0 gains +25 on bot match when in rested set

**Independent Test**: `pytest tests/test_match_rewards_fatigue_gate.py`; manual bot match with fatigue-0 unused reserve → fatigue 25 (or to 100)

- [x] T005 [P] [US2] Add `mark_match_fatigue_applied` + fetch `fatigue_applied_at` in `apps/discord_bot/core/match_runs.py` (mirror `mark_match_xp_applied` / `fetch_match_reward_row` column list) per `contracts/fatigue-applied-gate.md`
- [x] T006 [US2] Rewrite early-return / fitness block in `apps/discord_bot/core/match_rewards.py`: apply XP if needed; apply fitness if `fatigue_applied_at` null; mark on success; do not treat `xp_applied_at` alone as full rewards-done
- [x] T007 [US2] Same gate pattern in `apps/discord_bot/core/league_rewards.py`
- [x] T008 [P] [US2] Create `tests/test_match_rewards_fatigue_gate.py`: mock db — when `xp_applied_at` set and `fatigue_applied_at` null, fitness RPC still invoked once; when both set, fitness not re-invoked

**Checkpoint**: Reporter case (bot + fatigue 0 + unused) can no longer be permanently skipped after an XP-only success

---

## Phase 4: US3 — Predictable top-7 bench rest (P2)

**Goal**: Highest-OVR unused healthy cards rest; manager can predict who gets +25

**Independent Test**: `pytest tests/test_bench_rest_selection.py`

- [x] T009 [P] [US3] Add pure `pick_bench_rest_ids` in `packages/player_engine/player_engine/bench_rest.py` (exclude starters/injured/retired; sort overall DESC; cap 7; optional id ASC tie-break) per `contracts/bench-selection-order.md`
- [x] T010 [P] [US3] Export from `packages/player_engine/player_engine/__init__.py`
- [x] T011 [P] [US3] Create `tests/test_bench_rest_selection.py` (10 unused → top 7 OVR; injured skipped; starters skipped)
- [x] T012 [US3] Update `fetch_bench_ids` in `apps/discord_bot/core/injury_rpc.py` to select `id, injury_tier, overall` (and retired filter) and use `pick_bench_rest_ids` (or equivalent `.order("overall", desc=True)` + same rules)

**Checkpoint**: Deep-squad “my named bench never moves” is deterministic, not random DB order

---

## Phase 5: US2 — Match-end visibility (P2)

**Goal**: Manager sees that bench rest ran or that fitness failed

**Independent Test**: Bot match result shows bench-rest line; forced fitness failure shows short warning (coins/XP still kept)

- [x] T013 [US2] Return / thread fitness summary from reward helpers (rested count or failure flag) without failing coin return
- [x] T014 [US2] Surface copy in bot match finalize path (`apps/discord_bot/cogs/battle_cog.py` and/or match result embed helper) per `contracts/match-end-bench-rest-copy.md`
- [x] T015 [US2] On fitness exception: log + manager-visible warning (footer/ephemeral); do not swallow silently; still leave `fatigue_applied_at` null for retry

**Checkpoint**: Silent “nothing happened” is gone for success and failure

---

## Phase 6: US1 — Docs / rules clarity (P3)

**Goal**: Published rules match behavior (bot/league rest, friendly sandbox, top-7 by OVR, cap 100)

**Independent Test**: Changelog + SDD mention competitive-only bench rest and crash-safe fatigue gate

- [x] T016 [P] [US1] Update `change_log.md` — bench rest reliability / match-end note (player-facing)
- [x] T017 [P] [US1] Brief reconcile in `.specify/specs/v1.0.0/spec.md` (fatigue gate + ordered top-7)
- [x] T018 [US1] Refresh `specs/014-bench-rest-clarity/spec.md` verdict with fatigue-0 bench evidence; mark stories done in checklist notes when shipped

---

## Phase 7: Polish

- [x] T019 Apply `059` on ElevenBoss Supabase via scratch script; run verify
- [x] T020 Run `pytest tests/test_bench_rest_selection.py tests/test_match_rewards_fatigue_gate.py -q`
- [x] T021 Grep confirm: no remaining early-return that skips fitness on `xp_applied_at` alone in `match_rewards.py` / `league_rewards.py`; friendlies still have no `apply_post_match_fitness`
- [x] T022 Follow `quickstart.md` — one bot match with fatigue-0 high-OVR unused reserve → +25 and match-end copy; Bisup `git pull` + restart after Python ship

---

## Dependencies

```text
T001
  → T002 → T003 → T004          (schema)
  → T005 → T006 → T007 → T008   (fatigue gate MVP — T005∥T008 after T002 conceptually; tests can land with mocks before apply)
  → T009 → T010 → T011 → T012   (ordered top-7; T009∥T010∥T011 then T012)
  → T013 → T014 → T015          (UX; needs reward helper return from T006)
  → T016 → T017 → T018          (docs)
  → T019 → T020 → T021 → T022  (ship verify)
```

- **Ship MVP after T002–T008 + T019** (gate fix unblocks fatigue-0 bench miss from crash window).
- **T009–T012** required if named bench still stuck after gate (deep squad / wrong 7).
- **T013–T015** required for visible confirmation.
- Bisup: apply `059` on Supabase, then `git pull` + `systemctl restart elevenboss`.

---

## Parallel opportunities

- T004 ∥ T003 after T002 drafted
- T009 ∥ T010 ∥ T011 after T001
- T016 ∥ T017 while T013–T015 in progress
- T008 can be written against the contract before live migration if mocks don’t need the column

---

## MVP scope (stop / validate)

1. T001–T008 + T019–T020 — crash-safe fitness on bot/league  
2. Manual: fatigue-0 bench + bot → **25**  
3. Then T009–T015 if still unclear who rested / no UI signal  
4. Docs T016–T018 + T021–T022 before calling done
