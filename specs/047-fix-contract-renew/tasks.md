# Tasks: Fix Contract Renew Stuck After First Renewal

**Input**: Design documents from `/specs/047-fix-contract-renew/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included — plan/quickstart call for `tests/test_contract_renew_fix.py` (key format / post-renew eligibility guard) plus SQL/Discord smoke. No full integration suite.

**Locked decisions** (research.md / plan.md):
- Root cause: permanent `contract_renewal:{card_id}` idempotency key
- Migration `087_fix_contract_renew_idempotency.sql` — per-attempt key (client UUID or UTC-minute bucket)
- Keep `RETURNS BOOLEAN`; bot re-fetches expiry for honest UI
- No ledger deletes; stuck cards self-heal on next renew
- Cite **US-42** — coins only via `apply_club_economy`

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: US1–US3 maps to spec user stories
- Exact file paths required

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm touch list and verify script expectations

- [x] T001 Grep `renew_contract`, `contract_renewal:`, `renew_callback`, and `to_regprocedure('public.renew_contract` across `apps/discord_bot/`, `supabase/migrations/`, and `supabase/scripts/verify_required_schema.sql`; confirm touch list matches `specs/047-fix-contract-renew/plan.md`
- [x] T002 [P] Note current 4-arg signature probe at `supabase/scripts/verify_required_schema.sql` (line ~325) must be updated when 5-arg RPC ships

**Checkpoint**: Touch list known; verify script gap documented

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Ship fixed `renew_contract` RPC — **MUST land before Discord story work depends on re-renew**

**⚠️ CRITICAL**: Do not edit already-applied migrations in place; forward file `087` only

- [x] T003 Create `supabase/migrations/087_fix_contract_renew_idempotency.sql`: `DROP FUNCTION IF EXISTS public.renew_contract(bigint, uuid, bigint, integer)`; recreate with optional `p_idempotency_key TEXT DEFAULT NULL`; effective key per `contracts/renew-idempotency.md`; preserve age ≥35, ownership, extend-from-now-if-expired, `apply_club_economy` pipe; `GRANT EXECUTE`; end with schema guard for new signature
- [x] T004 [P] Create `scratch/apply_migration_087.py` following `scratch/apply_migration_086.py` pattern for `087_fix_contract_renew_idempotency.sql`
- [x] T005 Update `supabase/scripts/verify_required_schema.sql` `renew_contract` `to_regprocedure` probe to the 5-arg signature `(bigint,uuid,bigint,integer,text)` (or equivalent that matches DEFAULT-arg catalog)
- [x] T006 Apply migration locally/remote via `python scratch/apply_migration_087.py` and run verify (`python scratch/verify_schema_full.py` or `verify_required_schema.sql`)

**Checkpoint**: Fixed RPC live in DB; verify passes; old 4-arg overload gone

---

## Phase 3: User Story 1 — Renew works every time a manager pays (Priority: P1) 🎯 MVP

**Goal**: Second+ renewals charge (when not duplicate attempt) and actually extend `contract_expires_at`; double-tap safe

**Independent Test**: Card with historical `contract_renewal:{uuid}` ledger + past grace → renew once → expiry in future → match/squad gate clears

**Contract**: [contracts/renew-idempotency.md](./contracts/renew-idempotency.md)

### Tests for User Story 1

- [x] T007 [P] [US1] Add `tests/test_contract_renew_fix.py` covering: expected effective-key shape documentation/helper if extracted; post-renew “still past grace ⇒ not success” guard logic (pure, if factored); assert permanent key format is not used by new bot caller

### Implementation for User Story 1

- [x] T008 [US1] Update `apps/discord_bot/cogs/player_cog.py` `renew_callback` to pass a per-click `p_idempotency_key` (UUID) into `renew_contract`
- [x] T009 [US1] After RPC in `renew_callback`, re-select `contract_expires_at`, load `contract_grace_days`, and only show success when `contract_blocks_xi` is false; include new expiry in success copy per `contracts/renew-profile-ui.md`
- [x] T010 [US1] SQL smoke from `quickstart.md`: renew stuck Roy Thompson (or equivalent) with unique 5th arg; confirm expiry advances; same key replay does not double-charge

**Checkpoint**: US1 MVP — re-renew works in SQL + profile path ready

---

## Phase 4: User Story 2 — Honest failure / age rules unchanged (Priority: P2)

**Goal**: Age ≥35, insufficient coins, and not-owned still fail clearly; no false “renewed” when expiry unchanged

**Independent Test**: Age ≥35 raises; low coins error leaves expiry unchanged; past-grace false success impossible after T009

**Contract**: [contracts/renew-profile-ui.md](./contracts/renew-profile-ui.md)

### Implementation for User Story 2

- [x] T011 [US2] Confirm migration still `RAISE`s age ≥35 and ownership failures in `087_fix_contract_renew_idempotency.sql` (grep/read; adjust if dropped)
- [x] T012 [US2] In `apps/discord_bot/cogs/player_cog.py` renew error path: surface RPC/insufficient-funds errors via existing `error_embed`; ensure “renew returned but still past grace” uses a clear ephemeral message (not success)
- [x] T013 [P] [US2] Extend `tests/test_contract_renew_fix.py` (or age tests) to keep `can_renew_contract(35) is False` / document RPC age guard unchanged

**Checkpoint**: US2 — failure modes honest; lifecycle gate intact

---

## Phase 5: User Story 3 — Affected clubs recover without manual SQL (Priority: P2)

**Goal**: Stuck cards self-heal via normal renew after deploy; ops path documented

**Independent Test**: After migrate + bot restart, Crimson FC renews Roy Thompson on `/player-profile` → past-grace gate gone (no ledger DELETE)

### Implementation for User Story 3

- [x] T014 [US3] Discord smoke: `/player-profile` on stuck human card → Renew → success with new expiry → battle/squad no longer names that card as past grace
- [x] T015 [P] [US3] Ensure `specs/047-fix-contract-renew/quickstart.md` ops note remains accurate (prefer player renew; emergency = call fixed RPC with unique key; no ledger delete)
- [x] T016 [P] [US3] Optional polish: remove or uniquify static `custom_id="renew_contract_profile"` in `apps/discord_bot/cogs/player_cog.py` so stale views fail closed (non-blocking if time-boxed)

**Checkpoint**: US3 — live stuck clubs recoverable by players

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Ship hygiene

- [x] T017 [P] Add player-facing renew fix note to `change_log.md`
- [x] T018 Run `pytest tests/test_contract_renew_fix.py -q` (and related age/wages tests if touched) and mark quickstart Discord smoke complete
- [x] T019 Confirm no new slash commands/tables; grep `renew_contract` callers updated for optional 5th arg; no direct `players.coins` UPDATE

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Start immediately
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS** reliable re-renew
- **US1 (Phase 3)**: After Foundational (RPC must exist for smoke; bot can be coded in parallel after T003 drafted)
- **US2 (Phase 4)**: After US1 UI honesty (T009) or alongside T011 migration confirm
- **US3 (Phase 5)**: After US1 + migration applied + bot deploy
- **Polish (Phase 6)**: After desired stories complete

### User Story Dependencies

| Story | Depends on | Notes |
|-------|------------|-------|
| US1 Re-renew works | Phase 2 | MVP hotfix |
| US2 Honest failures | US1 UI path | Age guard is migration-side |
| US3 Self-heal stuck clubs | US1 + deploy | No separate data migration |

### Parallel Opportunities

- T002 with T001
- T004 apply script while T003 SQL is written
- T007 tests while T003/T008 in progress
- T015 / T016 / T017 in parallel during smoke prep

---

## Parallel Example: Foundational

```text
Task: "Write 087_fix_contract_renew_idempotency.sql"
Task: "Create scratch/apply_migration_087.py"
Task: "Update verify_required_schema.sql renew_contract probe"
```

---

## Parallel Example: User Story 1

```text
Task: "Add tests/test_contract_renew_fix.py"
Task: "Wire p_idempotency_key + expiry check in player_cog.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 Setup  
2. Phase 2 Migration 087 + verify  
3. Phase 3 Bot renew honesty + SQL smoke (Roy Thompson)  
4. **STOP and VALIDATE**: stuck card renews and match gate clears  
5. Deploy bot

### Incremental Delivery

1. Foundational RPC → DB fixed  
2. US1 profile path → players unblocked  
3. US2 tighten failure copy / age confirm  
4. US3 Discord smoke + changelog  
5. Optional custom_id polish  

### Suggested MVP scope

**Phases 1–3 (US1)**: migration + profile renew with UUID key and post-expiry check. Enough to unblock Crimson FC / Roy Thompson.

---

## Notes

- [P] = different files or safely parallel
- Never patch remote-applied `047_audit_remediation.sql` in place — only forward `087`
- Commit after each phase checkpoint when implementing
- Stop at US1 checkpoint to unblock production if needed

