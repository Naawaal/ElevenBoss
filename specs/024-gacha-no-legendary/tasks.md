# Tasks: Gacha Pack Epic Cap (No Legendary Drops)

**Input**: Design documents from `/specs/024-gacha-no-legendary/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Required by plan/FR-008 — update `tests/test_pack_configs.py` (defaults + sanitize + ≥10k zero-Legendary simulation). No Discord integration suite.

**Locked decisions** (research.md / plan.md):
- Standard pack defaults **60 / 30 / 10** (Common / Rare / Epic); fold old Legendary **2** into Epic
- `sanitize_pack_config` strips Legendary even if `game_config` is wrong
- Seed `pack_standard_rarities` + `pack_standard_rarity_weights` in migration **068**
- Bot reads config and passes override into pure `generate_pack` (no DB in `packages/`)
- Keep `generate_support_legendary` + owned Legendary cards untouched
- Store copy: Epic max; no Legendary pack promise

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: US1–US3 maps to spec user stories
- Exact file paths required

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm touch list and scaffolding

- [x] T001 Grep `PACKS`, `rarity_weights`, `generate_pack`, `get_pack_config`, `Legendary`, `60, 30, 8, 2`, Store gacha copy; confirm touch list matches `specs/024-gacha-no-legendary/plan.md`; note `generate_support_legendary` must remain
- [x] T002 [P] Create `scratch/apply_migration_068.py` from an existing `scratch/apply_migration_*.py` pattern

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Epic-capped package defaults + sanitize/resolve + migration seeds — **MUST complete before Store wiring that depends on new APIs**

**⚠️ CRITICAL**: Do not ship Store claim with config overlay until package sanitize guarantees zero Legendary

- [x] T003 Update `packages/gacha/gacha/pack_configs.py` `PACKS["standard"]` to rarities `("Common", "Rare", "Epic")` and weights `(60, 30, 10)` per `contracts/pack-epic-cap.md`
- [x] T004 Add `sanitize_pack_config` and `resolve_pack_config` in `packages/gacha/gacha/pack_configs.py` (strip Legendary; invalid → Epic-capped defaults)
- [x] T005 [P] Export new helpers from `packages/gacha/gacha/__init__.py`
- [x] T006 Update `packages/gacha/gacha/generator.py` `generate_pack` to use `resolve_pack_config` / sanitize and accept optional `rarities` / `rarity_weights` overrides
- [x] T007 Author `supabase/migrations/068_pack_epic_cap_odds.sql` seeding `pack_standard_rarities` and `pack_standard_rarity_weights` with **DO UPDATE** per `contracts/game-config-pack-odds.md`
- [x] T008 Apply migration via `scratch/apply_migration_068.py` (or confirm seeds present)
- [x] T009 Update `tests/test_pack_configs.py`: assert `(60, 30, 10)` defaults; sanitize strips Legendary; invalid override falls back; **N≥10_000** rolls → Legendary count **0**; Epic within ±2 pp of 10%

**Checkpoint**: `pytest tests/test_pack_configs.py -q` green; package never rolls Legendary

---

## Phase 3: User Story 1 — Packs Never Drop Legendary (Priority: P1) 🎯 MVP

**Goal**: Live daily pack claim uses Epic-capped generation (defaults sufficient even before config overlay)

**Independent Test**: Claim `/store` pack → all cards Common/Rare/Epic; simulation already proves 0 Legendary

### Implementation for User Story 1

- [x] T010 [US1] Wire `apps/discord_bot/cogs/store_cog.py` pack claim to call updated `generate_pack` (defaults path) so production claims use Epic-capped mix immediately
- [x] T011 [US1] Grep `apps/discord_bot/` + `packages/gacha/` for pack-generation paths still using Legendary-inclusive weights; confirm only `generate_support_legendary` (non-pack) remains intentional

**Checkpoint**: US1 demoable — Store packs cannot drop Legendary via package defaults

---

## Phase 4: User Story 2 — Odds Clear and Tunable (Priority: P1)

**Goal**: Store shows Epic-max copy; odds loaded from `game_config` with safe fallback

**Independent Test**: Store hub copy lists Epic max; changing config weights (valid) affects rolls; bad config still never Legendary

### Implementation for User Story 2

- [x] T012 [P] [US2] Add helper to read pack rarity override from `game_config` (e.g. in `apps/discord_bot/core/economy_rpc.py` or `apps/discord_bot/core/pack_config_rpc.py`) returning `(rarities, weights) | None` on parse failure
- [x] T013 [US2] Pass config override into `generate_pack` from `apps/discord_bot/cogs/store_cog.py` claim path per `contracts/game-config-pack-odds.md`
- [x] T014 [US2] Update Daily Gacha Pack field copy in `apps/discord_bot/cogs/store_cog.py` per `contracts/store-pack-copy.md` (Epic max; ~60/30/10; no Legendary promise)

**Checkpoint**: US2 — tunable odds + honest Store copy

---

## Phase 5: User Story 3 — Existing Legendaries & Event Grants (Priority: P2)

**Goal**: Confirm owned Legendaries and thank-you grant path untouched

**Independent Test**: Grep/diff shows no mutation of owned cards; `generate_support_legendary` still callable; thank-you RPCs unchanged

### Implementation for User Story 3

- [x] T015 [US3] Verify `packages/gacha/gacha/generator.py` `generate_support_legendary` and `apps/discord_bot/views/support_legendary_claim.py` / migration `067` are unchanged by this feature (no shared pack-table dependency introduced)
- [x] T016 [P] [US3] Confirm squad/marketplace Legendary display maps remain (owned-card styling only) — no removal required unless pack-odds advertising leaked there

**Checkpoint**: US3 — event Legendary + owned cards still valid

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Docs, changelog, SDD, final grep

- [x] T017 [P] Update `change_log.md` — packs no longer drop Legendary; odds 60/30/10 Epic max; event Legendaries unchanged
- [x] T018 [P] Reconcile `.specify/specs/v1.0.0/spec.md` daily pack odds (remove Legendary 2%; document Epic-capped mix)
- [x] T019 Grep repo player-facing pack odds for stale “Legendary 2%” / `60, 30, 8, 2` in pack context; leave wage/rarity mult and Division “Legendary” alone
- [x] T020 Run `specs/024-gacha-no-legendary/quickstart.md` checks (`pytest tests/test_pack_configs.py -q`)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Start immediately
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS** reliable Store/config wiring
- **US1 (Phase 3)**: Depends on Foundational (new `generate_pack` behavior)
- **US2 (Phase 4)**: Depends on Foundational + US1 claim call site
- **US3 (Phase 5)**: Can run in parallel with US2 (verification / no-op)
- **Polish (Phase 6)**: After desired stories complete

### User Story Dependencies

- **US1 (P1)**: After Foundational — MVP (defaults alone ban Legendary)
- **US2 (P1)**: Builds on US1 claim path for config + copy
- **US3 (P2)**: Verification; no dependency on US2

### Parallel Opportunities

- T001 ∥ T002
- T005 ∥ T007 (export vs migration) after T003/T004 drafted
- T012 ∥ T017 ∥ T018 (helper / docs) once Foundational done
- T015 ∥ T016 (verification)

---

## Implementation Strategy

### MVP First (US1 + Foundational)

1. Phase 1 Setup  
2. Phase 2 Package defaults + sanitize + tests  
3. Phase 3 Store uses new `generate_pack`  
4. **STOP and VALIDATE** — packs never Legendary  
5. Then US2 config + Store copy before calling it done for ops

### Suggested MVP scope

**Foundational + US1 + US2** (ban + config + copy). US3 is a verification gate in the same release.

---

## Notes

- Do not put Supabase clients in `packages/gacha`
- Do not change `claim_daily_pack` RPC signature unless required (payload rarity just won’t be Legendary)
- Rollback = restore old package weights + config keys + Store copy; no card data migration
- Commit only when user requests
