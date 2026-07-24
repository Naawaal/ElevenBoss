# Tasks: Marketplace V1.5 — Professional UX & Polish

**Input**: Design documents from `/specs/045-marketplace-ux-polish/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included — plan/quickstart require unit coverage for time-left, trend labels, discovery/`recent_sales` formatting, ask-vs-fair helpers in `tests/test_marketplace_ux_polish.py` (and/or extend `tests/test_market_intelligence.py`). No full Discord integration suite.

**Locked decisions** (research.md / plan.md):
- Polish-only — no new migration, slash command, or market mechanics
- Never invent market numbers; no `get_market_analytics` on hub
- Product name **Marketplace**; Back = `Back to Market`
- Board: fetch on Apply / post-mutate; select+sort from memory
- Favorite filters / true pagination deferred
- Cite **US-42.6** only if purchase/list RPC paths are touched (prefer presentation-only)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: US1–US5 maps to spec user stories
- Exact file paths required

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm touch list before editing marketplace surfaces

- [x] T001 Grep `/marketplace` hub, `show_transfer_board`, `_board_listings`, `_discovery_field_value`, `BuyConfirmView`, `show_my_listings`, `show_sell_menu`, `active_training`, and `get_market_analytics` across `apps/discord_bot/`; confirm touch list matches `specs/045-marketplace-ux-polish/plan.md` (no analytics-on-hub)
- [x] T002 [P] Create stub `apps/discord_bot/core/marketplace_copy.py` with `PRODUCT_NAME`, `BACK_TO_MARKET`, `BACK_TO_LISTINGS`, and placeholder ownership-error constant per `contracts/marketplace-copy-language.md` (wire imports in later stories)

**Checkpoint**: Touch list known; copy module exists

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Pure presentation helpers + tests — **MUST land before Discord story wiring**

**⚠️ CRITICAL**: Do not invent prices; helpers only format existing inputs

- [x] T003 Add pure helpers in `packages/economy/economy/market_intelligence.py`: relative deadline from `expires_at` (e.g. `14h left` / `Ending soon`), trend label map (`up`→Rising, `down`→Softening, `flat`→Steady), and ask-vs-fair line builder (omit fair segment if fair is None)
- [x] T004 [P] Export new helpers from `packages/economy/economy/__init__.py`
- [x] T005 [P] Create `tests/test_marketplace_ux_polish.py` covering deadline edge cases, trend labels, ask-vs-fair omit-when-null, and discovery body with/without `recent_sales` / `insufficient_data` (may call Discord-side formatter later — start with pure helpers)
- [x] T006 Flesh `apps/discord_bot/core/marketplace_copy.py` with trend word constants (if not purely in packages), shared ownership/session error string(s), and hub subtitle helper listing sub-areas

**Checkpoint**: Helpers green under pytest; ready for US1/US2 UI

---

## Phase 3: User Story 1 — Faster browse → buy with scannable board (Priority: P1) 🎯 MVP

**Goal**: Transfer Board results show scannable preview + time-left; detail shows rarity + ask-vs-fair; Buy confirm keeps compact market/fair cue

**Independent Test**: P2P on, ≥3 listings → Apply defaults → see preview with prices/time-left → select → detail fair/rarity → Buy confirm still has context

**Contract**: [contracts/board-preview-and-buy.md](./contracts/board-preview-and-buy.md)

### Implementation for User Story 1

- [x] T007 [US1] Add board preview builder in `apps/discord_bot/views/marketplace_transfer.py` (up to ~8 lines: name · OVR · price · time-left; note count / “up to 25” when truncated) and use it in `show_transfer_board` results stage instead of opaque “N listing(s). Select…”
- [x] T008 [P] [US1] Enrich Transfer Board Select option descriptions with OVR, price, and time-left (char budget) in `marketplace_transfer.py` results view
- [x] T009 [US1] On listing detail in `show_transfer_board` / results view: show rarity when present; ask-vs-fair via existing `fair_value_coins` / helpers; show time remaining
- [x] T010 [US1] Update `BuyConfirmView` in `marketplace_transfer.py` to retain ask + OVR + compact fair/market cue (pass through from detail; do not strip discovery/fair)

**Checkpoint**: US1 MVP — blind select removed; buy context retained

---

## Phase 4: User Story 2 — Market intelligence visible at decisions (Priority: P1)

**Goal**: Readable discovery (trend + recent sales); buy/list confirms keep cues; ownership trail stays compact

**Independent Test**: Listing with cohort data shows Rising/Softening/Steady + recent sales; buy confirm keeps compact cue; insufficient data still honest

**Contract**: [contracts/discovery-presentation.md](./contracts/discovery-presentation.md)

### Tests for User Story 2

- [x] T011 [P] [US2] Extend `tests/test_marketplace_ux_polish.py` (or transfer-local formatter tests) for `_discovery_field_value` behavior: recent_sales lines, human trend, insufficient_data path invents nothing

### Implementation for User Story 2

- [x] T012 [US2] Rewrite `_discovery_field_value` in `apps/discord_bot/views/marketplace_transfer.py` per discovery contract (human trend, up to 3 recent sales, insufficient copy unchanged in intent)
- [x] T013 [US2] Ensure list-confirm path reuses the same discovery formatter; Buy confirm uses compact variant from T010
- [x] T014 [P] [US2] Polish ownership trail formatting in `_ownership_trail_text` / detail field for readability (no invented clubs; empty state clear)

**Checkpoint**: US2 — 043 data fully manager-readable at decision points

---

## Phase 5: User Story 3 — Cohesive Marketplace language (Priority: P2)

**Goal**: One product name, consistent Back/confirm vocabulary, shared ownership errors

**Independent Test**: Hub → Search → Board → Back → Agent → Scouting uses Marketplace + `Back to Market`

**Contract**: [contracts/marketplace-copy-language.md](./contracts/marketplace-copy-language.md)

### Implementation for User Story 3

- [x] T015 [US3] Update hub embed in `apps/discord_bot/cogs/marketplace_cog.py` (`show_marketplace_hub`) to title `Marketplace` and subtitle listing Transfer Board · Scouting · Agent · My Listings (when P2P)
- [x] T016 [P] [US3] Replace Back button labels across `marketplace_transfer.py` and `marketplace_cog.py` with `marketplace_copy.BACK_TO_MARKET` / `BACK_TO_LISTINGS`
- [x] T017 [US3] Align confirm button style intents (buy/list success, agent danger) and collapse ownership/session error strings to shared copy constants in cog + transfer views
- [x] T018 [P] [US3] Optional truncate hint “Showing up to 25” when board/agent/scouting selects are capped in those views

**Checkpoint**: US3 — one design language

---

## Phase 6: User Story 4 — Listing & selling clarity (Priority: P2)

**Goal**: My Listings show expiry; agent offer shows POT; success summaries concise

**Independent Test**: Active listing shows time-left; agent offer shows POT before Confirm

### Implementation for User Story 4

- [x] T019 [US4] Surface `expires_at` as time-left on each field/row in `show_my_listings` (`marketplace_transfer.py`)
- [x] T020 [US4] Show potential (and rarity if already loaded) on agent offer embed in `apps/discord_bot/cogs/marketplace_cog.py` before Confirm Sale
- [x] T021 [P] [US4] Tighten success/failure ephemeral copy for list confirm, buy success, and agent sale success in transfer views + cog (concise summaries; actionable validation errors)

**Checkpoint**: US4 — sell/list decisions informed

---

## Phase 7: User Story 5 — Leaner marketplace loads (Priority: P3)

**Goal**: In-memory board select/sort; scoped training eligibility; narrow selects

**Independent Test**: Sort/select do not re-call `_board_listings`; training query scoped to owner cards

**Contract**: [contracts/marketplace-hot-path.md](./contracts/marketplace-hot-path.md)

### Implementation for User Story 5

- [x] T022 [US5] Refactor `TransferBoardResultsView` callbacks in `marketplace_transfer.py` so Sort and Select use `self.listings` (re-sort via `sort_transfer_listings` in memory); only Apply Filters / post-buy refresh call `_board_listings`
- [x] T023 [US5] Scope `active_training` reads in `marketplace_cog.py` (sell menu) and `marketplace_transfer.py` (list player) to the manager’s card ids / owner — remove unfiltered global scan
- [x] T024 [P] [US5] Narrow `select` columns on hub player fetch, sell/list roster, and scouting pool opens in `marketplace_cog.py` / `marketplace_transfer.py` (drop `select("*")` where safe)

**Checkpoint**: US5 — snappier hot path without semantic change

---

## Phase 8: Polish & Cross-Cutting

**Purpose**: Regression, changelog, integrity, ship readiness

- [x] T025 [P] Run `pytest tests/test_marketplace_ux_polish.py tests/test_market_intelligence.py tests/test_marketplace_integrity_guards.py -q` (adjust file set to what exists) until green
- [x] T026 [P] Update `change_log.md` with player-facing Marketplace polish note (clearer board, time-left, fair/market cues)
- [x] T027 Grep `apps/discord_bot/` for `get_market_analytics` on hub/board paths (must remain zero); confirm no new slash commands; confirm no new migration files unless unavoidable
- [x] T028 Discord smoke per `specs/045-marketplace-ux-polish/quickstart.md` §§2–3; mark `specs/045-marketplace-ux-polish/checklists/requirements.md` notes + set `spec.md` Status when done
- [x] T029 Persona walkthrough (mobile browse→buy, seller My Listings, agent sell, P2P-off scouting shortcut, double-tap confirm): settlement unchanged; document gaps fixed

---

## Dependencies & Story Order

```text
Phase 1 Setup
    ↓
