# Tasks: Profile Finance & Hospital Hub

**Input**: Design documents from `/specs/003-profile-finance-hospital/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included — plan/quickstart require pure formatter coverage for L0 empty-state, bed copy, and patient-list truncation (`tests/test_profile_hospital_summary.py`). Discord flows validated via quickstart.

**Organization**: Tasks grouped by user story (US1–US4) for incremental delivery.

**Locked decisions** (from research.md):
- `show_profile` + `ProfileHubView` hub pattern
- Reuse `HospitalPanelView` with `origin="facilities"|"profile"` + add Upgrade on panel
- L0 profile summary = empty-state copy; panel keeps `beds = level + 1`
- Finances = shared builder with `/club-finances` (no ledger)
- Club Stats → `show_squad_hub`
- Keep `guild_only`; no new slash/migration/RPC

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 / US2 / US3 / US4
- Include exact file paths in descriptions

## Path Conventions

- Bot: `apps/discord_bot/`
- Embeds: `apps/discord_bot/embeds/`
- Views: `apps/discord_bot/views/`
- Tests: `tests/` at repo root
- SDD: `.specify/specs/v1.0.0/`
- Feature docs: `specs/003-profile-finance-hospital/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm scope and contracts before code

- [x] T001 Review `specs/003-profile-finance-hospital/plan.md` against `contracts/profile-dashboard.md`, `contracts/profile-hospital-nav.md`, and `contracts/club-finances-soft-deprecate.md`; note any drift in `specs/003-profile-finance-hospital/research.md` if found
- [x] T002 [P] Confirm migration `050_fatigue_injury_hospital.sql` already defines `hospital_level` / `hospital_patients` and that this feature needs **no** new migration file

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared embed builders and extractable `show_*` entry points all stories reuse

**⚠️ CRITICAL**: No user-story hub wiring until formatters + extracted helpers exist

- [x] T003 Create `apps/discord_bot/embeds/profile_embeds.py` with pure helpers for Club Finance field text and Hospital summary states (L0 empty-state per FR-004; L≥1 beds/recovery/patients; truncation cue; hospital-unavailable fallback string)
- [x] T004 [P] Export or share patient ETA formatting from `apps/discord_bot/embeds/hospital_embeds.py` (e.g. promote `_eta_str`) so profile summary and hospital panel stay consistent
- [x] T005 Extract `build_club_finances_embed(player, starting_cards, *, weekly_wages)` (and keep fetch logic callable) from `apps/discord_bot/cogs/economy_cog.py` into a shared helper in that module or `apps/discord_bot/embeds/` — `/club-finances` must call the shared builder
- [x] T006 Extract `async def show_squad_hub(interaction, owner_id)` from `apps/discord_bot/cogs/squad_cog.py` so `/squad` and profile Club Stats share one entry (pitch + `SquadHubView`)
- [x] T007 [P] Add `tests/test_profile_hospital_summary.py` covering L0 empty-state copy, L≥1 `occupied/capacity` + recovery line, patient truncation (“and N more”), and unavailable fallback — assert helpers never invent beds when level is 0

**Checkpoint**: Formatters tested; finances embed + squad hub callable; `/profile` behavior unchanged until US1

---

## Phase 3: User Story 1 — One-Stop Club Dashboard (Priority: P1) 🎯 MVP

**Goal**: `/profile` shows Club Finance + Hospital summary alongside existing identity/energy/division/record/trophies

**Independent Test**: Run `/profile` with L0 and with L≥1 (± patients); confirm finance + hospital sections and that league/record/trophies remain

### Implementation for User Story 1

- [x] T008 [US1] Implement `async def show_profile(interaction, owner_id)` in `apps/discord_bot/cogs/profile_cog.py` that re-fetches `players` by `discord_id`, syncs action energy (existing helpers), loads active `hospital_patients` with `player_cards` join (`discharge_date` null), and builds the dashboard embed via `profile_embeds` + existing division/trophy logic
- [x] T009 [US1] Reorganize `/profile` embed fields so Club Finance (coins + gems/`tokens`) and Hospital sections match `contracts/profile-dashboard.md` and the UX mockup in `specs/003-profile-finance-hospital/spec.md` without removing energy/division/record/trophy fields
- [x] T010 [US1] Point `ProfileCog.profile` at `show_profile` (keep `@guild_only`, `@ensure_registered`, immediate defer); send embed ephemeral (hub view added in US2)

