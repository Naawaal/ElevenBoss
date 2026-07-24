# Tasks: Marketplace Intelligence & Market Analytics

**Input**: Design documents from `/specs/043-marketplace-intelligence/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included — plan/quickstart/AGENTS require unit coverage for cohort/median/trend/sort/Best Value in `tests/test_market_intelligence.py`. Extend integrity greps where purchase history writes are asserted. No full Discord integration suite.

**Locked decisions** (research.md / plan.md):
- Enrich `transfer_sales_log` in place (no parallel sale table); forward-only snapshots
- New `card_ownership_history` without FK CASCADE to `player_cards`
- Cohort: role + rarity + OVR ±3; min sales 5; trend 7d vs prior 7d
- Board sorts in-app on filtered ≤50/≤25 set; Best Value = price/fair ascending
- Ops analytics via RPC only — no Discord admin dashboard; no new slash command
- Migration: `086_marketplace_intelligence.sql`; cite **US-42.6** on mutating PRs

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: US1–US6 maps to spec user stories
- Exact file paths required

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm touch list and apply-script scaffolding before schema work

- [x] T001 Grep callers of `purchase_transfer_listing`, `process_agent_sale`, `purchase_scouting_player`, `sign_youth_scout_prospect`, `transfer_sales_log`, and marketplace views; confirm touch list matches `specs/043-marketplace-intelligence/plan.md`
- [x] T002 [P] Create `scratch/apply_migration_086.py` from `scratch/apply_migration_085.py` pattern (point at `086_marketplace_intelligence.sql`; no-op until migration exists)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema shell, config, RLS, verify guards — **MUST complete before story RPC/UI wiring**

**⚠️ CRITICAL**: Do not ship bot discovery/sort/career UI against unapplied schema

- [x] T003 Author `supabase/migrations/086_marketplace_intelligence.sql`: ALTER `transfer_sales_log` snapshot columns (`fair_value_coins`, `rarity`, `role`, `overall`, `potential`, `age_at_sale`, `player_name`) + indexes per `data-model.md`; seed `game_config` keys `price_discovery_min_sales` / `price_discovery_ovr_window`
- [x] T004 In `086_marketplace_intelligence.sql`, create `card_ownership_history` (no FK to `player_cards`), unique open-segment index, supporting indexes, ENABLE RLS + SELECT/INSERT/UPDATE policies for bot roles per `contracts/ownership-history.md`
- [x] T005 In `086_marketplace_intelligence.sql`, add `ensure_card_ownership_open(p_card_id, p_owner_id, p_via)` and `get_card_ownership_history(p_card_id)` per ownership contract; GRANT execute; include migration schema-guard block
- [x] T006 Extend `supabase/scripts/verify_required_schema.sql` for new table, policies, functions, and config keys (watch `split_part` for function/policy entries)
- [x] T007 Apply via `scratch/apply_migration_086.py` and run `python scratch/verify_schema_full.py` (or `verify_required_schema.sql`) until green — re-apply after later RPC tasks land in the same file if edited before first apply

**Checkpoint**: Schema verified for history tables/helpers; user-story RPC replacements can proceed

---

## Phase 3: User Story 1 — Durable completed-transfer history (Priority: P1) 🎯 MVP

**Goal**: Every successful P2P purchase appends an immutable sales-log row with money + fair value + attribute snapshot

**Independent Test**: Complete one P2P buy → `transfer_sales_log` row has non-null snapshots; second sale appends; first row unchanged; failed buy inserts nothing

**Contract**: [contracts/transfer-history-enrichment.md](./contracts/transfer-history-enrichment.md)

### Implementation for User Story 1

- [x] T008 [US1] REPLACE `purchase_transfer_listing` in `supabase/migrations/086_marketplace_intelligence.sql` to read card attrs, compute `v_fair` via `compute_agent_offer`, and INSERT enriched `transfer_sales_log` (all snapshot columns non-null on new rows) while preserving tax/ownership/`FOR UPDATE` race behavior from `062`/`075` lineage
- [x] T009 [P] [US1] Extend `tests/test_marketplace_integrity_guards.py` (or equivalent source greps) to assert purchase path INSERT includes snapshot column names / fair-value write
- [x] T010 [US1] Re-apply `086` if needed and smoke-query one purchase (or SQL-level check) that new sales log rows populate snapshots; confirm failed purchase paths still raise before INSERT

**Checkpoint**: US1 MVP — enriched history durable without UI

---

## Phase 4: User Story 2 — Player ownership career trail (Priority: P1)

**Goal**: P2P transfer closes seller segment + opens buyer segment; agent sale closes segment before DELETE; managers can view club trail

**Independent Test**: Buy a card → ownership chain shows seller then buyer; agent-sell another card → history remains with `ended_via='agent_sale'`; career UI shows ordered club names

**Contract**: [contracts/ownership-history.md](./contracts/ownership-history.md) · UI: [contracts/marketplace-intelligence-ui.md](./contracts/marketplace-intelligence-ui.md)

### Implementation for User Story 2

- [x] T011 [US2] In `086_marketplace_intelligence.sql`, extend `purchase_transfer_listing` to close open seller ownership segment and open buyer segment (link `transfer_sales_log_id`) in the same transaction as ownership UPDATE
- [x] T012 [US2] In `086_marketplace_intelligence.sql`, REPLACE/patch `process_agent_sale` to close open ownership segment (`ended_via='agent_sale'`) **before** `DELETE FROM player_cards`
- [x] T013 [P] [US2] Optionally wire `ensure_card_ownership_open` into `purchase_scouting_player` and `sign_youth_scout_prospect` in `086` (`acquired_via` scouting/youth_scout); skip pack INSERT paths (lazy bootstrap instead)
- [x] T014 [US2] Add ownership career embed/builder + listing-detail “Career” (or inline trail) in `apps/discord_bot/views/marketplace_transfer.py`: call `get_card_ownership_history` / ensure + read; empty/minimal and ordered club-name trail; defer before DB
- [x] T015 [US2] On career open with zero rows, call `ensure_card_ownership_open(..., 'legacy_bootstrap')` then re-read so current club appears without inventing prior clubs (`apps/discord_bot/views/marketplace_transfer.py`)

**Checkpoint**: US1 + US2 independently demoable (SQL + career UI)

---

## Phase 5: User Story 3 — Price discovery from real market data (Priority: P1)

**Goal**: Managers see real cohort avg/median/active high-low/recent/trend or insufficient-data — never invented prices

**Independent Test**: ≥5 cohort sales → discovery shows matching stats; thin market → insufficient-data copy; P2P flag off → no discovery panels on agent/scouting paths

**Contract**: [contracts/price-discovery.md](./contracts/price-discovery.md)

### Tests for User Story 3

- [x] T016 [P] [US3] Add `tests/test_market_intelligence.py` covering cohort match (±OVR window), insufficient-data gate (min 5), average/median, trend up/down/flat/null windows — expect FAIL until T017

### Implementation for User Story 3

- [x] T017 [P] [US3] Implement `packages/economy/economy/market_intelligence.py` (`cohort_matches`, `average_price`, `median_price`, `trend_from_medians`, `insufficient_data`) with `from __future__ import annotations` and full typing; no `discord` imports
- [x] T018 [US3] Export market-intelligence helpers from `packages/economy/economy/__init__.py`
- [x] T019 [US3] Add `get_price_discovery` RPC in `supabase/migrations/086_marketplace_intelligence.sql` per contract (config-driven min/window; active listing high/low/count; recent sales bound; GRANT + verify guard)
- [x] T020 [US3] Wire price-discovery embed on Transfer Board listing detail and List Player confirm path in `apps/discord_bot/views/marketplace_transfer.py` (and hub touch in `apps/discord_bot/cogs/marketplace_cog.py` only if needed); insufficient-data copy; hide when P2P flag off

**Checkpoint**: Discovery usable on list/buy paths; pure tests green

---

## Phase 6: User Story 4 — Improved Transfer Board sorting (Priority: P2)

**Goal**: Seven sort modes on filtered board results without new board fetches or losing filters

**Independent Test**: Mixed listings → each sort reorders correctly; Best Value puts missing fair last; empty filters → empty-state

**Contract**: [contracts/transfer-board-sort.md](./contracts/transfer-board-sort.md)

### Tests for User Story 4

- [x] T021 [P] [US4] Extend `tests/test_market_intelligence.py` with `sort_transfer_listings` cases for all seven modes + Best Value missing-fair-last

### Implementation for User Story 4

- [x] T022 [P] [US4] Implement `sort_transfer_listings` (and Best Value ratio helper) in `packages/economy/economy/transfer_market.py` or `market_intelligence.py`; export from `packages/economy/economy/__init__.py`
- [x] T023 [US4] Add sort control to Transfer Board UI in `apps/discord_bot/views/marketplace_transfer.py`: apply after existing filters on in-memory list; default newest/current behavior; ≤25 select cap unchanged; no regen-scouting sort

**Checkpoint**: Board sort works without regressing filters/buy

---

## Phase 7: User Story 5 — Internal market analytics (Priority: P2)

**Goal**: Ops can call one RPC for volume, tax, agent mix, success rate, breakdowns — zeros when empty; not on hub open

**Independent Test**: Seed known sales/expires/agent ledger rows in a window → `get_market_analytics` reconciles counts/money; empty window → zeros

**Contract**: [contracts/market-analytics.md](./contracts/market-analytics.md)

### Implementation for User Story 5

- [x] T024 [US5] Add `get_market_analytics(p_from, p_to)` in `supabase/migrations/086_marketplace_intelligence.sql` returning metrics + breakdowns (+ `daily_volume` series) per contract; GRANT + verify guard
- [x] T025 [P] [US5] Confirm quickstart ops example in `specs/043-marketplace-intelligence/quickstart.md` matches final RPC signature; no Discord admin surface added in `apps/discord_bot/`

**Checkpoint**: Ops analytics queryable; marketplace hub unchanged for analytics

---

## Phase 8: User Story 6 — Long-term data collection / low overhead (Priority: P3)

**Goal**: Daily series and indexed history support balancing without slowing hub list/buy

**Independent Test**: After a day of activity, analytics `daily_volume` / lifetime metrics available; hub open does not call analytics RPC

### Implementation for User Story 6

- [x] T026 [US6] Verify `086` indexes (`transfer_sales_log_created_idx`, cohort idx, ownership card idx) exist and analytics uses them; keep `daily_volume` in `get_market_analytics` (no separate nightly job unless proven necessary)
- [x] T027 [P] [US6] Grep `apps/discord_bot/cogs/marketplace_cog.py` and `apps/discord_bot/views/marketplace_transfer.py` to ensure `get_market_analytics` is never called on hub/board open; only discovery/ownership/sort on manager paths

**Checkpoint**: Collection is byproduct of US1–US5 writes + on-read analytics

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Ship hygiene, regressions, player-facing copy

- [x] T028 [P] Update `change_log.md` with short player-facing notes (price discovery, ownership career, Transfer Board sorts) — skip ops-only analytics detail
- [x] T029 [P] Extend `tests/test_marketplace_integrity_guards.py` / race tests as needed so purchase still enforces own-buy, tax split, and single winner after 086 REPLACE
- [x] T030 Run unit suite from quickstart: `pytest tests/test_market_intelligence.py tests/test_transfer_market_math.py tests/test_marketplace_integrity_guards.py -q`
- [x] T031 Manual Discord + SQL smoke per `specs/043-marketplace-intelligence/quickstart.md` (history, ownership, discovery, sorts, agent close, analytics RPC)
- [x] T032 Grep touched files: no new slash commands; no `discord` imports under `packages/`; no direct `players.coins` updates; purchase still uses `apply_club_economy` only

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Start immediately
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS** US1–US6 bot/RPC story work that needs tables
- **US1 (Phase 3)**: After Foundational — MVP enriched sales log
- **US2 (Phase 4)**: After US1 purchase REPLACE exists (same migration file; ownership writes after snapshot INSERT)
- **US3 (Phase 5)**: After Foundational (+ ideally US1 so cohort has snapshot rows); pure package can start in parallel with US2 UI
- **US4 (Phase 6)**: After Foundational; independent of discovery UI but shares test file with US3
- **US5 (Phase 7)**: After Foundational (+ US1 snapshots improve breakdowns)
- **US6 (Phase 8)**: After US5 analytics RPC shape stable
- **Polish (Phase 9)**: After desired stories complete

### User Story Dependencies

| Story | Depends on | Independently testable? |
|-------|------------|-------------------------|
| US1 History | Phase 2 | Yes (SQL after one purchase) |
| US2 Ownership | US1 purchase body in 086 | Yes (career UI + SQL) |
| US3 Discovery | Phase 2 + first-class snapshots (US1) | Yes (seeded sales log) |
| US4 Sort | Phase 2 | Yes (in-memory fixtures / board) |
| US5 Analytics | Phase 2 (+ US1 for rich tops) | Yes (ops RPC) |
| US6 Collection | US5 | Yes (grep + analytics daily_volume) |

### Parallel Opportunities

- T001 ∥ T002
- T016 ∥ T017 (tests then impl — tests first)
- T017/T018 pure package ∥ T014 UI ownership (different files) after Phase 2
- T021/T022 sort helpers ∥ T024 analytics RPC (different concerns)
- T028 ∥ T029 polish docs vs integrity greps

---

## Parallel Example: User Story 3

```text
# After Phase 2 + US1 snapshots available:
Task: T016 tests/test_market_intelligence.py (cohort/median/trend) — FAIL first
Task: T017 packages/economy/economy/market_intelligence.py
Task: T018 packages/economy/economy/__init__.py exports
# Then sequential:
Task: T019 get_price_discovery in 086
Task: T020 Wire discovery UI in marketplace_transfer.py
```

---

## Parallel Example: User Stories 4 + 5 (after foundation)

```text
Dev A: T021–T023 Transfer Board sort (package + views)
Dev B: T024–T025 get_market_analytics RPC + quickstart check
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 Setup  
2. Phase 2 Foundational (schema + verify)  
3. Phase 3 US1 enriched purchase history  
4. **STOP and VALIDATE** via SQL smoke  
5. Then US2 → US3 for manager-facing value

### Incremental Delivery

1. Setup + Foundational → schema ready  
2. US1 → durable history (MVP)  
3. US2 → ownership career UI  
4. US3 → price discovery  
5. US4 → board sorts  
6. US5 → ops analytics  
7. US6 → overhead/collection check  
8. Polish → change_log + pytest + quickstart smokes  

### Suggested MVP scope

**US1 only** (enriched `transfer_sales_log` on purchase).  
**Recommended first ship slice**: US1 + US2 + US3 (history + career + discovery). US4 is a cheap follow-on; US5/US6 are ops.

---

## Notes

- Keep all schema/RPC changes in **one** forward migration `086`; do not edit applied `062`/`075` in place  
- When REPLACE'ing `purchase_transfer_listing` / `process_agent_sale`, diff against latest bodies (075/063 patches) so payroll/state guards are not dropped  
- Pack acquisition ownership wiring is explicitly deferred (lazy `legacy_bootstrap`)  
- Commit after each task or logical group; cite US-42.6 on mutating PRs  
- Avoid: second sale history table, Discord admin analytics hub, new slash commands, invented discovery numbers
)

