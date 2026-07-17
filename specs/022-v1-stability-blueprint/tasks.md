# Tasks: v1 Stability Blueprint

**Input**: Design documents from `/specs/022-v1-stability-blueprint/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Required for Critical/High remediations per FR-003 / plan (extend existing race/math/parity tests; add Select/OVR asserts where fixes ship). No full Discord integration suite — Discord paths use quickstart persona steps.

**Locked decisions** (research.md / plan.md):
- Verify-first Wave 0 before writing fix code
- Select empty = omit Select + embed empty-state + Back (`view_helpers`)
- Legacy OVR = dry-run `scripts/fix_inflated_player_stats.py` then apply **or** defer with count
- Evo truthfulness = copy/config alignment only (not full `018` redesign)
- Flags stay default-off; migration `066_*` only if Critical reopen needs RPC fix
- No new slash commands / hubs / registry DB table

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: US1–US7 maps to spec user stories
- Exact file paths required

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm touch list and working tree alignment with the plan

- [x] T001 Grep `tick_evolution_match_progress`, `apply_club_economy`, `apply_bot_match_rewards`, `purchase_transfer_listing`, `process_club_weekly_payroll`, `award_manager_of_the_matchday`, `league_state_machine_job`, `auto_sim_expired_fixtures`, `discord.ui.Select` callers under `apps/discord_bot/` and `supabase/migrations/`; confirm touch list matches `specs/022-v1-stability-blueprint/plan.md`
- [x] T002 [P] Skim `specs/022-v1-stability-blueprint/contracts/` + `quickstart.md` and note which Verify IDs map to existing `tests/test_*.py` files (no code yet)

---

## Phase 2: Foundational — Wave 0 Verify (Blocking)

**Purpose**: Reclassify Verify/Suspect items with greps + pytest **before** any Open remediations

**CRITICAL**: Do not start US2–US6 code fixes until this phase updates the Issue Registry in `specs/022-v1-stability-blueprint/spec.md`

- [x] T003 Execute coin/XP bypass greps per `contracts/wave0-verify-greps.md` across `apps/discord_bot/` (C5); record hits or clean in Notes
- [x] T004 [P] Confirm zero Python callers of `tick_evolution_match_progress` under `apps/`; confirm friendly conclude path in `apps/discord_bot/cogs/battle_cog.py` stays sandbox (H2)
- [x] T005 [P] Confirm `apps/discord_bot/main.py` registers `league_state_machine_job` once @ 00:05 and that `auto_sim_expired_fixtures_job` in `apps/discord_bot/core/scheduler_jobs.py` skips `pacing_mode='dynamics'` (C4 / E8)
- [x] T006 [P] Run `pytest tests/test_transfer_market_race.py tests/test_transfer_market_math.py tests/test_wage_payroll_math.py tests/test_league_automation_rules.py tests/test_momd_selection.py tests/test_league_dynamics_windows.py tests/test_seasonal_promo_relegation.py tests/test_audit_fixes.py tests/test_economy_flows.py -q` and paste summary into registry Notes (or skip list if a file missing)
- [x] T007 [P] Run schema verify (`python scratch/verify_schema_full.py` or `supabase/scripts/verify_required_schema.sql`) when `DATABASE_URL` available; else mark H7 Verify deferred with reason (H7)
- [x] T008 Search `apps/discord_bot/` for leftover `debug-` file writers / dead `energy_regen_job` schedule (L1); note Open only if found
- [x] T009 Update Issue Registry statuses (Verify→Closed or Open+bundle) for C1–C5, H2, H4, H5, H7, H9, L1, L4 in `specs/022-v1-stability-blueprint/spec.md`

**Checkpoint**: Registry accurate; any failed Verify is Open with bundle; US1 can freeze the catalog; fix stories may begin for Open items only

---

## Phase 3: User Story 1 — Freeze Defect Registry (Priority: P1) MVP

**Goal**: One authoritative inventory with severity, module, status, expected behavior — no unnamed handwaves

**Independent Test**: Every Input-named concern and seed ID in `spec.md` has status + Notes after Wave 0; Intentional items labeled; no code required if all Verify pass

### Implementation for User Story 1

- [x] T010 [US1] Add a short **Wave 0 Results** subsection (date + pytest command + reopen list) under Assumptions or Notes in `specs/022-v1-stability-blueprint/spec.md`
- [x] T011 [US1] Confirm Intentional rows (friendly sandbox, L3, L5, M8, strike≥3 agent-sale if confirmed later) stay Intentional — not queued as Open fixes — in `specs/022-v1-stability-blueprint/spec.md`
- [x] T012 [US1] Cross-check registry IDs against `contracts/wave0-verify-greps.md`, `money-idempotency.md`, `select-empty-state.md`, `ovr-truth.md`, `edge-case-matrix.md` so every Open/Suspect ID appears in at least one contract

**Checkpoint**: MVP demoable as a trustworthy registry even before code fixes

---

## Phase 4: User Story 2 — Critical Money & Races (Priority: P1)

**Goal**: Coins, ownership, payroll, MoMD, automation ticks stay atomic under double-invoke / concurrency

**Independent Test**: Race/payroll/MoMD retries ≤1 success; SC-001–SC-003

### Tests for User Story 2

- [x] T013 [P] [US2] Confirm / extend `tests/test_transfer_market_race.py` still encodes C1 (one success, zero double-debit) per `contracts/money-idempotency.md`
- [x] T014 [P] [US2] Add or extend a pure/smoke retry assertion for payroll week-key idempotency in `tests/test_wage_payroll_math.py` (or documented scratch smoke path referenced from registry Notes) for C2
- [x] T015 [P] [US2] Confirm MoMD uniqueness / empty-eligible cases remain covered in `tests/test_momd_selection.py` and note re-settle smoke for C3 in `specs/022-v1-stability-blueprint/quickstart.md`

### Implementation for User Story 2

- [x] T016 [US2] If C1/H4/H9 Open: repair `purchase_transfer_listing` / peer guards in latest transfer migration path + bot error mapping in `apps/discord_bot/views/marketplace_transfer.py` / `apps/discord_bot/cogs/marketplace_cog.py` (else mark Closed from T009)
- [x] T017 [US2] If C2 Open: repair payroll uniqueness / job retry in `supabase/migrations/` forward fix + `apps/discord_bot/tasks/weekly_payroll_job.py` (Conditional `066_*` only if needed)
- [x] T018 [US2] If C3 Open: repair MoMD award idempotency path used by `apps/discord_bot/core/league_automation.py` / Journal hooks (forward migration only if needed)
- [x] T019 [US2] If C4 Open: fix double-sim / admin Start race in `apps/discord_bot/core/scheduler_jobs.py`, `apps/discord_bot/core/league_automation.py`, and `apps/discord_bot/cogs/admin_cog.py` gates
- [x] T020 [US2] If C5 Open: remove residual coin/XP bypasses in identified cog paths; route through `apps/discord_bot/core/economy_rpc.py` / `match_xp` pipes
- [x] T021 [US2] Re-run Wave 0 money pytest subset; set Critical IDs Closed with named check in `specs/022-v1-stability-blueprint/spec.md`

**Checkpoint**: Critical money IDs Closed or still Verify-passed; skip code tasks that T009 already Closed

---

## Phase 5: User Story 3 — Select Empty-State UX (Priority: P2)

**Goal**: Empty option lists never become unexplained SelectMenu disappearance

**Independent Test**: Hospital last discharge / academy empty / transfer filter zero show empty copy + Back (SC-007)

### Tests for User Story 3

- [x] T022 [P] [US3] Add a small pure helper unit test in `tests/test_select_empty_state.py` for “no Select when options empty” decision helper (if extracted as testable pure/predicate in `view_helpers` or sibling)

### Implementation for User Story 3

- [x] T023 [US3] Implement `add_select_if_options` (and optional empty-state line helper) in `apps/discord_bot/core/view_helpers.py` per `contracts/select-empty-state.md`
- [x] T024 [US3] Wire hospital admit/discharge rebuild + empty copy in `apps/discord_bot/views/store_facilities.py` (H1)
- [x] T025 [P] [US3] Wire academy empty Select + recovery copy in `apps/discord_bot/views/academy_hub.py` (H1)
- [x] T026 [P] [US3] Wire Transfer Board / My Listings zero-result empty copy + Change Filters/Back in `apps/discord_bot/views/marketplace_transfer.py` (H1)
- [x] T027 [US3] Grep remaining `discord.ui.Select` in `apps/discord_bot/views/`; apply same pattern where option lists can empty; note out-of-scope hubs in registry Notes
- [x] T028 [US3] Mark H1 Closed in `specs/022-v1-stability-blueprint/spec.md` with quickstart persona steps cited

**Checkpoint**: Select empty-state scripted paths pass ≥95% checklist

---

## Phase 6: User Story 4 — OVR Truth (Priority: P2)

**Goal**: New cards overall == True OVR; legacy inflation disposition recorded; progression does not overshoot POT

**Independent Test**: ≥50 new cards equal; dry-run count + apply/defer decision (SC-004)

### Tests for User Story 4

- [x] T029 [P] [US4] Add/extend factory True OVR equality asserts in `tests/` (or existing factory/pack test module) sampling ≥50 creates per `contracts/ovr-truth.md`

### Implementation for User Story 4

- [x] T030 [US4] Dry-run `python scripts/fix_inflated_player_stats.py`; record inflated count in H3 Notes in `specs/022-v1-stability-blueprint/spec.md`
- [x] T031 [US4] Ops disposition: either apply fair rebalance via script **or** defer with same count documented — update H3 status/Notes in `specs/022-v1-stability-blueprint/spec.md`
- [x] T032 [US4] Spot-check allocate / evo claim / mentor paths keep overall/POT coherent (`packages/player_engine/`, related RPCs); fix shared helper once if drift proven
- [x] T033 [US4] Align evolution hub copy/slots/cooldown/cost with live config (no false PlayStyle promise) in `apps/discord_bot/cogs/development_cog.py` and related views (H8 / B-Evo-Truth) — truthfulness only, not full 018 redesign

**Checkpoint**: H3 disposition done; H8 copy truth closed or residual noted without PlayStyle lie

---

## Phase 7: User Story 5 — Match & Progression Parity (Priority: P2)

**Goal**: Bot/league pipes correct; friendly sandbox; evo ticks once; gates agree

**Independent Test**: Three match-type checklist + one-tick evo (SC-005 / SC-006)

### Implementation for User Story 5

- [x] T034 [US5] Document bot vs league vs friendly reward matrix results in `specs/022-v1-stability-blueprint/quickstart.md` after tracing `apps/discord_bot/core/match_rewards.py`, `league_rewards.py`, `battle_cog.py`
- [x] T035 [US5] If H6 Proven: re-validate XI / squad at match lock/start in `apps/discord_bot/cogs/battle_cog.py` + `apps/discord_bot/core/squad_validity.py`; else mark Disproven/Closed
- [x] T036 [US5] If H5 Open: fix claim-by-`owner_id` / DM notifier edge in `apps/discord_bot/views/level_reward_claim.py` + `apps/discord_bot/tasks/level_reward_notifier.py`
- [x] T037 [P] [US5] Confirm `tests/test_audit_fixes.py` still green for formation wingback bands (L4)
- [x] T038 [US5] Mark H2/H5/H6/L4 statuses final in `specs/022-v1-stability-blueprint/spec.md`

**Checkpoint**: Match-type parity + evo tick-once verified

---

## Phase 8: User Story 6 — Recent-Feature Edges (Priority: P2)

**Goal**: Prove/disprove E1–E12 before recommending flag enablement; fix Proven High+

**Independent Test**: All twelve Verdicts set; Proven High+ Closed (SC-008)

### Implementation for User Story 6

- [x] T039 [P] [US6] Probe E1–E2 mentor edges (`packages/player_engine/mentor_math.py`, mentor RPC, `/development` allocate UI); record Verdict in `specs/022-v1-stability-blueprint/spec.md`
- [x] T040 [P] [US6] Probe E3 hospital loop + M2 UI/RPC parity (`apps/discord_bot/views/store_facilities.py`, fatigue RPCs); record Verdict
- [x] T041 [P] [US6] Probe E4–E5 transfer flip/roster race (`marketplace_transfer.py`, purchase RPC); record Verdict; fix if Proven High
- [x] T042 [P] [US6] Probe E6–E7 wages shrink-window + strike≥3 agent-sale Intentional (`packages/economy/economy/wages.py`, payroll RPC, Finances copy); record Verdict
- [x] T043 [P] [US6] Probe E8–E10 dynamics/automation pause/force-end (`league_automation.py`, `admin_cog.py`, scheduler); record Verdict; fix Proven High
- [x] T044 [P] [US6] Probe E11 evo cancel cooldown farm + E12 retro claim after P2P; record Verdict; fix Proven High
- [x] T045 [US6] Fix any Proven High+ edges at the shared RPC/helper (not one-off UI); add/extend one failing-then-passing check per FR-003
- [x] T046 [US6] Set all E1–E12 Verdicts + close M1–M5 Suspects that were proved/disproved in `specs/022-v1-stability-blueprint/spec.md`

**Checkpoint**: Edge matrix complete; flags still default-off; pilot enablement recommendation written in Notes if green

---

## Phase 9: User Story 7 — Prioritized Sequence & Exit Gates (Priority: P3)

**Goal**: Waves executed in risk order; Low polish does not block v1 declare

**Independent Test**: Waves 0–3 exit gates mapped to SC; residual Low listed as backlog

### Implementation for User Story 7

- [x] T047 [US7] Add **Wave Exit Gate** checklist (SC-001–SC-008 with pass/fail) to `specs/022-v1-stability-blueprint/quickstart.md`
- [x] T048 [US7] Move unfinished Low/Medium (L2, M5, M6, M7 as applicable) to an explicit **Backlog** table in `specs/022-v1-stability-blueprint/spec.md` — not silent Open blockers
- [x] T049 [US7] Confirm no new slash command/hub/table shipped unless Critical Conditional Path — document SC-010 compliance in `specs/022-v1-stability-blueprint/spec.md`

**Checkpoint**: Stability bar declared with backlog honesty

---

## Phase 10: Polish & Cross-Cutting

**Purpose**: Hygiene, copy, changelog, SDD reconcile

- [x] T050 [P] Dual-ladder profile/league copy clarity (M6) in `apps/discord_bot/cogs/profile_cog.py` + `competitive_display.py`
- [x] T051 [P] Fix broken legacy tests (L2): `tests/test_injury_eta_backfill.py`, `tests/test_squad_swap_confirm.py` — full suite green
- [x] T052 [P] Remove pilot-only Run Cycle controls in `apps/discord_bot/cogs/admin_cog.py` only after midnight cron trusted (M7) — left with ponytail; remove when prod cron trusted
- [x] T053 Update `change_log.md` for any manager-visible fixes shipped in Waves 1–3
- [x] T054 Reconcile behavioral contract deltas into `.specify/specs/v1.0.0/spec.md` and `.specify/specs/v1.0.0/plan.md` if implement diverged — N/A this session
- [x] T055 Run full `specs/022-v1-stability-blueprint/quickstart.md` validation pass and tick Wave Exit Gate checklist

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Start immediately
- **Foundational Wave 0 (Phase 2)**: Depends on Setup — BLOCKS all fix stories
- **US1 (Phase 3)**: After Phase 2 (registry freeze / MVP)
- **US2 (Phase 4)**: After Phase 2; only code for IDs still Open
- **US3–US6 (Phases 5–8)**: After Phase 2; prefer US2 Critical closes before US3 if staffing serial; US3 can proceed in parallel once money Criticals green
- **US7 (Phase 9)**: After desired Waves 0–3 complete
- **Polish (Phase 10)**: After US7 or in parallel for timeboxed Low items

### User Story Dependencies

| Story | Depends on | Notes |
|-------|------------|-------|
| US1 Registry | Phase 2 | MVP — docs only |
| US2 Money | Phase 2 | Skip Closed Verify tasks |
| US3 Select | Phase 2; prefer after US2 Critical | H1 Open today |
| US4 OVR | Phase 2 | Can parallel US3 after money green |
| US5 Match | Phase 2 | Uses Wave 0 H2 results |
| US6 Edges | Phase 2; after US2 if touching same RPCs | E* Verdicts |
| US7 Sequence | US1 + Waves executed | Exit gates |

### Parallel Opportunities

- T003–T008 greps/tests largely [P] within Phase 2
- T013–T015 money test confirms [P]
- T025–T026 Select hub wires [P] after T023
- T039–T044 edge probes [P] across modules
- T050–T052 polish [P]

---

## Parallel Example: Phase 2 Wave 0

```text
Task: "Confirm zero Python tick_evolution callers + friendly sandbox (T004)"
Task: "Confirm scheduler single 00:05 + dynamics skip (T005)"
Task: "Run money/league pytest batch (T006)"
Task: "Schema verify if DATABASE_URL (T007)"
Task: "Debug/dead job search (T008)"
```

## Parallel Example: User Story 3 Select

```text
# After T023 helper lands:
Task: "Wire academy empty Select (T025)"
Task: "Wire marketplace empty/filter (T026)"
```

## Parallel Example: User Story 6 Edges

```text
Task: "Probe mentor E1–E2 (T039)"
Task: "Probe hospital E3 (T040)"
Task: "Probe transfer E4–E5 (T041)"
Task: "Probe wages E6–E7 (T042)"
Task: "Probe automation E8–E10 (T043)"
Task: "Probe evo/retro E11–E12 (T044)"
```

---

## Implementation Strategy

### MVP First (US1 only)

1. Phase 1 Setup
2. Phase 2 Wave 0 Verify + registry update
3. Phase 3 US1 registry freeze
4. STOP — demo trustworthy Issue Registry

### Incremental delivery (recommended)

1. MVP (US1)
2. US2 Critical money — only Open IDs
3. US3 Select (high manager visibility)
4. US4 OVR + US5 match parity
5. US6 edge matrix before any flag default-on talk
6. US7 exit gates + Phase 10 polish timebox

### Suggested MVP scope

**Phases 1–3 only** (Setup + Wave 0 + Registry freeze). That alone delivers FR-001 and stops rediscovering bugs. Code remediations start at Phase 4.

---

## Notes

- Tasks marked “If X Open” are no-ops when Wave 0 Closed them — check the box with “N/A Closed in T009” when skipping
- Conditional migration `066_*` only via US2 if Critical RPC reopen proven
- Do not invent seller DMs, bidding, or PlayStyle evo grants in this feature
- Commit cadence: after Phase 2, after each US that ships code, after polish
