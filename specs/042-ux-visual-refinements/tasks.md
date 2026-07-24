# Tasks: Store / Swap / Hospital UX Refinements

**Input**: Design documents from `/specs/042-ux-visual-refinements/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included — plan/research/quickstart require unit coverage for near-full math and hospital slot capping; Confirm-gate regression for swap.

**Organization**: Tasks grouped by user story (P1 → P2 → P3) for independent delivery.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete work)
- **[Story]**: US1 / US2 / US3 maps to spec user stories
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm repo readiness; no new dependencies or migrations

- [x] T001 Confirm touch list vs `plan.md`: `packages/energy/`, `apps/discord_bot/cogs/store_cog.py`, `apps/discord_bot/cogs/squad_cog.py`, `apps/discord_bot/core/swap_compare.py`, `apps/discord_bot/core/hospital_board.py`, `apps/discord_bot/embeds/hospital_embeds.py`, `apps/discord_bot/views/store_facilities.py`, `tests/`; verify `assets/admited.png` (1536×1024) and `assets/fonts/Roboto-Bold.ttf` / `Roboto-Regular.ttf` exist
- [x] T002 [P] Confirm Pillow already used by `apps/discord_bot/core/pitch_generator.py` (no new pip dependency) and note `_ASSETS_DIR` + `_RENDER_SEM` reuse pattern for new render modules

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared constraints before story work — no schema; keep packages Discord-free

**⚠️ CRITICAL**: Complete before US1–US3 implementation

- [x] T003 Document fail-open / asset-fallback rules from `contracts/` into a one-line ponytail note target: energy data missing → refill stays enabled; hospital asset missing → text-only panel (no blocking exceptions in hub open paths)
- [x] T004 Confirm FR-015: no new slash commands, no migrations, no changes to `purchase_energy_refill` / `swap_squad_players` / admit-discharge RPC signatures

**Checkpoint**: Foundation ready — user stories can proceed independently (or in P1→P2→P3 order)

---

## Phase 3: User Story 1 — Near-Full Energy Refill Guard (Priority: P1) 🎯 MVP

**Goal**: Disable Buy Energy Refill when energy is at/near max with clear full vs near labels; recompute on every store open/refresh

**Independent Test**: Open `/store` with energy at max or within threshold → button disabled + label/copy; below threshold → purchase works as today

**Contract**: [contracts/energy-near-full-guard.md](./contracts/energy-near-full-guard.md)

### Tests for User Story 1

- [x] T005 [P] [US1] Add near-full matrix unit tests in `tests/test_energy_near_full.py` (full, near via within-5, near via 95%, below threshold, `maximum <= 0` fail-open) against `packages/energy` helpers — expect FAIL until T006–T007

### Implementation for User Story 1

- [x] T006 [P] [US1] Implement `is_energy_near_full` and `near_full_reason` in `packages/energy/energy/near_full.py` per contract (ceil 95% OR within 5 of max; full takes precedence at/above max)
- [x] T007 [US1] Export helpers from `packages/energy/energy/__init__.py` (`is_energy_near_full`, `near_full_reason`)
- [x] T008 [US1] Wire `show_store` + `StoreHubView` in `apps/discord_bot/cogs/store_cog.py`: after `sync_action_energy`, compute reason; disable `store_energy_refill` when near/full; set label `⚡ Energy already full` / `⚡ Near maximum` / restore `⚡ Buy Energy Refill`; update Energy Refill embed field copy; leave other buttons unchanged; recompute on every `show_store` refresh

**Checkpoint**: US1 shippable alone (MVP)

---

## Phase 4: User Story 2 — Visual Squad Swap Comparison (Priority: P2)

**Goal**: Side-by-side OUT/IN compare image on Swap Players; selects + Confirm gating unchanged

**Independent Test**: Open swap → placeholders image; select both → image shows name/pos/OVR; Confirm still gated; empty/incompatible bench → Confirm off, no fake IN player

**Contract**: [contracts/swap-compare-visual.md](./contracts/swap-compare-visual.md)

### Tests for User Story 2

- [x] T009 [P] [US2] Re-run / extend `tests/test_squad_swap_confirm.py` so Confirm remains disabled until both sides selected after any `SquadSwapView` changes (regression guard)

### Implementation for User Story 2

- [x] T010 [P] [US2] Create `apps/discord_bot/core/swap_compare.py` with `generate_swap_compare_image(out_card, in_card) -> discord.File` (`swap_compare.png`); reuse roster-card styling/fonts from `pitch_generator.py`; placeholders for null sides; optional PAC/SHO/PAS/DRI/DEF/PHY when present; use `_RENDER_SEM` + `asyncio.to_thread`
- [x] T011 [US2] Ensure starter/reserve dicts passed into swap include fields needed for compare (name, position, overall, rarity/attrs if already fetched) in `apps/discord_bot/cogs/squad_cog.py` open-swap path — extend fetch/select payload only if attrs missing
- [x] T012 [US2] Wire `SquadSwapView` in `apps/discord_bot/cogs/squad_cog.py`: on open and on bench/reserve select, regenerate compare file, `embed.set_image(url="attachment://swap_compare.png")`, `edit_message(..., attachments=[file])`; keep eligibility + Confirm gating; Back still restores pitch

**Checkpoint**: US1 + US2 both independently functional

---

## Phase 5: User Story 3 — Visual Hospital Patient Panel (Priority: P3)

**Goal**: Hospital panel shows `assets/admited.png` with up to 6 overlaid patient names; regenerates on each panel open; text waiting/overflow + asset fallback preserved

**Independent Test**: Empty hospital → empty board + “*No one admitted.*”; admit/discharge → names update on refresh; waiting list still visible; missing asset → text-only still usable

**Contract**: [contracts/hospital-admitted-visual.md](./contracts/hospital-admitted-visual.md)

### Tests for User Story 3

- [x] T013 [P] [US3] Add slot-cap / empty / overflow helper tests in `tests/test_hospital_board_slots.py` (max 6 overlay rows; overflow excluded from overlay list) — FAIL until helper exists

### Implementation for User Story 3

- [x] T014 [P] [US3] Implement patient row selection helper + `generate_hospital_board(patients) -> discord.File | None` in `apps/discord_bot/core/hospital_board.py` using `assets/admited.png`; overlay up to 6 names on lined rows (tunable Y%); empty list still returns empty board; missing/unreadable asset → `None`; `_RENDER_SEM` + `asyncio.to_thread`
- [x] T015 [US3] Update `hospital_panel_embed` in `apps/discord_bot/embeds/hospital_embeds.py` to accept optional image attachment flag / call `embed.set_image(url="attachment://hospital_board.png")` when board file will be attached; keep Current Patients + Waiting text fields (overflow names remain in text)
- [x] T016 [US3] Wire `show_hospital_panel` in `apps/discord_bot/views/store_facilities.py`: await board render; attach file when present; edit/send with `attachments=[file]`; admit/discharge/upgrade refresh paths already call this — verify visual updates without extra wiring

**Checkpoint**: All three stories independently functional

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Ship hygiene across stories

- [x] T017 [P] Update player-facing `change_log.md` with short notes for near-full refill disable, visual swap compare, and hospital board image
- [x] T018 Run unit suite from `specs/042-ux-visual-refinements/quickstart.md`: `pytest tests/test_energy_near_full.py tests/test_hospital_board_slots.py tests/test_squad_swap_confirm.py -q`
- [ ] T019 Manual Discord smoke per `quickstart.md` (Store near-full, Swap compare, Hospital empty/admit/discharge + optional asset-missing fallback)
- [x] T020 Grep for accidental new slash commands or direct `players.coins` / energy mutation bypasses in touched files; confirm packages have zero `discord` imports

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Start immediately
- **Foundational (Phase 2)**: After Setup — blocks story implementation
- **US1 (Phase 3)**: After Foundational — **MVP**
- **US2 (Phase 4)**: After Foundational — independent of US1
- **US3 (Phase 5)**: After Foundational — independent of US1/US2
- **Polish (Phase 6)**: After desired stories complete

### User Story Dependencies

```text
Phase 1 → Phase 2 → ┬→ US1 (P1) ──┐
                     ├→ US2 (P2) ──┼→ Phase 6 Polish
                     └→ US3 (P3) ──┘