**Checkpoint**: US1 shippable alone — rich read-only dashboard without requiring button navigation

---

## Phase 4: User Story 2 — Action Buttons Under Profile (Priority: P1)

**Goal**: Profile hub buttons open Hospital management, Finances detail, and Squad stats; Back/refresh updates the dashboard

**Independent Test**: From `/profile`, exercise all three buttons; upgrade/discharge from profile-origin hospital; Back shows updated coins/level/beds/patients

### Implementation for User Story 2

- [x] T011 [US2] Add `origin: Literal["facilities", "profile"] = "facilities"` to `show_hospital_panel` and `HospitalPanelView` in `apps/discord_bot/views/store_facilities.py`; Back → `show_facilities` when `facilities`, lazy-import `show_profile` when `profile`
- [x] T012 [US2] Add **Upgrade Hospital** control on `HospitalPanelView` in `apps/discord_bot/views/store_facilities.py` reusing the same `upgrade_club_facility` / gate logic as `FacilitiesHubView` hospital upgrade; refresh panel with same `origin` after success
- [x] T013 [US2] Implement `ProfileHubView` in `apps/discord_bot/cogs/profile_cog.py` (owner `interaction_check`, timeout ~180–900s, timeout disable helper) with buttons: 🏥 Manage Hospital → `show_hospital_panel(..., origin="profile")`; 💰 Finances → finance panel; 📊 View Club Stats → `show_squad_hub`
- [x] T014 [US2] Implement Finances sub-view (embed from T005 + Back to Profile calling `show_profile`) in `apps/discord_bot/cogs/profile_cog.py` or `economy_cog.py`; wire ProfileHubView Finances button to it
- [x] T015 [US2] Attach `ProfileHubView` in `show_profile` so `/profile` and Back-to-Profile refreshes always re-bind buttons on the refreshed embed
- [x] T016 [US2] Grep `apps/discord_bot/` to confirm Store → Facilities → Hospital → Back still defaults `origin="facilities"` and no new `/hospital` slash command was added

**Checkpoint**: US1 + US2 — full one-stop hub with round-trip refresh

---

## Phase 5: User Story 3 — Graceful Empty / Missing-Club / Partial Failure (Priority: P2)

**Goal**: Clear messaging for no-club, guild-only DMs, hospital fetch failure, and long patient lists

**Independent Test**: Unregistered / DM / forced hospital query failure / many patients behave per quickstart §7

### Implementation for User Story 3

- [x] T017 [US3] In `show_profile` (`apps/discord_bot/cogs/profile_cog.py`), wrap hospital patients fetch so failure sets Hospital section to the unavailable fallback from `profile_embeds` while finance + core profile still render
- [x] T018 [P] [US3] Confirm patient truncation + “Manage Hospital” cue from T003/T007 is applied in the live embed path in `apps/discord_bot/embeds/profile_embeds.py` (cap ~5 lines)
- [x] T019 [US3] Verify `/profile` retains `@app_commands.guild_only()` and `@ensure_registered` in `apps/discord_bot/cogs/profile_cog.py`; document in code comment or footer that DMs are guild-only (no custom DM dashboard in v1)
- [x] T020 [P] [US3] Ensure ProfileHubView / hospital / finances views use owner checks and timeout disable (`apps/discord_bot/core/view_helpers.py` patterns) with clear recovery (“run `/profile` again”) on stale interaction where applicable

**Checkpoint**: Edge paths fail soft; happy path unchanged

---

## Phase 6: User Story 4 — Soft-Deprecate `/club-finances` (Priority: P3)

**Goal**: Keep `/club-finances` working; point managers to `/profile`; Finances button stays in parity

**Independent Test**: `/club-finances` shows wallet/wages/facilities + `/profile` pointer; Finances button matches content

