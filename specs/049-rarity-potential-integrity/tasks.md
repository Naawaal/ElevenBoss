# Tasks: Rarity Potential Cap Integrity

**Input**: Design documents from `/specs/049-rarity-potential-integrity/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included — plan/quickstart require unit + property tests (`tests/test_rarity_potential_integrity.py`), extend `tests/test_potential_generation.py`, and Python↔SQL parity (`tests/test_rarity_potential_sql_parity.py`). Dry-run + double-run repair are ops validation gates, not optional.

**Locked decisions** (research.md / plan.md):
- Caps: Common 75 / Rare 85 / Epic 92 / Legendary 99 — only two hosts (Python + SQL `rarity_potential_cap`)
- Reject illegal OVR; never raise POT above rarity to match OVR
- Migrations **088** (guards + audit + RPC rewrites) then **089** (VALIDATE CHECKs after repair)
- Dry-run reimbursement report with EXACT / RECONSTRUCTED / MANUAL_REVIEW before any production mutate
- Cite **US-42.2 / US-42.7 / US-42.9**; refunds via `apply_club_economy` only
- No academy rarity redesign (clamp Common YA to ≤75); no marketplace damages; no mentor auto-reverse

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: US1–US4 maps to spec user stories
- Exact file paths required

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm live RPC definitions and touch list before coding

- [x] T001 Run `pg_get_functiondef` on dev/prod for `process_match_result`, `register_new_player`, `claim_daily_pack`, `process_youth_intake`, `sign_youth_scout_prospect`, `process_daily_academy_growth`, `allocate_skill_point`, `process_stat_drill`, `claim_evolution_reward`, `train_with_fodder`; note any drift vs repo migrations into `specs/049-rarity-potential-integrity/research.md` (append “Live defs” subsection)
- [x] T002 [P] Repo-wide classify POT writers: grep `potential`, `base_potential`, `model_copy`, `INSERT INTO player_cards`, `UPDATE.*potential` across `packages/`, `apps/discord_bot/`, `supabase/migrations/`, `scripts/`; confirm list matches plan touch list in `specs/049-rarity-potential-integrity/plan.md`

**Checkpoint**: Live authority + touch list known; no coding against stale RPC signatures

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Central Python rarity-cap helpers + card model invariant — **MUST land before generators, gates, or scripts**

**⚠️ CRITICAL**: No US1–US4 implementation until helpers + model validation exist

- [x] T003 Add `rarity_potential_cap`, `clamp_potential`, and `validate_potential_integrity` to `packages/player_engine/player_engine/potential.py` (KeyError/ValueError on unknown rarity — no `.get(rarity, 75)` for enforcement) per `contracts/rarity-potential-invariant.md`
- [x] T004 Fix `generate_potential` in `packages/player_engine/player_engine/potential.py`: reject `overall > rarity_cap`; final POT = `max(overall, MIN_POTENTIAL, min(candidate, cap))`; remove legacy “OVR may exceed rarity” escape
- [x] T005 Update `apply_dynamic_potential_boost` in `packages/player_engine/player_engine/potential.py` to require `rarity` and ceiling `min(rarity_cap, base_potential + MAX_DYNAMIC_BOOST)`
- [x] T006 Add Pydantic model-level validator on `CreatedPlayerCard` in `packages/player_engine/player_engine/created_card.py` calling `validate_potential_integrity`; if `model_copy` skips revalidation, document and enforce explicit validate-after-copy in producers
- [x] T007 Export new helpers from `packages/player_engine/player_engine/__init__.py`
- [x] T008 [P] Update `tests/test_potential_generation.py` for new `apply_dynamic_potential_boost(..., rarity)` signature and generation reject cases; keep existing happy-path coverage green

**Checkpoint**: Foundation ready — generators and SQL can share one Python law

---

## Phase 3: User Story 1 — Illegal potential cannot grow further (Priority: P1) 🎯 MVP

**Goal**: Stop new corruption and stop spending illegal POT headroom (Python producers + migration 088 RPC guards)

**Independent Test**: Dynamic boost / regen / youth / ingress / skill / drill / evolution / academy at rarity boundary never produce or consume POT above cap; illegal create/ingress rejected

**Contracts**: [rarity-potential-invariant.md](./contracts/rarity-potential-invariant.md), [card-ingress-reject.md](./contracts/card-ingress-reject.md), [progression-effective-pot.md](./contracts/progression-effective-pot.md)

### Tests for User Story 1

- [x] T009 [P] [US1] Add `tests/test_rarity_potential_integrity.py`: rarity boundary pass/fail; Epic 92+boost→92; regen/youth property asserts; `CreatedPlayerCard` illegal POT fails; seeded bulk generation across rarities/ages/positions
- [x] T010 [P] [US1] Add `tests/test_rarity_potential_sql_parity.py` (skip if no `DATABASE_URL`) asserting SQL `rarity_potential_cap` matches `RARITY_POT_CAPS` for all four rarities + unknown → NULL

### Implementation for User Story 1

- [x] T011 [P] [US1] Fix `packages/player_engine/player_engine/player_factory.py`: reject `target_ovr > rarity_cap` before generation; validate card after construction
- [x] T012 [P] [US1] Fix `packages/player_engine/player_engine/regen_pool.py`: replace hard `94` with `rarity_potential_cap(rarity)`; never leave unchecked `model_copy` POT above cap
- [x] T013 [P] [US1] Fix `packages/player_engine/player_engine/youth_intake.py`: `clamp_potential` after academy tier roll and gem bump (Common ≤75); no academy rarity redesign
- [x] T014 [P] [US1] Audit/fix remaining generators (`packages/player_engine/player_engine/procedural_generator.py`, gacha/support legendary paths under `packages/` / `apps/discord_bot/`) to use shared validate — no private rarity tables
- [x] T015 [US1] Update `packages/player_engine/player_engine/progression_gates.py` (and mentor eligibility callers if needed) to use effective POT = `min(stored, rarity_cap)`
- [x] T016 [US1] Create `supabase/migrations/088_rarity_potential_guards.sql`: `rarity_potential_cap(text)`; rewrite `process_match_result` dynamic POT with rarity; reject-not-raise on `register_new_player`, `claim_daily_pack`, `process_youth_intake`, `sign_youth_scout_prospect`; effective POT in `allocate_skill_point`, `process_stat_drill`, `claim_evolution_reward`, `process_daily_academy_growth`, `train_with_fodder` (+ mentor assert if in scope); create `potential_cap_repair_audit` + RLS; insert `game_config.potential_rarity_caps_enabled`; optional NOT VALID CHECKs; end with schema guard DO block
- [x] T017 [P] [US1] Extend `supabase/scripts/verify_required_schema.sql` for `function:rarity_potential_cap` (and audit table/policies/constraints as staged in 088)
- [x] T018 [US1] Add `scratch/apply_migration_088.py` (mirror `scratch/apply_migration_087.py`); apply 088 on dev; run verify script
- [x] T019 [US1] Mark unsafe or fix `scripts/recalculate_potentials.py` so it cannot recreate illegal POT via old `generate_potential` escape
- [x] T020 [US1] Grep all callers of changed Python helpers / RPC names in `apps/discord_bot/` and update bot paths that assemble card JSON so they do not rely on “raise POT to OVR” behavior

**Checkpoint**: US1 MVP — leak stopped in code + DB; safe to inventory without growing damage

---

## Phase 4: User Story 2 — Ops inventory + dry-run reimbursement report (Priority: P1)

**Goal**: Read-only anomaly inventory and per-card dry-run refund report with confidence labels — **non-negotiable before production mutate**

**Independent Test**: Script produces CSV/report with category A/B/C, proposed OVR/POT/stats, refunds, EXACT|RECONSTRUCTED|MANUAL_REVIEW|NONE; zero writes to `player_cards` / balances

**Contract**: [repair-reimbursement.md](./contracts/repair-reimbursement.md)

### Implementation for User Story 2

- [x] T021 [US2] Implement `scripts/potential_cap_audit.py`: anomaly SQL inventory; export full before-state; classify Category A/B/C; propose target OVR/POT/base/attrs using `balance_true_ovr` / attribution heuristics; label `refund_confidence`; `--dry-run` default (no writes)
- [x] T022 [P] [US2] Wire dry-run to optionally insert `repair_status=dry_run` rows into `potential_cap_repair_audit` **only** when explicitly flagged (still no card/balance mutation); keep default filesystem report under `reports/` or stdout
- [x] T023 [US2] Document MANUAL_REVIEW resolution checklist in script `--help` / module docstring: unclassified must be 0; material MANUAL_REVIEW needs human policy before US3 apply
- [x] T024 [US2] Run dry-run against dev/clone (or prod read-only); attach summary counts by rarity + confidence to ops notes; confirm Category A proposes `NONE` refunds

**Checkpoint**: US2 — reviewed dry-run exists; repair may not start until MANUAL_REVIEW policy clear

---

## Phase 5: User Story 3 — Repair cards + refund removed paid progression + notify (Priority: P2)

**Goal**: Fair Category A/B/C repair; idempotent refunds via economy pipe; grouped manager DMs after commit

**Independent Test**: Clone repair twice → second run 0 extra changes; anomaly 0; true OVR == stored; DMs reflect committed refunds (or “none required”)

**Contract**: [repair-reimbursement.md](./contracts/repair-reimbursement.md) · data-model audit table

### Implementation for User Story 3

- [x] T025 [US3] Implement `scripts/potential_cap_repair.py`: apply Category A/B/C mutations; adjust attrs then recalculate OVR (reuse `balance_true_ovr` in `packages/player_engine/player_engine/player_factory.py`); write audit before/after; refuse apply if unclassified/MANUAL_REVIEW unresolved
- [x] T026 [US3] Refund path: coins/energy via `apply_club_economy` with keys `potential_cap_fix:<batch>:<card>:<kind>`; SP updates keep `skill_points` / `skill_points_spent` consistent; never double-refund same removed point as drill + SP
- [x] T027 [US3] Idempotency: `UNIQUE(batch_id, card_id)` / second `--apply` same batch → 0 extra refunds/stat changes; assert in script self-check or small test harness
- [X] T028 [US3] Clone dry-run → apply → re-apply → anomaly COUNT = 0; true OVR equals stored for repaired rows
  - Sandbox `--batch rarity_pot_fix_20260731`: pass1 changed=131/sp=8/anom=0; pass2 changed=0.
  - **Blocked on ops**: live inventory shows **131** anomalies (123×A / 8×B); do not `--apply` until MANUAL_REVIEW policy + clone sign-off. Tooling ready: `scripts/potential_cap_repair.py`.
- [x] T029 [P] [US3] Add manager DM sender (ops script or thin helper under `apps/discord_bot/tasks/` / reuse `apps/discord_bot/core/scheduler_jobs.py` `_send_dm` pattern): one grouped DM per manager from audit after repair+refund success; log `notified_at` / `notification_error`; DM failure does not roll back
- [X] T030 [US3] Production window runbook execution only after clone sign-off: contain deployed → lock/snapshot → repair → refund → verify → notify (document commands used in quickstart notes)
  - Prod `--apply` batch `rarity_pot_fix_20260731`: 131 repaired, 24 SP across 8 Cat B, anomalies=0, idempotent re-apply, migration 089 validated.
  - Cat A incidental OVR rewrite from `recalculate_card_ovr` restored (34 cards) before notify.
  - Notify: chunked DMs ready; **re-run `--send` with production Discord token** (local `.env` pointed at Dev bot — 21/24 owners undeliverable / no mutual guild).

**Checkpoint**: US3 — historical fairness applied; managers informed of actual outcomes

---

## Phase 6: User Story 4 — Lock DB + monitor zero anomalies (Priority: P3)

**Goal**: VALIDATE CHECKs; schema verify; anomaly monitors at lifecycle boundaries; no silent auto-repair of new violations

**Independent Test**: Invalid Epic POT 93 write rejected; anomaly COUNT = 0 at deploy/startup/after youth/regen/academy/aging/match; CRITICAL log if non-zero

**Contract**: [rarity-potential-invariant.md](./contracts/rarity-potential-invariant.md)

### Implementation for User Story 4

- [x] T031 [US4] Create `supabase/migrations/089_validate_potential_integrity.sql` + `scratch/apply_migration_089.py`: VALIDATE constraints when anomaly = 0; final schema assertions; apply only after US3 prod/clone anomaly 0
- [x] T032 [P] [US4] Extend `supabase/scripts/verify_required_schema.sql` for final constraint names (`player_cards_potential_rarity_cap_chk`, `player_cards_base_potential_rarity_cap_chk`, `player_cards_overall_potential_chk`)
- [x] T033 [US4] Add anomaly COUNT helper + CRITICAL logging on bot startup in `apps/discord_bot/main.py` (and/or shared core helper); after lifecycle jobs in `apps/discord_bot/tasks/youth_intake_notifier.py`, `apps/discord_bot/tasks/regen_pool_job.py`, `apps/discord_bot/tasks/academy_growth_job.py`, and season aging path in `apps/discord_bot/core/scheduler_jobs.py` — log card_id/owner/rarity/OVR/POT; **do not** auto-repair
- [x] T034 [P] [US4] Update `change_log.md` with player-facing note: rarity absolute POT caps; Common academy ≤75; possible corrections/refunds for affected cards
- [x] T035 [US4] Plan sunset of temporary `game_config.potential_rarity_caps_enabled` after constraints validated (delete or no-op comment in migration note / follow-up task — must never re-open caps)

**Checkpoint**: US4 — recurrence structurally impossible; monitors watch for zero

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Full-suite confidence and quickstart alignment

- [x] T036 [P] Align `specs/049-rarity-potential-integrity/quickstart.md` with final script flags and migration names after implementation
- [x] T037 Run `pytest tests/ -q` (or at least potential + integrity + parity + progression-related suites); fix regressions from signature changes
- [x] T038 [P] Confirm no new slash commands/hub buttons/tables beyond audit; grep confirms superseded POT anti-patterns (`IF v_pot < overall THEN v_pot := overall`, regen `min(94`) gone from active code paths
- [x] T039 Run implementation-integrity + user-perspective checks (`.agents/skills/implementation-integrity-check`, `.agents/skills/user-perspective-check`) before calling feature done; cite US-42.2/42.7/42.9 on PR

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Start immediately
- **Foundational (Phase 2)**: After Setup — **BLOCKS all user stories**
- **US1 (Phase 3)**: After Foundational — **MVP / containment**; prefer before or in parallel with US2 inventory (US2 needs `rarity_potential_cap` SQL from T016+)
- **US2 (Phase 4)**: Needs 088 applied (T018) for accurate SQL inventory; **BLOCKS US3 production apply**
- **US3 (Phase 5)**: After US2 dry-run review + MANUAL_REVIEW policy
- **US4 (Phase 6)**: After US3 anomaly = 0 (VALIDATE must not run on dirty data)
- **Polish (Phase 7)**: After desired stories complete

### User Story Dependencies

```text
Setup → Foundational → US1 (containment MVP)
                         ↓
                       US2 (dry-run) ──→ US3 (repair/refund/DM) ──→ US4 (VALIDATE + monitors)
```

- **US1**: No dependency on repair; deployable alone as emergency containment
- **US2**: Depends on US1 SQL cap function for inventory queries
- **US3**: Depends on US2 reviewed report
- **US4**: Depends on US3 clean anomaly count

### Parallel Opportunities

- T001 ‖ T002 (Setup)
- T008 ‖ (after T003–T006)
- T009 ‖ T010 (US1 tests)
- T011 ‖ T012 ‖ T013 ‖ T014 (producer fixes, different files)
- T017 ‖ T016 drafting (verify list while migration authored)
- T022 ‖ T023 (US2 docs vs optional audit insert)
- T029 ‖ T025–T027 after repair API shape known
- T032 ‖ T034 ‖ T035 (US4 docs/verify/flag sunset)
- T036 ‖ T038 (Polish)

---

## Parallel Example: User Story 1

```text
# After Foundational (T003–T008):
Task: "Fix player_factory.py reject + validate"
Task: "Fix regen_pool.py rarity cap"
Task: "Fix youth_intake.py clamp"
Task: "Audit procedural_generator / gacha paths"
Task: "tests/test_rarity_potential_integrity.py"
# Then serialize migration 088 + apply + parity test
```

---

## Parallel Example: User Story 2

```text
Task: "potential_cap_audit.py dry-run core"
Task: "MANUAL_REVIEW checklist in docstring"
# Optional audit-table dry_run insert is separate flag
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 Setup (live defs + grep)
2. Phase 2 Foundational helpers
3. Phase 3 US1 producers + 088 + tests
4. **STOP and VALIDATE**: boundary tests green; illegal ingress rejected on dev
5. Deploy containment even if repair tooling unfinished

### Incremental Delivery

1. US1 containment deployed → leak stopped  
2. US2 dry-run reviewed → compensation policy locked  
3. US3 clone then prod repair/refund/DM  
4. US4 VALIDATE + monitors + change_log  
5. Polish full pytest + integrity checks  

### Suggested MVP scope

**US1 only** (Phases 1–3): central caps, generators, 088 RPC guards, progression effective POT, unit/parity tests.

---

## Notes

- [P] = different files, no incomplete deps
- Do not invent academy rarity tiers — clamp only
- Do not VALIDATE constraints (089) before anomaly = 0
- Do not credit marketplace overpayment algorithmically
- Do not reverse mentor transfers automatically
- Prefer shortest working diffs; reuse `balance_true_ovr` and existing DM helpers
