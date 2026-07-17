# Tasks: Player-to-Player Transfer Market

**Input**: Design documents from `/specs/017-player-transfer-market/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Include pure-math unit tests from plan (`tests/test_transfer_market_math.py`) — required by AGENTS for non-trivial tax/bounds formulas. No full Discord integration suite.

**Locked decisions** (research.md / plan.md):
- Buy-it-now only; 10% tax via buyer −gross / seller +net burn
- Ownership `UPDATE owner_id` (not delete)
- Floor 0.75× / ceil 2.5× agent fair value; TTL 72h; re-list cooldown 6h; slots 5
- Flag `p2p_transfer_market_enabled` default **false**; agent + scouting unchanged
- Migration: `062_p2p_transfer_market.sql`
- Extend `/marketplace` only — no new slash command

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: US1–US5 maps to spec user stories
- Exact file paths required

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm touch list and scaffolding before schema work

- [x] T001 Grep `process_agent_sale`, `purchase_scouting_player`, `marketplace_cog`, `apply_club_economy`, `senior_roster_cap`, `compute_agent_offer` callers; confirm touch list matches `specs/017-player-transfer-market/plan.md`
- [x] T002 [P] Create `scratch/apply_migration_062.py` from an existing `scratch/apply_migration_*.py` pattern (no-op until migration file exists)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Pure math, schema, RPCs, guards — **MUST complete before hub P2P wiring**

**⚠️ CRITICAL**: No Transfer Board / My Listings / list-buy bot wiring until this phase is done and schema verify passes

- [x] T003 [P] Implement `packages/economy/economy/transfer_market.py` per `contracts/transfer-tax-bounds.md` (`seller_net`, `tax_amount`, `listing_price_bounds`, `validate_listing_price` using `generate_agent_offer`)
- [x] T004 [P] Export transfer helpers from `packages/economy/economy/__init__.py`
- [x] T005 [P] Optional: mirror default tax bps / floor / ceil / ttl / cooldown keys in `packages/economy/economy/flows.py` `EconomyConfig` / defaults dict
- [x] T006 [P] Add `tests/test_transfer_market_math.py` covering 10% net, floor≤ceil, reject out-of-bounds price, fair-value reuse of agent offer
- [x] T007 Author `supabase/migrations/062_p2p_transfer_market.sql`: tables `transfer_listings` + `transfer_sales_log` + indexes + RLS policies per `data-model.md`; seed `game_config` keys; helper `p2p_transfer_market_enabled()`; schema guard block
- [x] T008 In `062_p2p_transfer_market.sql`, add `create_transfer_listing` and `cancel_transfer_listing` per `contracts/create-cancel-listing.md` (bounds via `compute_agent_offer`, slot cap, eligibility, re-list cooldown, cancel allowed when flag off)
- [x] T009 In `062_p2p_transfer_market.sql`, add `purchase_transfer_listing` per `contracts/purchase-transfer-listing.md` (`apply_club_economy` buy/sale, ownership transfer, sales_log, senior roster cap, self-buy reject, `FOR UPDATE` race safety)
- [x] T010 In `062_p2p_transfer_market.sql`, add `expire_stale_transfer_listings` per `contracts/expire-listings.md`
- [x] T011 In `062_p2p_transfer_market.sql`, update `process_agent_sale` to reject cards with an active transfer listing; add active-listing exclusion guards to `set_formation_and_assignments`, `swap_squad_players`, `process_stat_drill`, `process_recovery_session`, `train_with_fodder`, `start_player_evolution`, `allocate_skill_point`, and `transfer_mentor_xp` (return a friendly error if a listed card is targeted). Confirm match simulation only pulls from `squad_assignments` to satisfy FR-017.
- [x] T012 Extend `supabase/scripts/verify_required_schema.sql` with tables/RPCs/policies/config from 062 (fix split_part pitfalls for functions)
- [x] T013 Apply migration via `scratch/apply_migration_062.py` and run `python scratch/verify_schema_full.py` (or `verify_required_schema.sql`) until green

**Checkpoint**: Schema verified; `pytest tests/test_transfer_market_math.py -q` green; bot wiring can begin

---

## Phase 3: User Story 1 — List a player for sale (Priority: P1) 🎯 MVP

**Goal**: With flag on, manager lists an eligible card at a custom price, sees it under My Listings, and can cancel to restore the card

**Independent Test**: Flag on → List Player → confirm → hub shows `1/5` → card gone from agent sell / not XI-assignable → Cancel → card restored (no buyer required)

### Implementation for User Story 1

- [x] T014 [P] [US1] Create `apps/discord_bot/views/marketplace_transfer.py` with owner check, defer-on-click, My Listings embed (name/pos/OVR/age/POT/price/net), Cancel flow calling `cancel_transfer_listing`
- [x] T015 [US1] Add List Player flow in `apps/discord_bot/views/marketplace_transfer.py`: eligible roster select (exclude XI/training/evo/injury/academy/listed), Modal for price, confirm embed with fair/floor/ceil/net using `transfer_market` helpers, call `create_transfer_listing`
- [x] T016 [US1] Wire hub My Listings enablement + live `n / slot_cap` count in `apps/discord_bot/cogs/marketplace_cog.py` when `p2p_transfer_market_enabled` is true; keep button disabled when flag false
- [x] T017 [P] [US1] Exclude active-listed card ids from agent sell eligible list in `apps/discord_bot/cogs/marketplace_cog.py`
- [x] T018 [P] [US1] Reject listed cards on squad assign in `apps/discord_bot/cogs/squad_cog.py` with clear ephemeral (“Delist first”)
- [x] T019 [P] [US1] Exclude listed cards from development drill/fusion/mentor targets in `apps/discord_bot/cogs/development_cog.py`

**Checkpoint**: US1 independently demoable — list + cancel + locks work with flag on

---

## Phase 4: User Story 2 — Browse, filter, and buy (Priority: P1)

**Goal**: Buyer opens Transfer Board, filters by position/OVR/age/POT bands, Buy Now completes tax-correct ownership transfer

**Independent Test**: Seller has active listing; Buyer filters → Buy Now → buyer −gross, seller +net, `owner_id` updated; second buyer gets already-sold

### Implementation for User Story 2

- [x] T020 [US2] Add Search Market submenu (Regen Scouting vs Transfer Board) in `apps/discord_bot/cogs/marketplace_cog.py` / `apps/discord_bot/views/marketplace_transfer.py` per `contracts/marketplace-p2p-ui.md` when flag on; scouting-only path when flag off
- [x] T021 [US2] Implement Transfer Board browse + filter selects in `apps/discord_bot/views/marketplace_transfer.py`: Position (`Any|GK|DEF|MID|FWD`) plus preset bands for OVR / Age / Potential (e.g. OVR 75–79, Age 21–25) per FR-005; query active `transfer_listings` joined to `player_cards` (≤25 options; empty-state copy). No free-range min/max Modals.
- [x] T022 [US2] Implement Buy Now confirm + RPC `purchase_transfer_listing` with `p_expected_price`; map errors (insufficient coins, own listing, sold, roster full, price mismatch) to ephemeral embeds in `apps/discord_bot/views/marketplace_transfer.py`
- [x] T023 [US2] After successful buy, refresh Transfer Board / hub listing counts for buyer session in `apps/discord_bot/views/marketplace_transfer.py`

**Checkpoint**: Two-club list→buy works; tax visible in success copy; races fail cleanly for loser

---

## Phase 5: User Story 3 — Manage listings and understand tax (Priority: P2)

**Goal**: My Listings is the seller’s home — clear net-after-tax before and after sales

**Independent Test**: Open My Listings alone; each row shows listed price and net; after remote purchase, next hub/My Listings visit no longer shows the card and coins reflect net credit

### Implementation for User Story 3

- [x] T024 [US3] Polish My Listings embed copy (tax explanation footer, net column prominence) in `apps/discord_bot/views/marketplace_transfer.py`
- [x] T025 [US3] Ensure sold listings immediately vanish from the My Listings view via UI refresh after cancel/sell-side state change. No seller DM in v1 (ponytail: simplicity).
- [x] T026 [P] [US3] Ensure List confirm and My Listings both call shared `seller_net` / tax preview from `packages/economy/economy/transfer_market.py` (no duplicated 0.9 literals in cog)

**Checkpoint**: Seller never needs board browse to understand tax or manage posts

---

## Phase 6: User Story 4 — Feature flag + coexistence (Priority: P2)

**Goal**: Flag off = legacy hub; flag on = agent + scouting + P2P without forcing migration of habits

**Independent Test**: Toggle flag false → My Listings disabled, no Transfer Board, agent/scouting OK; true → all three rails; agent daily cap does not block listing

### Implementation for User Story 4

- [x] T027 [US4] Centralize flag read helper (e.g. in `apps/discord_bot/cogs/marketplace_cog.py` or `apps/discord_bot/core/economy_rpc.py`) using `get_game_config` / `p2p_transfer_market_enabled`
- [x] T028 [US4] Audit hub button labels/copy: rename Sell to **Sell to Agent** clarity; Search Market branching only when flag on — in `apps/discord_bot/cogs/marketplace_cog.py`
- [x] T029 [US4] Smoke checklist notes: agent sale still capped; listing still allowed at cap — verify in quickstart path (no code if already true)

**Checkpoint**: Rollout-safe defaults; zero regression when flag off

---

## Phase 7: User Story 5 — Daily habit / Discord-simple UX (Priority: P3)

**Goal**: Fast duplicate→list and gap→filter→buy paths; expiry sweeper keeps board fresh

**Independent Test**: Hub→listed in short guided flow; Transfer Board filter finds band; stale listings expire via job

### Implementation for User Story 5

- [x] T030 [P] [US5] Add `apps/discord_bot/tasks/transfer_listing_expiry_job.py` calling `expire_stale_transfer_listings` and logging `expired_count`
- [x] T031 [US5] Register hourly (or similar) job in `apps/discord_bot/core/scheduler_jobs.py` and `apps/discord_bot/main.py`
- [x] T032 [US5] UX copy polish for duplicate/bargain loops (fair-value guide on list, “under agent value” hint optional only if price &lt; fair) in `apps/discord_bot/views/marketplace_transfer.py` — keep Discord-simple, no auctions

**Checkpoint**: Expiry job wired; list/buy still ≤ few interactions

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Ship hygiene, schema docs, player-facing changelog

- [x] T033 [P] Update `change_log.md` with P2P market + 10% tax + flag rollout note
- [x] T034 [P] Reconcile US-11 / marketplace ACs in `.specify/specs/v1.0.0/spec.md` (and plan notes if needed) for P2P listings + tax
- [x] T035 Grep for hard-coded `0 / 5`, leftover “My Listings (Soon)”, and any `players.coins` direct updates in marketplace paths; fix leftovers
- [x] T036 Run `specs/017-player-transfer-market/quickstart.md` validation (pytest + schema + flag off/on smoke)
- [x] T037 Run integrity pass: every new RPC has a call site; agent/scouting callers unchanged when flag off; no `discord` imports under `packages/`
- [x] T038 Add a concurrent double-buy race check in `tests/test_transfer_market_race.py` (or SQL/script equivalent under `scratch/` if CI lacks live DB) validating `FOR UPDATE` locking in `purchase_transfer_listing` — exactly one success, zero double-debit, loser sees listing unavailable (SC-005)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup** → no deps
- **Phase 2 Foundational** → after Setup; **BLOCKS** all user story UI work
- **Phase 3 US1** → after Foundational (MVP)
- **Phase 4 US2** → after US1 list exists (needs listings to buy; can stub seed via RPC for parallel if needed)
- **Phase 5 US3** → after US1 My Listings skeleton (T014+)
- **Phase 6 US4** → can start after hub flag wiring (T016); finalize after US1/US2 paths exist
- **Phase 7 US5** → after purchase path; expiry job independent of UI polish
- **Phase 8 Polish** → after desired stories complete

### User Story Dependencies

```text
Foundational (math + 062 RPCs)
    └── US1 List/Cancel/Locks  ──┐
         ├── US3 Tax/My Listings polish
         └── US2 Transfer Board Buy ── US5 Expiry + habit UX
    US4 Flag coexistence (wraps hub gating; verify last with US1/US2)
