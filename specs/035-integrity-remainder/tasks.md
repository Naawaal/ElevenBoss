# Tasks: Game Integrity Remainder (US-42.6–42.10)

**Input**: Design documents from `/specs/035-integrity-remainder/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Parent**: `specs/029-game-integrity` (US-42) | **Depends on**: Locked `030`–`034`

**Tests**: Required — `tests/test_economy_registry_guards.py`, `tests/test_marketplace_integrity_guards.py`, `tests/test_job_catalog_guards.py` (+ extend transfer race tests if present).

**Locked decisions** (research.md / remainder-audit.md):
- One folder; waves **W7 ∥ W6 → W8 → W9 → W10**
- Living registry + catalogs as markdown contracts + pytest greps
- Marketplace purchase RPC **already OK** — lock with tests; Soft tax sink / expiry key
- Gems/`tokens` = N/A in registry until product defines mutations
- Default **no migration 078** unless Critical SQL appears
- Do not reopen Locked 42.1–42.5; no new hubs / second pipes

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: `[US1]`=W6 market · `[US2]`=W7 economy · `[US3]`=W8 jobs · `[US4]`=W9 RPC · `[US5]`=W10 security

---

## Phase 1: Setup — W0 audit confirm

**Purpose**: Confirm Critical list still matches code before filling catalogs

- [x] T001 Re-confirm `specs/035-integrity-remainder/contracts/remainder-audit.md` against `purchase_transfer_listing` / `apps/` coins UPDATE grep / `main.py` job list
- [x] T002 [P] Note ordered wave list in `specs/035-integrity-remainder/checklists/requirements.md` Notes
- [x] T003 [P] Confirm next migration would be `078` only if needed; default path = docs+tests only

**Checkpoint**: Audit current

---

## Phase 2: User Story 2 — Economy registry (W7 / P0) 🎯 MVP-B

**Goal**: Living faucet/sink registry + pipe greps (SC-002)

### Tests

- [x] T004 [P] [US2] Create `tests/test_economy_registry_guards.py`: no `players` + `coins` direct UPDATE/assign patterns under `apps/`; friendly path still non-faucet (reuse or cite `033` greps); registry markdown exists and contains seed ids (`match_`, `transfer_`, `season_prize`, `daily_login`, etc.)

### Implementation

- [x] T005 [US2] Grep all `apply_club_economy` / `apply_match_economy` / economy RPC call sites under `apps/` and `supabase/migrations/` (latest prize/transfer/store paths)
- [x] T006 [US2] Complete `specs/035-integrity-remainder/contracts/economy-source-sink-registry.md` to **100%** of known mutations (merge duplicates; mark Soft tax burn; tokens N/A)
- [x] T007 [P] [US2] Document minimum inflation signals (duplicate-key hits, faucet velocity query notes) in registry Notes or short subsection
- [x] T008 [P] [US2] Confirm INV-11 friendly non-faucet still locked (no new faucet wire)

**Checkpoint**: Registry reviewable + greps green

---

## Phase 3: User Story 1 — Marketplace integrity (W6 / P1) 🎯 MVP-A

**Goal**: Race/own-buy/busy-list locked by tests (SC-001)

### Tests

- [x] T009 [P] [US1] Create `tests/test_marketplace_integrity_guards.py`: SQL/source asserts `purchase_transfer_listing` has `FOR UPDATE` or equivalent lock, own-buy raise, `transfer_buy:` / `transfer_sale:` keys; `create_transfer_listing` references `assert_card_action_allowed` / `list_transfer`; statuses include active/sold/cancelled/expired
- [x] T010 [P] [US1] Extend or cite `tests/test_transfer_market_race.py` (or smoke) — document how race is proven if live-only

### Implementation

- [x] T011 [US1] Fix **only** Critical market holes found by T009 (do not rewrite RPC if already compliant)
- [x] T012 [P] [US1] Soft: ensure `transfer_tax_burn` row accurate in registry; **skip** 078 tax sink unless product insists
- [x] T013 [P] [US1] Soft: expiry job idempotency note in job catalog / marketplace contract — skip per-listing key unless cheap

**Checkpoint**: Market integrity test-locked

---

## Phase 4: User Story 3 — Job catalog (W8 / P1)

**Goal**: Every `main.py` job documented with run-key/catch-up (SC-003)

### Tests

- [x] T014 [P] [US3] Create `tests/test_job_catalog_guards.py`: parse or assert each scheduler job name registered in `apps/discord_bot/main.py` appears in `contracts/job-catalog.md`

### Implementation

- [x] T015 [US3] Read `apps/discord_bot/main.py` scheduler registrations; complete `specs/035-integrity-remainder/contracts/job-catalog.md` (module path, schedule intent, run_key, catch_up, notes → RPC/`_run_once`)
- [x] T016 [P] [US3] Spot-check league lifecycle / transfer expiry / payroll rows point at durable idempotency (no divergent prize cron)
- [x] T017 [P] [US3] Soft only: add missing run-key in a job module if Critical hole found — else document existing RPC keys

**Checkpoint**: Job catalog complete

---

## Phase 5: User Story 4 — RPC guarantees (W9 / P0)

**Goal**: Checklist artifact + enforce on any new SQL this feature adds (SC-004)

### Implementation

- [x] T018 [P] [US4] Finalize `specs/035-integrity-remainder/contracts/rpc-guarantee-checklist.md` (already seeded — ensure review-ready wording)
- [x] T019 [P] [US4] Sample-note transfer + `apply_club_economy` + prize RPCs as compliant in checklist
- [x] T020 [US4] If any migration `078+` is added in this feature: extend `supabase/scripts/verify_required_schema.sql` + scratch apply/smoke; else mark N/A in checklist Notes

**Checkpoint**: W9 process ready

---

## Phase 6: User Story 5 — Security & edges (W10 / P1)

**Goal**: Threat model + edge catalog + stale UX (SC-005)

### Tests

- [x] T021 [P] [US5] Grep/assert marketplace/store interaction paths fail closed on ownership mismatch or include reject patterns (source-level; cite existing checks)

### Implementation

- [x] T022 [US5] Complete `specs/035-integrity-remainder/contracts/threat-model.md` (soft controls only)
- [x] T023 [US5] Complete `specs/035-integrity-remainder/contracts/edge-catalog-remainder.md` — ≥1 row per applicable epic §8 category for W6–W10
- [x] T024 [P] [US5] Soft anti-abuse: confirm floors/holds/caps cited from `017` / registry — no hard-ban system

**Checkpoint**: W10 docs Done

---

## Phase 7: Polish & Cross-Cutting

- [x] T025 [P] Run `pytest tests/test_economy_registry_guards.py tests/test_marketplace_integrity_guards.py tests/test_job_catalog_guards.py -q`
- [x] T026 [P] Update `change_log.md` **only** if managers see new market/economy copy; else note enforcement-only in checklist
- [x] T027 Run `quickstart.md` Validations 0–6; set `specs/035-integrity-remainder/spec.md` Status → Locked
- [x] T028 Confirm zero new slash commands / no second economy-XP pipe / no `026` calendar rewrite / no reopen of `030`–`034` behavior
- [x] T029 [P] Pointer in `.specify/specs/v1.0.0/spec.md` to `specs/035-integrity-remainder` (US-42.6–42.10)
- [x] T030 [P] Confirm `specs/029-game-integrity/spec.md` still cites `035` consolidate note
- [x] T031 [P] Mark all tasks complete in this file when implement finishes

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1**: Immediate
- **Phase 2 US2 (W7)**: First Critical doc — can parallel Phase 3
- **Phase 3 US1 (W6)**: Parallel with Phase 2
- **Phase 4 US3 (W8)**: After W7 seed helpful; independent
- **Phase 5 US4 (W9)**: Anytime; before Lock if 078 added
- **Phase 6 US5 (W10)**: After W6–W8 catalogs exist for cross-links
- **Phase 7**: After W6+W7 minimum; prefer all waves

### User Story / Wave map

| Story | Wave | Priority |
|-------|------|----------|
| US2 | W7 Economy registry | P0 MVP-B |
| US1 | W6 Marketplace | P1 MVP-A |
| US3 | W8 Jobs | P1 |
| US4 | W9 RPC | P0 process |
| US5 | W10 Security | P1 |

### Parallel Opportunities

- T004 || T009 || T014 once paths known
- T005–T006 then T007 || T008
- T015 after main.py read; T018 || T019 anytime
- T022 || T023 in W10
- T026 || T029 || T030 in Polish

### MVP stop

After **T006 + T004** (registry + greps) and **T009** (market guards) — ship value before W8–W10 polish.

---

## Implementation Strategy

1. W0 audit confirm  
2. W7 fill registry + economy greps  
3. W6 marketplace source guards (+ Soft tax doc)  
4. W8 job catalog from `main.py`  
5. W9 checklist finalize  
6. W10 threat + edges  
7. Tests + Lock  

### Suggested stop points

| Stop | When |
|------|------|
| Registry MVP | After T008 |
| Market + registry | After T013 |
| Full remainder | After T031 |

---

## Notes

- [P] = different files, no incomplete dependencies
- Prefer markdown contracts over new DB registry tables
- Soft tax sink / gem pipe / per-listing expiry key deferred unless Critical
- Commit only when user requests