```

- **US1**: No dependency on US2/US3
- **US2**: No dependency on US1/US3 (shares only Pillow patterns, not code from US1)
- **US3**: No dependency on US1/US2

### Within Each Story

- Tests first (expect fail) → pure/helper → Discord wiring → checkpoint

### Parallel Opportunities

- T001 then T002 [P] in Setup
- After T004: T005∥T006 (test + near_full.py), then T007→T008
- After Foundational: US1 / US2 / US3 can run in parallel by different owners
- Within US2: T009∥T010 then T011→T012
- Within US3: T013∥T014 then T015→T016
- Polish: T017∥T020; then T018→T019

---

## Parallel Example: After Foundational

```bash
# Developer A — MVP Store guard
Task: T005 tests/test_energy_near_full.py
Task: T006 packages/energy/energy/near_full.py
Task: T007-T008 store_cog wiring

# Developer B — Swap compare
Task: T009 test_squad_swap_confirm.py
Task: T010 apps/discord_bot/core/swap_compare.py
Task: T011-T012 squad_cog.py

# Developer C — Hospital board
Task: T013 tests/test_hospital_board_slots.py
Task: T014 apps/discord_bot/core/hospital_board.py
Task: T015-T016 hospital_embeds.py + store_facilities.py
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 + Phase 2  
2. Phase 3 (T005–T008)  
3. **STOP** — validate `/store` near-full disable  
4. Ship Store guard alone if needed  

### Incremental Delivery

1. Setup + Foundational  
2. US1 → demo Store  
3. US2 → demo Swap visual  
4. US3 → demo Hospital board  
5. Polish (changelog + quickstart)  

### Notes

- Do **not** rename `assets/admited.png` in v1  
- Discord buttons: label + embed field substitute for tooltips  
- Keep dual selects on swap; image is advisory only  
- Hospital waiting list stays text; visual = admitted overlay only  

---

## Task Summary

| Phase | Tasks | Count |
|-------|-------|-------|
| Setup | T001–T002 | 2 |
| Foundational | T003–T004 | 2 |
| US1 Energy (P1) | T005–T008 | 4 |
| US2 Swap (P2) | T009–T012 | 4 |
| US3 Hospital (P3) | T013–T016 | 4 |
| Polish | T017–T020 | 4 |
| **Total** | T001–T020 | **20** |
