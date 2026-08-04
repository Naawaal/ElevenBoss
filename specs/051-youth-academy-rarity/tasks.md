# Tasks: Youth Academy Rarity-Cap Redesign

**Input**: Design documents from `/specs/051-youth-academy-rarity/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included â€” plan/quickstart require pytest for caps, V2 generation, scout ranges, weekly ledger; schema verify after migration **095**. AGENTS.md: non-trivial pure logic leaves a runnable check.

**Locked decisions** (research.md / plan.md):
- Capacity **3/3/4/4/5**; intake default **2**; promote cap **2**/UTC week
- Rarity-first generation; Legendary L5-only (~0.1%) + kill switch; no pity
- Scout split: **assessment** (narrow ranges) + **discovery** (paid seat under capacity/sign ledger)
- FR-022: Python generate + RPC reject-invalid (not silent rarity upgrade)
- Cutover: repair illegal POT, init ranges, grandfather over-cap; flag `youth_academy_v2_enabled`
- Migration **095** (repo head 094); no `/academy`; no second player table
- Cite **US-42.2 / US-42.7 / US-42.9**; fees via `apply_club_economy` only
- Primary hub: `/development`; Squad optional; Profile compatibility

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: US1â€“US8 maps to spec user stories
- Exact file paths required

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm live academy RPC surface and touch list before coding

- [x] T001 Diff live/repo defs for `process_youth_intake`, `promote_academy_player`, `release_academy_player`, `dispatch_youth_scout`, `finalize_youth_scout_report`, `sign_youth_scout_prospect`, `process_daily_academy_growth`, `academy_slot_cap`, `upgrade_club_facility`; append notes under `specs/051-youth-academy-rarity/research.md` if drift vs migrations 060/075/088
- [x] T002 [P] Grep academy touch list across `packages/economy/economy/facility_effects.py`, `packages/player_engine/player_engine/youth_intake.py`, `packages/player_engine/player_engine/youth_math.py`, `apps/discord_bot/views/academy_hub.py`, `apps/discord_bot/embeds/academy_embeds.py`, `apps/discord_bot/tasks/youth_intake_notifier.py`, `apps/discord_bot/tasks/academy_growth_job.py`, `tests/test_academy_slots.py`; confirm matches `specs/051-youth-academy-rarity/plan.md` source tree

**Checkpoint**: No coding against stale scout/intake signatures

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared pure helpers, config mirrors, and migration **095** schema spine â€” **MUST land before story RPCs/UI**

**âš ï¸ CRITICAL**: No US1â€“US8 implementation until caps, range helpers, and 095 columns/config exist

- [x] T003 Update `ACADEMY_SLOT_CAPS` / `academy_slot_cap()` to `{1:3,2:3,3:4,4:4,5:5}` in `packages/economy/economy/facility_effects.py`; add rarity-weight + initial-range-width + facility preview helper stubs (concrete tables filled in US1/US5)
- [x] T004 [P] Create `packages/player_engine/player_engine/scout_ranges.py`: `init_visible_range(potential, rarity, academy_level)`, `narrow_range(lo, hi, potential, tier)`, `star_band_from_interval(lo, hi)` â€” monotonic, always contains true POT, respects `rarity_potential_cap`
- [x] T005 [P] Extend `packages/player_engine/player_engine/youth_math.py`: growth speed by YA level; advisory `ready_ovr_for_level`; keep growth off `apply_card_xp`
- [x] T006 Export new helpers from `packages/player_engine/player_engine/__init__.py` and `packages/economy/economy/__init__.py` (if that package re-exports facility helpers)
- [x] T007 Create `supabase/migrations/095_youth_academy_rarity_v2.sql` spine: `player_cards` columns (`pot_visible_lo/hi`, `scout_assessment_level`, `academy_origin`, `academy_age_out_pending_at`, `academy_warned_aging_at`); table `academy_weekly_actions` + RLS; rewrite SQL `academy_slot_cap` to 3/3/4/4/5; insert `game_config` keys from `data-model.md` (including `youth_intake_count=2`, `youth_academy_v2_enabled=false`, Legendary kill switch, promote fee/caps); schema guard DO block stubs for new objects
- [x] T008 [P] Extend `supabase/scripts/verify_required_schema.sql` for new columns, `academy_weekly_actions`, policies, and functions added in 095
- [x] T009 Add `scratch/apply_migration_095.py` mirroring prior apply scripts; do not flip V2 flag yet
- [x] T010 [P] Update `tests/test_academy_slots.py` for new cap curve; add skeleton `tests/test_scout_ranges.py` covering init/narrow/monotonic failures

**Checkpoint**: Foundation ready â€” generation, seating, scout, and cutover can share one law

---

## Phase 3: User Story 1 â€” Trust every academy playerâ€™s rarity ceiling (Priority: P1) ðŸŽ¯ MVP

**Goal**: Every academy-generated/signed prospect obeys `overall â‰¤ potential â‰¤ rarity ceiling`; upgrades never reroll existing identity

**Independent Test**: Generate/sign at YA L1â€“L5 across rarities; POT never exceeds cap; OVR â‰¤ POT; Legendary absent below L5; kill switch zeros L5 Legendary

**Contracts**: [rarity-generation-v2.md](./contracts/rarity-generation-v2.md)

### Tests for User Story 1

- [x] T011 [P] [US1] Add `tests/test_youth_intake_v2.py`: rarity-first samples at each YA level; Common/Rare/Epic/Legendary ceilings; L&lt;5 Legendary rate 0; kill switch; property assert integrity via `validate_potential_integrity`

### Implementation for User Story 1

- [x] T012 [US1] Rewrite `packages/player_engine/player_engine/youth_intake.py` for V2: roll rarity from level weights â†’ OVR/POT bands within cap; default count 2; remove Common-only + gem `+5` as V2 path; reuse `clamp_potential` / `create_player_card`
- [x] T013 [P] [US1] Update `packages/gacha/gacha/generator.py` wrappers (`generate_youth_intake` / discovery helper) to call V2 card generation
- [x] T014 [US1] In `095_youth_academy_rarity_v2.sql`, harden `process_youth_intake` and discovery-sign path: call `assert_card_potential_integrity`; reject Legendary when YA level &lt; 5 or kill switch on; reject illegal bot payloads (FR-022 â€” no silent rarity upgrade)
- [x] T015 [US1] Gate V2 generator in `apps/discord_bot/tasks/youth_intake_notifier.py` on `youth_academy_v2_enabled` / generation version; keep seating via `process_youth_intake`

**Checkpoint**: US1 MVP â€” new academy cards cannot break rarity ceilings

---

## Phase 4: User Story 2 â€” Limited weekly youth intake (Priority: P1)

**Goal**: Monday free intake seats at most 2 into free capacity only; idempotent per UTC week; full/over-cap â†’ 0 seats + clear block

**Independent Test**: Known free seats â†’ seated = min(2, free); full â†’ 0 + capacity_blocked; same-week retry â†’ no duplicate

**Contracts**: [rarity-generation-v2.md](./contracts/rarity-generation-v2.md), [capacity-cutover.md](./contracts/capacity-cutover.md) (free_seats rule)

### Implementation for User Story 2

- [x] T016 [US2] Ensure `game_config.youth_intake_count` default 2 and Python default `n=2` in `packages/player_engine/player_engine/youth_intake.py` + `apps/discord_bot/tasks/youth_intake_notifier.py`
- [x] T017 [US2] Update `process_youth_intake` in `supabase/migrations/095_youth_academy_rarity_v2.sql`: `free_seats = max(0, academy_slot_cap(level) - occupied)`; seat only min(payload, free_seats); return `capacity_blocked` when zero; keep `youth_intake_log` week idempotency
- [x] T018 [US2] Update intake DM/copy in `apps/discord_bot/embeds/youth_intake_embeds.py` for partial seat / capacity blocked messaging (still no exact POT dump â€” ranges land with US3)

**Checkpoint**: US2 â€” weekly heartbeat respects new retention math

---

## Phase 5: User Story 8 â€” Fair cutover for illegal / over-capacity academies (Priority: P1)

**Goal**: Repair illegal academy POT without lowering legal OVR; grandfather over-cap; init scouting ranges containing true POT; escalate OVR&gt;cap rows

**Independent Test**: Sample illegal Common/Rare repaired; over-cap club keeps seats, acquisitions blocked; ranges contain POT

**Contracts**: [capacity-cutover.md](./contracts/capacity-cutover.md)

### Implementation for User Story 8

- [x] T019 [US8] Add cutover SQL in `supabase/migrations/095_youth_academy_rarity_v2.sql`: audit/repair academy POT â‰¤ cap without reducing legal OVR; leave overall&gt;cap for 049 escalation; set `academy_origin='migration'` where null; init `pot_visible_lo/hi` via width table; set assessment level none
- [x] T020 [US8] Enforce strict `occupied < cap` on intake + discovery-sign RPCs in `095_youth_academy_rarity_v2.sql` (over-cap â‡’ block adds)
- [x] T021 [US8] Apply 095 on clone via `scratch/apply_migration_095.py`; run `supabase/scripts/verify_required_schema.sql`; spot-check over-cap and repaired rows
- [x] T022 [P] [US8] Document ops cutover checklist in `specs/051-youth-academy-rarity/quickstart.md` Â§2 (clone â†’ verify â†’ flag flip order)

**Checkpoint**: Live clubs survivable before enabling V2 UI flag

---

## Phase 6: User Story 3 â€” Evaluate uncertain potential through scouting (Priority: P1)

**Goal**: Prospects show approximate POT range; assessment scouts narrow only; Deep â‰  exact POT default; stars from interval; no double-charge conflicts

**Independent Test**: Unscouted â†’ tier ladder â†’ range only narrows and contains true POT; conflict dispatch rejected

**Contracts**: [scout-assessment-ranges.md](./contracts/scout-assessment-ranges.md)

### Tests for User Story 3

- [x] T023 [P] [US3] Complete `tests/test_scout_ranges.py`: init contains POT; Quick/Standard/Deep narrow monotonic; Deep width â‰¥ configured min; never widens; star_band_from_interval ignores hidden exact when interval mid differs

### Implementation for User Story 3

- [x] T024 [US3] Add assessment job table or per-card job columns + RPCs in `095_youth_academy_rarity_v2.sql`: `dispatch_academy_assessment` / `finalize_academy_assessment` (names per migration) â€” charge via `apply_club_economy`, idempotent conflict reject, narrow bounds on finalize
- [x] T025 [US3] Rebalance discovery path in same migration: paid add max 1 under capacity + weekly sign counter hook (counter table used fully in US4); fog discovery presentation away from exact Deep POT shortlist-as-primary
- [x] T026 [US3] Update `apps/discord_bot/embeds/academy_embeds.py` + `apps/discord_bot/embeds/youth_intake_embeds.py`: range + interval stars; remove default exact POT on Deep/list/intake
- [x] T027 [US3] Wire assess actions + finalize-due in `apps/discord_bot/views/academy_hub.py` and `apps/discord_bot/tasks/academy_growth_job.py` (or scout finalize hook); map errors in `apps/discord_bot/core/api_errors.py`

**Checkpoint**: US3 â€” discovery fantasy without POT spoilers

---

## Phase 7: User Story 4 â€” Develop, promote, or release within limits (Priority: P2)

**Goal**: Daily growth â‰¤ POT/cap; early promote allowed; max 2 promotes/UTC week; roster-cap safe; graduation embed; release frees seat no refund

**Independent Test**: Grow below ready; promote twice OK; third blocked; full roster fails clean; release cannot re-promote

**Contracts**: [weekly-actions-ledger.md](./contracts/weekly-actions-ledger.md)

### Tests for User Story 4

- [x] T028 [P] [US4] Add `tests/test_academy_weekly_ledger.py`: promote counter increments; first-free fee still counts; cap blocks; paid-sign counter independent

### Implementation for User Story 4

- [x] T029 [US4] Rewrite `promote_academy_player` in `095_youth_academy_rarity_v2.sql`: weekly ledger lock; fee via `apply_club_economy` (`academy_promote_fee` / first free); senior soft-cap; return graduation fields; no card duplication
- [x] T030 [P] [US4] Confirm `release_academy_player` frees seat, no refund, blocks later promote; keep 075 state guards
- [x] T031 [US4] Ensure `process_daily_academy_growth` never raises OVR above POT or rarity cap (088 assert path retained/extended in 095)
- [x] T032 [US4] Add graduation embed helper in `apps/discord_bot/embeds/academy_embeds.py`; use from `AcademyHubView._promote` in `apps/discord_bot/views/academy_hub.py`; show weekly promotes used/cap on hub

**Checkpoint**: US4 â€” promotion payoff with retention brakes

---

## Phase 8: User Story 5 â€” Facilities improve odds, not rerolls (Priority: P2)

**Goal**: YA upgrade preview shows capacity/rarity/range-width/growth beforeâ†’after; upgrade does not mutate existing prospects; L5 Legendary ultra-rare / disableable

**Independent Test**: Preview numerics; upgrade; existing rarity/POT unchanged; capacity curve 3/3/4/4/5

**Contracts**: [academy-hub-surfaces.md](./contracts/academy-hub-surfaces.md), [rarity-generation-v2.md](./contracts/rarity-generation-v2.md)

### Implementation for User Story 5

- [x] T033 [US5] Fill rarity weights, range widths, growth multipliers in `packages/economy/economy/facility_effects.py` + validated `game_config` JSON keys (FR-021 sum/bands/caps checks in pure loader or SQL comments + Python validate)
- [x] T034 [US5] Expand `_youth_next_preview` / YA field in `apps/discord_bot/views/store_facilities.py` for capacity, rarity odds, scout-range width, development speed beforeâ†’after
- [x] T035 [P] [US5] Assert `upgrade_club_facility` path does not touch seated cardsâ€™ rarity/POT (spot test or SQL comment + regression note in `tests/test_academy_slots.py`)

**Checkpoint**: US5 â€” facility spend feels fair and concrete

---

## Phase 9: User Story 7 â€” Reach academy from existing hubs (Priority: P2)

**Goal**: Same academy hub from Development (primary), optional Squad, Profile compatibility; compact status lines; no `/academy`

**Independent Test**: Open from `/development`, `/squad` (if present), Profile Manage Academy â†’ one experience; no new slash command

**Contracts**: [academy-hub-surfaces.md](./contracts/academy-hub-surfaces.md)

### Implementation for User Story 7

- [x] T036 [US7] Add Youth Academy button on `DevelopmentHubView` in `apps/discord_bot/cogs/development_cog.py` â†’ `show_academy_hub(..., origin="development")`
- [x] T037 [P] [US7] Add optional Youth button + compact academy status on `SquadHubView` / squad embeds in `apps/discord_bot/cogs/squad_cog.py`
- [x] T038 [P] [US7] Keep `ProfileHubView.manage_academy` in `apps/discord_bot/cogs/profile_cog.py`; add compact academy line on profile embed; origin `"profile"`
- [x] T039 [US7] Make `AcademyHubView._back` origin-aware in `apps/discord_bot/views/academy_hub.py`; update footers/copy that hardcode `/profile â†’ Manage Academy` in academy/intake/scout DMs
- [x] T040 [P] [US7] Grep for `/academy` command registration under `apps/discord_bot/` â€” confirm none added

**Checkpoint**: US7 â€” discoverable without a new command family

---

## Phase 10: User Story 6 â€” Aging pressure without silent deletion (Priority: P3)

**Goal**: Warn â†’ â‰¤1 POT decay/season â†’ age-out pending + grace â†’ auto-release (not forced senior / not silent delete)

**Independent Test**: Fixture through warn, decay, pending, grace expiry â†’ auto-release; hub shows warning before decay

**Contracts**: [capacity-cutover.md](./contracts/capacity-cutover.md)

### Implementation for User Story 6

- [x] T041 [US6] Replace promote-or-delete@20 in `process_daily_academy_growth` (and/or hook `process_season_aging`) inside `095_youth_academy_rarity_v2.sql` with warn stamp, decay â‰¤1, pending+grace, auto-release per config keys
- [x] T042 [US6] Surface aging warning / pending copy in `apps/discord_bot/embeds/academy_embeds.py` and hub load path in `apps/discord_bot/views/academy_hub.py`
- [x] T043 [P] [US6] Add pure/unit coverage for decay bounds in `tests/test_youth_math.py` (or new aging helper tests)

**Checkpoint**: US6 â€” urgency without roster inflation or silent loss

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: Rollout, observability, docs, acceptance

- [x] T044 Flip rollout: set `youth_academy_v2_enabled=true` only after 095 verified + bot build deployed; document order in `specs/051-youth-academy-rarity/quickstart.md`
- [x] T045 [P] Add structured logging / counters for generation volume, rarityÃ—level mix, Legendary count, capacity blocks, promote/release in intake/growth/promote paths (`apps/discord_bot/tasks/youth_intake_notifier.py`, academy RPCs via returned jsonb fields)
- [x] T046 [P] Update `change_log.md` with player-facing YA V2 (capacity, intake 2, scouting ranges, promote weekly limit, Development entry)
- [x] T047 Reconcile `.specify/specs/v1.0.0/spec.md` and `.specify/specs/v1.0.0/plan.md` with shipped YA V2 behavior (SDD rule)
- [x] T048 Run `specs/051-youth-academy-rarity/quickstart.md` scenarios; map results to SC-001â€¦SC-010
- [x] T049 [P] Grep superseded Common-only gem path / old slot asserts / exact Deep POT copy â€” remove dead callers in `packages/` and `apps/discord_bot/`
- [x] T050 Wiring/integrity pass: every new RPC has a call site; no orphan helpers; cite US-42.2/42.7/42.9 in PR blurb when implementing

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (1)** â†’ **Foundational (2)** â†’ blocks all stories
- **US1 (3)** â†’ enables safe generation for US2/US3 discovery
- **US2 (4)** â†’ intake seating uses foundational caps + US1 generator
- **US8 (5)** â†’ needs 095 columns from Phase 2; should complete before production flag flip
- **US3 (6)** â†’ needs visible-range columns + US1 integrity
- **US4 (7)** â†’ needs weekly ledger from Phase 2; promote after seating works
- **US5 (8)** â†’ preview math can parallel US4 after weights exist (T033 after T012)
- **US7 (9)** â†’ UI entry after hub shows ranges/counters (after US3/US4 preferred)
- **US6 (10)** â†’ aging after growth/promote paths stable
- **Polish (11)** â†’ after desired stories complete

### User Story Dependencies

| Story | Depends on | Can parallelize with |
|-------|------------|----------------------|
| US1 | Phase 2 | â€” (MVP first) |
| US2 | US1 + Phase 2 | US8 prep after columns |
| US8 | Phase 2 (+ US1 repair helpers) | US2 |
| US3 | Phase 2 + US1 | US4 ledger SQL after table exists |
| US4 | Phase 2 + US1 | US5 preview copy |
| US5 | Phase 2 + US1 weights | US7 embeds |
| US7 | US3/US4 hub fields preferred | â€” |
| US6 | US4 growth path | Polish docs |

### Parallel Opportunities

- T003 / T004 / T005 after T001â€“T002
- T011 / T013 while T012 in progress (tests first then fill)
- T037 / T038 / T040 in US7
- T045 / T046 / T049 in Polish

---

## Parallel Example: User Story 1

```text
# After Phase 2:
Task: T011 tests/test_youth_intake_v2.py
Task: T013 packages/gacha/gacha/generator.py wrappers
# Then sequential:
Task: T012 youth_intake.py V2 rewrite
Task: T014 RPC integrity in 095
Task: T015 youth_intake_notifier.py gate
```

---

## Parallel Example: User Story 7

```text
Task: T036 development_cog.py Youth button
Task: T037 squad_cog.py Youth + status
Task: T038 profile_cog.py compatibility + status
# Then:
Task: T039 academy_hub.py origin-aware back + copy
Task: T040 grep no /academy
```

---

## Implementation Strategy

### MVP First (US1 only)

1. Phase 1 Setup  
2. Phase 2 Foundational (095 spine + caps + scout_ranges)  
3. Phase 3 US1 rarity-safe generation + RPC reject  
4. **STOP** â€” validate ceilings on sample generations before intake/UI rework  

### Incremental delivery

1. US1 â†’ US2 intake retention â†’ US8 cutover on clone  
2. US3 scout ranges â†’ US4 promote ledger â†’ US5 facility preview  
3. US7 hub entry â†’ US6 aging â†’ Polish + flag flip  

### Suggested MVP scope

**US1 + foundational caps/columns** â€” stops illegal academy POT fantasy.  
**Ship-ready vertical slice**: US1 + US2 + US8 + US3 + US4 + US7 (P1s + promote limits + Development entry). US5/US6 can trail one release if needed; do not enable flag without US8 cutover on target DB.

---

## Notes

- Single migration **095** preferred; only add **096** if VALIDATE/CHECK must wait on long repair
- Do not trust client rarity/POT; do not invent rarity on cutover to save illegal POT
- Academy growth remains auto-stat ticks â€” never `apply_card_xp`
- Commit after each task or logical group when implementing; stop at checkpoints to validate