### Implementation for User Story 4

- [x] T021 [US4] Update `/club-finances` in `apps/discord_bot/cogs/economy_cog.py` to use the shared builder from T005 and add footer/description pointer: unified dashboard on `/profile`
- [x] T022 [US4] Confirm Finances button panel and `/club-finances` stay field-parity (wallet, wages, YA/TG/Hospital levels) with no ledger UI

**Checkpoint**: Soft transition complete; no command deletion

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Ship hygiene across stories

- [x] T023 [P] Update player-facing `change_log.md` with `/profile` finance + hospital hub note
- [x] T024 [P] Reconcile feature into `.specify/specs/v1.0.0/spec.md` and `.specify/specs/v1.0.0/plan.md` (hub surface; no new slash commands)
- [x] T025 Run `pytest tests/test_profile_hospital_summary.py -q` and walk `specs/003-profile-finance-hospital/quickstart.md` scenarios 1–7
- [x] T026 Grep `apps/discord_bot/` for accidental new `@app_commands.command` hospital/finances aliases and for direct `players.coins` updates in profile/hospital UI paths (must remain RPC-only on upgrade)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Start immediately
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS** all user stories
- **US1 (Phase 3)**: Depends on Foundational — 🎯 MVP
- **US2 (Phase 4)**: Depends on US1 `show_profile` existing (attaches hub + navigation)
- **US3 (Phase 5)**: Depends on US1 embed path; ideally after US2 for stale-button checks
- **US4 (Phase 6)**: Depends on T005 shared finances builder; can follow US2 Finances panel
- **Polish (Phase 7)**: After desired stories complete

### User Story Dependencies

```text
Phase 2 Foundational
        │
        ▼
   US1 Dashboard (MVP)
        │
        ├──────────────► US3 Edge handling
        │
        ▼
   US2 Action buttons ──► US4 Soft-deprecate /club-finances
        │
        ▼
     Polish
```

- **US1**: No dependency on buttons
- **US2**: Needs `show_profile` + hospital/finances/squad extractors
- **US3**: Hardens US1/US2; independently testable via quickstart edges
- **US4**: Needs shared finances builder; independent of hospital nav

### Parallel Opportunities

- T002 ∥ T001 (after skim)
- T004 ∥ T003 (different files)
- T007 after T003 (tests for formatters)
- T005 ∥ T006 (economy_cog vs squad_cog)
- T018 ∥ T020 within US3
- T023 ∥ T024 in Polish

---

## Parallel Example: Foundational

```bash
# After T003 exists:
Task: "Export ETA helper in apps/discord_bot/embeds/hospital_embeds.py"
Task: "Extract show_squad_hub in apps/discord_bot/cogs/squad_cog.py"
Task: "Extract build_club_finances_embed from apps/discord_bot/cogs/economy_cog.py"
```

## Parallel Example: User Story 2 prep

```bash
# Hospital origin + upgrade can land before ProfileHubView wiring:
Task: "Add origin param to show_hospital_panel in apps/discord_bot/views/store_facilities.py"
Task: "Add Upgrade Hospital on HospitalPanelView in apps/discord_bot/views/store_facilities.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1–2 (formatters, extracts, unit tests)
2. Complete Phase 3 US1 (`show_profile` dashboard)
3. **STOP and VALIDATE**: `/profile` finance + hospital sections
4. Demo read-only hub before button work

### Incremental Delivery

1. Setup + Foundational → helpers ready
2. US1 → dashboard MVP
3. US2 → full hub navigation + refresh
4. US3 → soft-fail edges
5. US4 → `/club-finances` pointer
6. Polish → changelog, SDD, quickstart

### Suggested MVP Scope

**US1 only** (T001–T010): managers see finance + hospital on `/profile` without buttons. Ship US2 next for the “one-stop actions” promise.

---

## Notes

- No new migration, RPC, or slash command in any task
- Lazy-import cross-cog `show_*` in button callbacks to avoid cycles
- Hospital math/costs remain owned by `002-injury-fatigue-hospital`
- Commit after each task or logical group when asked
