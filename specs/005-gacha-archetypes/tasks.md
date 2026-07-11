# Tasks: Gacha Card Archetypes & Factory Reliability

**Input**: Design documents from `/specs/005-gacha-archetypes/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included — plan/quickstart require pytest for archetype diversity (`tests/test_player_archetypes.py`), OVR exactness (`tests/test_player_factory_ovr.py`), pack configs (`tests/test_pack_configs.py`), and regen role (`tests/test_regen_pool.py`). Discord pack/squad UX via quickstart.

**Organization**: Tasks grouped by user story (US1–US3) for incremental delivery.

**Locked decisions** (from research.md):
- Archetype → `player_cards.role` (no new column on cards); migration `051` required because intake RPCs omit `role` today
- Catalog: 3 archetypes per position; FWD = Poacher / Speedster / Complete Forward; roll weights 30/30/40
- OVR balance = bulk estimate + greedy ±1 on top-2/bottom-2; delete `attempts < 10` while-loop
- Factory returns `CreatedPlayerCard`; `GachaPlayer.role` mapped at gacha boundary
- Pack configs in `gacha/pack_configs.py`; Standard 60/30/8/2 unchanged; no live Defender Pack SKU
- True OVR / PlayStyle formulas unchanged; no historical backfill; no new slash commands

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 / US2 / US3
- Include exact file paths in descriptions

## Path Conventions

- Pure engine: `packages/player_engine/player_engine/`
- Gacha: `packages/gacha/gacha/`
- Bot: `apps/discord_bot/`
- SQL: `supabase/migrations/`, `supabase/scripts/verify_required_schema.sql`
- Tests: `tests/` at repo root
- SDD: `.specify/specs/v1.0.0/`
- Feature docs: `specs/005-gacha-archetypes/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm callers and contracts before code

- [x] T001 Review `specs/005-gacha-archetypes/plan.md` against `contracts/created-player-card.md`, `contracts/pack-config.md`, and `contracts/role-persistence-rpc.md`; note any drift in `specs/005-gacha-archetypes/research.md` if found
- [x] T002 [P] Grep `packages/` and `apps/discord_bot/` for `create_player_card`, `generate_pack`, `card_rpc_payload`, and intake RPC names (`claim_daily_pack`, `register_new_player`, `process_youth_intake`, `insert_scouting_pool_player`); list exact call sites for US1–US3 wiring

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared creation contract + archetype catalog that US1/US2 both need

**⚠️ CRITICAL**: Do not rewrite factory callers until `CreatedPlayerCard` and the archetype catalog exist

- [x] T003 Add `CreatedPlayerCard` Pydantic model in `packages/player_engine/player_engine/created_card.py` per `contracts/created-player-card.md` (include `role`; `def` alias compatible with RPC JSON)
- [x] T004 [P] Implement archetype catalog + `roll_archetype(position, rng)` in `packages/player_engine/player_engine/archetypes.py` per research R2 (FWD/MID/DEF/GK × 3; weights sum ≈ 1.0; roll weights 30/30/40)
- [x] T005 Export `CreatedPlayerCard`, `roll_archetype`, and catalog helpers from `packages/player_engine/player_engine/__init__.py`

**Checkpoint**: Model + catalog importable; factory behavior unchanged until US1/US2

---

## Phase 3: User Story 1 — Distinct Card Identities (Priority: P1) 🎯 MVP

**Goal**: Same-position cards get distinct archetypes; `role` is visible and persisted

**Independent Test**: Batch-generate FWD Epics → ≥2 roles; Poacher vs Speedster mean SHO/PAC differ as expected; claimed cards store non-`Balanced` role when archetype rolled

### Tests for User Story 1

- [x] T006 [P] [US1] Create `tests/test_player_archetypes.py` asserting: catalog has ≥3 archetypes per position; FWD includes Poacher/Speedster/Complete Forward; seeded batch yields ≥2 FWD roles; archetype primary-stat means diverge in the expected direction

### Implementation for User Story 1