Phase 2 Foundational (helpers + copy + tests)
    ↓
Phase 3 US1 (board preview / buy) ──┬──→ Phase 4 US2 (discovery) ──→ can parallelize after T007–T009
    ↓                               │
Phase 5 US3 (copy language) ←───────┘  (can start after T002/T006)
    ↓
Phase 6 US4 (listings / agent)
    ↓
Phase 7 US5 (hot path)  — after US1 board view exists
    ↓
Phase 8 Polish
```

| Story | Depends on | Notes |
|-------|------------|-------|
| US1 | Phase 2 | MVP |
| US2 | Phase 2; shares board detail with US1 | |
| US3 | T002/T006 | Parallelizable with US1 late |
| US4 | Phase 2 helpers for time-left | |
| US5 | US1 board view structure | |

**Suggested MVP**: Phases 1–4 (US1 + US2) — scannable board + intelligence at decisions.

---

## Parallel Execution Examples

```text
# Setup / foundation
T002 || T001
T004 || T005 || T006   (after T003)

# US1
T008 || T009   (after preview T007 started)

# US2
T011 || T014

# Polish
T025 || T026
```

---

## Implementation Strategy

1. Helpers + copy first (Phase 2).  
2. MVP = board preview + fair/time + discovery/buy context (US1+US2).  
3. Naming/agent/listings polish (US3+US4).  
4. Perf last (US5) so UI contracts are stable.  
5. No schema/RPC work unless a bug forces a forward fix.

---

## Summary

| Metric | Count |
|--------|-------|
| Total tasks | 29 (T001–T029) |
| Phase 1 Setup | 2 |
| Phase 2 Foundational | 4 |
| US1 Board/buy | 4 |
| US2 Discovery | 4 |
| US3 Language | 4 |
| US4 Listings/agent | 3 |
| US5 Hot path | 3 |
| Phase 8 Polish | 5 |
| Parallelizable marked [P] | 12 |

**Independent tests**: US1 scannable preview + buy context; US2 trend/recent sales; US3 naming walk; US4 expiry+POT; US5 no board re-fetch on select.

**Format validation**: All tasks use `- [ ] Tnnn [P?] [USn?] …` with file paths.
)