```

### Parallel Opportunities

- T001 || T002
- T003 || T004 || T005 || T006 (then migration T007+)
- After T013: T017 || T018 || T019 with T014
- T030 can parallel late-story UI polish
- T033 || T034

### Parallel Example: After Foundation

```text
T014 marketplace_transfer.py (My Listings + cancel)
T017 marketplace_cog sell exclude listed
T018 squad_cog reject listed
T019 development_cog exclude listed
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 + Phase 2 (migration + math + verify)
2. Phase 3 US1 (list / cancel / locks) with flag **on** in staging
3. **STOP** — validate independent test in quickstart §5
4. Then US2 buy path before any production flag flip

### Incremental Delivery

1. Foundation → schema green  
2. US1 → list/cancel demo  
3. US2 → two-club buy + tax  
4. US3 → tax clarity polish  
5. US4 → confirm flag-off regression  
6. US5 → expiry job  
7. Polish → changelog + SDD + quickstart full  

### Suggested MVP scope

**T001–T019** (Setup + Foundational + US1). Do not enable production flag until US2 (T020–T023) also passes. Race check **T038** before production flag.

---

## Notes

- [P] = different files, no incomplete deps
- Cancel must work when flag flips off mid-flight (RPC contract)
- All coin paths: `apply_club_economy` only
- Prefer splitting UI into `views/marketplace_transfer.py` if `marketplace_cog.py` would bloat
- Commit after each logical group when asked; do not push/flag prod without verify
- Analyze remediations (2026-07-14): FR-005 preset bands; T025 concrete; T011 named RPCs; T038 race test