- [x] T007 [US1] Update `create_player_card` in `packages/player_engine/player_engine/player_factory.py` to roll archetype before stat jitter, use archetype weights for provisional stats, set `role` on a returned `CreatedPlayerCard` (keep existing while-loop balancer temporarily so US1 can be validated without US2)
- [x] T008 [US1] Update `packages/gacha/gacha/models.py` to add `role: str = "Balanced"` on `GachaPlayer`
- [x] T009 [US1] Update `_make_player` / youth mapping in `packages/gacha/gacha/generator.py` to map `CreatedPlayerCard.role` into `GachaPlayer`
- [x] T010 [US1] Update `packages/player_engine/player_engine/youth_intake.py` and `packages/player_engine/player_engine/regen_pool.py` to preserve `role` through POT overrides. Youth/regen callers must return `CreatedPlayerCard` (or `list[CreatedPlayerCard]`). Conversion to `dict` for the RPC payload may *only* happen at the Discord cog / DB wiring edge in `apps/`.
- [x] T011 [US1] Update `apps/discord_bot/core/card_payload.py` (`card_rpc_payload` + `scouting_pool_payload`) to include `"role"`
- [x] T012 [US1] Add `supabase/migrations/051_card_role_persistence.sql` per `contracts/role-persistence-rpc.md` (`scouting_pool_players.role`; extend register / claim_daily_pack / process_youth_intake / insert_scouting_pool_player / purchase_scouting_player to INSERT `COALESCE(role,'Balanced')`)
- [x] T013 [P] [US1] Add `scratch/apply_migration_051.py` (follow existing scratch apply pattern) and extend `supabase/scripts/verify_required_schema.sql` for `column:public.scouting_pool_players.role` (and `player_cards.role` if missing)
- [x] T014 [P] [US1] Show archetype on pack claim in `apps/discord_bot/embeds/gacha_embeds.py`; add a one-line role on marquee/youth in `apps/discord_bot/embeds/onboarding_embeds.py` if trivial; confirm `apps/discord_bot/embeds/squad_embeds.py` / player Role Style already surface `role`
- [x] T015 [P] [US1] Extend `tests/test_regen_pool.py` to assert regen cards expose a non-empty `role` from the catalog for the retired position

**Checkpoint**: US1 local validation — packs/intake produce visible, persisted archetypes even if OVR loop is still the old while&lt;10

**Note: US1 (MVP) is a local development checkpoint only. US2 (deterministic loop) must be completed and passing before this feature is merged to production to satisfy FR-006/008.**

---

## Phase 4: User Story 2 — Trustworthy Overall Ratings (Priority: P1)

**Goal**: Final True OVR matches creation target whenever attribute bounds allow; no abandoned mismatch loop

**Independent Test**: `pytest tests/test_player_factory_ovr.py` — large batch across positions/rarities hits `overall == target_ovr` when achievable

### Tests for User Story 2

- [x] T016 [P] [US2] Create `tests/test_player_factory_ovr.py` asserting: seeded multi-position/rarity batch achieves exact target True OVR when bounds allow; potential ceiling / clamp edge cases terminate without hanging; no reliance on `attempts < 10` abandon path

### Implementation for User Story 2

- [x] T017 [US2] Replace the while-loop balancer in `packages/player_engine/player_engine/player_factory.py` with deterministic bulk-estimate + greedy ±1 on top-2 / bottom-2 archetype attrs per research R3; skip zero-weight GK attrs; set `overall`/`base_rating` from final True OVR
- [x] T018 [US2] Run `pytest tests/test_player_factory_ovr.py tests/test_player_archetypes.py -q` and fix any archetype/OVR interactions without changing `packages/player_engine/player_engine/engine.py` True OVR / PlayStyle formulas

**Checkpoint**: US1 + US2 — distinct identities **and** trustworthy OVR from the same factory

---

## Phase 5: User Story 3 — Pack Configs & Typed Contracts (Priority: P2)

**Goal**: Standard pack weights live in named config; factory boundary is typed end-to-end; unknown pack id fails loudly; ready for future pack ids without touching balancing

**Independent Test**: `pytest tests/test_pack_configs.py`; `generate_pack(pack_id="standard")` preserves 60/30/8/2 within ±3 pp at N≥2000; unknown id raises; callers only consume `CreatedPlayerCard` / `GachaPlayer` (no bare incomplete dicts at package boundary)

### Tests for User Story 3

- [x] T019 [P] [US3] Create `tests/test_pack_configs.py` asserting Standard rarity/position weights, `get_pack_config("standard")` works, unknown `pack_id` raises a typed error, and `generate_pack` uses config: batch **N ≥ 2000**, each rarity within **±3 pp** of target (e.g. Common 57%–63%)

### Implementation for User Story 3

- [x] T020 [US3] Add `PackConfig` + `PACKS` registry and `get_pack_config` in `packages/gacha/gacha/pack_configs.py` per `contracts/pack-config.md` (Standard = 60/30/8/2 and 10/30/30/30); define `UnknownPackConfigError` (or equivalent) in the same module or adjacent
- [x] T021 [US3] Refactor `generate_pack` in `packages/gacha/gacha/generator.py` to `generate_pack(n: int | None = None, *, pack_id: str = "standard")` reading config; remove hardcoded rarity weight literals from control flow
- [x] T022 [US3] Export pack helpers from `packages/gacha/gacha/__init__.py`; confirm `/store` path in `apps/discord_bot/cogs/store_cog.py` still calls `generate_pack` with default Standard behavior (no new store SKU)
- [x] T023 [US3] Grep `packages/player_engine` and `packages/gacha` for leftover `create_player_card` → raw dict assumptions missing `role`; ensure youth/regen/gacha all go through the typed contract (dict dumps only at RPC edge via `card_rpc_payload`)

**Checkpoint**: All three stories complete — archetypes + exact OVR + configurable packs

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Ship hygiene across all stories

- [x] T024 [P] Update player-facing note in `change_log.md` for archetype identities, accurate pack OVRs, and role on new cards
- [x] T025 [P] Reconcile gacha archetype / factory reliability behavior into `.specify/specs/v1.0.0/spec.md` and `.specify/specs/v1.0.0/plan.md` (SDD single source of truth)
- [x] T026 Apply migration 051 (via `scratch/apply_migration_051.py` or equivalent) and run `supabase/scripts/verify_required_schema.sql` (or project verify script) before treating bot role display as done
- [x] T027 Run through `specs/005-gacha-archetypes/quickstart.md` checklist (unit tests + one Discord pack claim smoke for role on embed + squad)
- [x] T028 Confirm no new slash commands/hubs/tables; no `discord` imports under `packages/`; `engine.POSITION_WEIGHTS` / PlayStyle synergy untouched; Standard mix unchanged; grep shows intake RPCs INSERT `role`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS US1 and US2**
- **US1 (Phase 3)**: Depends on Phase 2 — MVP
- **US2 (Phase 4)**: Depends on Phase 2 + preferably T007 (same `player_factory.py` — sequential after US1 factory edit)
- **US3 (Phase 5)**: Can start pack_configs + tests after Setup in parallel with Phase 2; generator/GachaPlayer mapping should land after T008–T009 (US1)
- **Polish (Phase 6)**: After desired stories complete (migration apply before Discord role smoke)

### User Story Dependencies

| Story | Depends on | Notes |
|-------|------------|-------|
| US1 Archetypes | Phase 2 | MVP; includes role persistence migration |
| US2 Exact OVR | Phase 2 + US1 factory return type | Same file as T007 — do after US1 |
| US3 Pack configs | US1 `GachaPlayer.role` mapping preferred | Pack config file itself is independent |

### Parallel Opportunities

```text
After T002:
  → T003 || T004 (model + catalog)
After Phase 2:
  → T006 (US1 tests) while starting T007
  → T013 || T014 || T015 (scratch/verify, embeds, regen test) after T011–T012 payload/SQL exist
After US1 factory done:
  → T016–T018 (US2) sequential in player_factory
  → T019–T020 (US3 pack config + tests) in parallel (different package)
After T008–T009:
  → T021–T023 (wire generate_pack)
```

### Parallel Example: US1 embeds + verify vs US3 pack config

```bash
# Safe in parallel once role is on GachaPlayer / payload:
Task: "Show archetype on pack claim in apps/discord_bot/embeds/gacha_embeds.py"
Task: "Add PackConfig registry in packages/gacha/gacha/pack_configs.py"
Task: "Create tests/test_pack_configs.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 Setup  
2. Phase 2 Foundational  
3. Phase 3 US1 Archetypes + role persistence + pack embed  
4. **STOP and VALIDATE** — generate cards / claim pack show distinct roles in DB + UI  
5. Demo / ship MVP if needed  

### Incremental Delivery

1. Setup + Foundational → catalog + `CreatedPlayerCard` ready  
2. US1 Archetypes + migration 051 → validate identity + persistence (MVP)  
3. US2 Deterministic OVR → validate exact targets  
4. US3 Pack configs → validate Standard mix + typed boundary  
5. Polish → changelog + SDD + quickstart + verify schema  

### Suggested MVP Scope

**US1 only** is a **local development checkpoint** (archetypes + role persistence + display) — not a production merge gate. **US2 must pass before merge** to satisfy FR-006/008. US3 (pack configs) can trail US2 but should land in the same release when practical.

---

## Notes

- [P] = different files, no incomplete-task dependencies  
- Do **not** change `calculate_true_ovr` or PlayStyle synergy tables  
- Do **not** ship a Defender/Gold pack `/store` product in this feature  
- Do **not** backfill historical `Balanced` rows  
- Do **not** leave any `create_player_card` caller on a dict path that drops `role`  
- Commit after each story checkpoint when asked; avoid drive-by refactors outside listed files  
