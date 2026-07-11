# Tasks: Player Fatigue, Injury & Hospital

**Input**: Design documents from `/specs/002-injury-fatigue-hospital/`

**Prerequisites**: plan.md, plan-phase3.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included — plan/quickstart require pure formula coverage; AGENTS.md non-trivial logic check.

**Organization**:
- **Phases 1–2 (US1–US3)**: shipped — T001–T042 below (all `[x]`)
- **Phase 3 (US4)**: in-match substitution UI — **T043–T062** (unchecked)

**Locked decisions**: Q1=A costs · Q2=A no Tier-4 retire · Q3=A Phase 3 isolated PR · Injury soft-cap **A+C** · Phase 3: no `generator.send()`; pause via `asyncio.Event` + `MatchState` mutation

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 / US2 / US3 / **US4** (Phase 3)
- Include exact file paths in descriptions

## Path Conventions

- Packages: `packages/player_engine/`, `packages/match_engine/`, `packages/economy/`
- Bot: `apps/discord_bot/`
- Migrations / verify: `supabase/migrations/`, `supabase/scripts/`
- Tests: `tests/` at repo root
- SDD: `.specify/specs/v1.0.0/`
- Phase 3 plan: `specs/002-injury-fatigue-hospital/plan-phase3.md`
- Phase 3 contract: `specs/002-injury-fatigue-hospital/contracts/in-match-injury-sub.md`

---

## Phase 1: Setup (Shared Infrastructure) — SHIPPED

**Purpose**: Align docs and exports before schema/code

- [x] T001 Review `specs/002-injury-fatigue-hospital/plan.md` Economy Gate + A+C soft-cap against `contracts/fatigue-match.md`, `contracts/post-match-injury-rpc.md`, `contracts/hospital-facility.md`
- [x] T002 [P] Confirm next migration number after `049_verify_apply_card_xp_security_definer.sql` and name file `supabase/migrations/050_fatigue_injury_hospital.sql` (renumber if 050 already taken)

---

## Phase 2: Foundational (Blocking Prerequisites) — SHIPPED

**Purpose**: Schema + config + package exports that all stories need

**⚠️ CRITICAL**: No user-story wiring until migration objects exist and verify guards are sketched

- [x] T003 Create `supabase/migrations/050_fatigue_injury_hospital.sql` adding `player_cards.fatigue` (DEFAULT 100), injury columns, `players.hospital_level` (DEFAULT 0), `hospital_patients` + RLS policies, `game_config` seeds (`hospital_upgrade_costs`, fatigue keys), and stub/full RPCs per data-model (`apply_match_fatigue`, `process_post_match_injuries`, `process_daily_recovery`, `admit_to_hospital`, `discharge_from_hospital`)
- [x] T004 Extend `upgrade_club_facility` in the same migration (or adjacent section) to accept `'hospital'`, read `hospital_upgrade_costs`, charge via `apply_club_economy`, share `facility_last_upgrade_at` weekly cap, enforce match gates (5 career matches → L2, 20 → L4)
- [x] T005 Extend `supabase/scripts/verify_required_schema.sql` for new columns, `hospital_patients`, RPCs, and hospital facility key behavior guards
- [x] T006 [P] Export new modules from `packages/player_engine/player_engine/__init__.py` (placeholders OK until US1/US2 fill them)
- [x] T007 [P] Add hospital helpers/costs/label to `packages/economy/economy/facility_effects.py` and export from `packages/economy/economy/__init__.py` if needed

**Checkpoint**: Migration applies cleanly; verify script lists new objects; no Discord wiring yet

---

## Phase 3: User Story 1 — Per-Player Fatigue (Priority: P1) 🎯 MVP — SHIPPED

**Goal**: Competitive matches drain/recover card fatigue; NSS applies fatigue penalties; squad/profile show indicators; action energy untouched

**Independent Test**: Bot match lowers starter fatigue; bench gains ~15; profile/squad show fatigue; friendlies do not write fatigue; energy only changes by normal match spend

### Tests for User Story 1

- [x] T008 [P] [US1] Add `tests/test_fatigue_injury_math.py` covering drain formula example, penalty tier multipliers, bench/passive recovery caps, and assert fatigue helpers never reference action energy

### Implementation for User Story 1

- [x] T009 [P] [US1] Implement `packages/player_engine/player_engine/fatigue.py` (drain, `fatigue_stat_multiplier`, recovery constants mirroring `game_config` defaults)
- [x] T010 [US1] Extend `MatchPlayerCard` with `fatigue` in `packages/match_engine/match_engine/models.py` and hydrate in `apps/discord_bot/core/match_cards.py`
- [x] T011 [US1] Apply fatigue multiplier to phase attribute before 70/30 blend in `packages/match_engine/match_engine/phase_stats.py`
- [x] T012 [US1] Implement bot wrapper calling `apply_match_fatigue` in `apps/discord_bot/core/injury_rpc.py` (or `fatigue_rpc.py` if split) and invoke from `apps/discord_bot/core/match_rewards.py` after economy+XP for bot matches
- [x] T013 [US1] Invoke same fatigue apply from `apps/discord_bot/core/league_rewards.py` for league human rewards; skip friendlies in `apps/discord_bot/cogs/battle_cog.py`
- [x] T014 [US1] Compute per-starter drains in Python (tactic + intensity mods) before RPC; pass bench card ids for +15 rest
- [x] T015 [P] [US1] Add fatigue indicators to `apps/discord_bot/embeds/squad_embeds.py` and `/squad` flow in `apps/discord_bot/cogs/squad_cog.py`
- [x] T016 [P] [US1] Add fatigue bar to player profile in `apps/discord_bot/cogs/player_cog.py`
- [x] T017 [US1] Register daily job calling `process_daily_recovery` (fatigue portion) in `apps/discord_bot/main.py` / `apps/discord_bot/scheduler_jobs.py` (or existing scheduler module)
- [x] T018 [US1] Grep `apps/discord_bot/` to confirm fatigue writes never mutate `action_energy` / refill paths

**Checkpoint**: US1 shippable alone — fatigue drain/penalties/UI/recovery without injuries

---

## Phase 4: User Story 2 — Persistent Injuries (Priority: P2) — SHIPPED

**Goal**: Post-match injury rolls (A+C) persist on cards; injured blocked from XI/drills; expected return visible; roll 100 → Major

**Independent Test**: With a fatigued starter (&lt;75), post-match can injure at most one card; fresh squad (all ≥75) never injures; injured card blocked from drill/XI; profile shows tier + ETA

### Tests for User Story 2

- [x] T019 [P] [US2] Extend `tests/test_fatigue_injury_math.py` for injury chance, tier weights (100→Major), A+C eligibility (`fatigue >= 75` skipped), and max-one-injury selection helper

### Implementation for User Story 2

- [x] T020 [P] [US2] Implement `packages/player_engine/player_engine/injury_math.py` (chance, tiers, recovery days, A+C `select_post_match_injury(...)`)
- [x] T021 [US2] Wire post-match injury payload + `process_post_match_injuries` in `apps/discord_bot/core/injury_rpc.py`; call after fatigue from `match_rewards.py` / `league_rewards.py` (skip friendlies; skip RPC if empty)
- [x] T022 [US2] Block injured cards from starting XI in `apps/discord_bot/cogs/squad_cog.py` (and swap RPC pre-check messaging)
- [x] T023 [P] [US2] Block injured cards from drills (and evolution start if applicable) in `apps/discord_bot/cogs/development_cog.py`
- [x] T024 [P] [US2] Show injury badge + expected return on profile in `apps/discord_bot/cogs/player_cog.py` and squad embeds
- [x] T025 [US2] Ensure `process_daily_recovery` clears untreated injuries when days elapse; discharge hospital patients when due (RPC body completeness)
- [x] T026 [US2] Grep fusion/sell/agent paths; block or error clearly while injured/`in_hospital` in relevant cogs/RPCs
- [x] T027 [US2] Keep NSS cosmetic `INJURY` non-authoritative in `packages/match_engine/match_engine/v2_simulator.py` (optional rate trim); do not write card state from ticker alone

**Checkpoint**: US2 works with hospital_level 0 (1 bed) even before fancy Hospital UI

---

## Phase 5: User Story 3 — Hospital Facility (Priority: P2) — SHIPPED

**Goal**: Upgrade Hospital under Club Facilities; beds/recovery speed; auto-admit; overflow resolvable via DM or panel

**Independent Test**: Upgrade L0→L1 for 1,500 coins; admit on free bed; overflow prompts; weekly cap shared with YA/TG; match gates enforced

### Implementation for User Story 3

- [x] T028 [US3] Add Hospital card + upgrade UX to `apps/discord_bot/views/store_facilities.py` using `facility_effects` hospital costs/labels
- [x] T029 [P] [US3] Create `apps/discord_bot/embeds/hospital_embeds.py` (level, beds, patients, waiting list, upgrade line)
- [x] T030 [US3] Wire overflow follow-up after `process_post_match_injuries` (DM select + Hospital panel fallback) in `apps/discord_bot/core/injury_rpc.py` / battle reward callers
- [x] T031 [US3] Wire `admit_to_hospital` / `discharge_from_hospital` buttons/selects in Hospital panel views under `apps/discord_bot/views/`
- [x] T032 [P] [US3] Show hospital level on club finances if YA/TG shown in `apps/discord_bot/cogs/economy_cog.py`
- [x] T033 [US3] Confirm no new slash command; Hospital only via `/store` → Club Facilities (`apps/discord_bot/cogs/store_cog.py` copy only if needed)
- [x] T034 [US3] Verify upgrade uses `apply_club_economy` only (no direct coins UPDATE) via migration/RPC review

**Checkpoint**: Full Phase 1–2 loop: fatigue → injury (A+C) → hospital admit/overflow → daily recovery

---

## Phase 6: User Story 4 — In-Match Substitution UI (Priority: P3) 🎯 PHASE 3 ACTIVE

**Goal**: Authoritative mid-match injuries on live NSS; pause `async for` ≤30s with Select + Play On; mutate `MatchState` (Touchline pattern); auto-sim/AI auto-resolve; persist `recorded_injuries` without double-roll

**Independent Test**: Live bot injury before 90' shows prompt; sub/Play On/timeout/10-men/emergency GK work; auto-sim completes with no hang; post-match one injury persist; friendlies unchanged

**Prerequisites**: Phases 1–2 shipped (T001–T042). Plan: `plan-phase3.md`. Contract: `contracts/in-match-injury-sub.md`.

**⚠️ CRITICAL**: Do **not** use `generator.send()` / `asend()`. No new slash commands. No Hospital cost changes. No new migration unless RPC signature truly needs it (prefer Python-side `recorded_injuries` payload into existing `process_post_match_injuries`).

### Setup for Phase 3

- [x] T043 [US4] Review `specs/002-injury-fatigue-hospital/plan-phase3.md` + `contracts/in-match-injury-sub.md` against `TouchlineView` / live `async for` loops in `apps/discord_bot/cogs/battle_cog.py` and cosmetic `INJURY` yields in `packages/match_engine/match_engine/v2_simulator.py`

### Tests for User Story 4

- [x] T044 [P] [US4] Add `tests/test_match_substitution_resolve.py` covering `auto_pick_bench` (same-position preference then OVR), empty bench → None, `apply_sub` / `apply_ten_men`, `emergency_gk_card`, `play_on_tier_upgrade` (~60% +1 cap Major), and `auto_resolve_injury` decision matrix

### Pure resolve + MatchState

- [x] T045 [P] [US4] Implement `packages/match_engine/match_engine/substitution_resolve.py` with pure helpers from contract (`auto_pick_bench`, `apply_sub`, `apply_ten_men`, `emergency_gk_card`, `play_on_tier_upgrade`, `auto_resolve_injury`); export from `packages/match_engine/match_engine/__init__.py` and/or `packages/match_engine/__init__.py`
- [x] T046 [US4] Extend `MatchState` in `packages/match_engine/match_engine/v2_simulator.py` with serializable fields: `bench_home`/`bench_away`, `subs_used_home`/`subs_used_away`, `pending_injuries`, `recorded_injuries`, `compromised_card_ids`, `sub_resolution` (document that `asyncio.Event` lives as a Discord-attached sidecar attribute, not a Pydantic field)
- [x] T047 [US4] Apply Play On / compromised multiplier (×0.50) in `packages/match_engine/match_engine/phase_stats.py` (or squad contrib path) when card id is in `compromised_card_ids`
- [x] T048 [US4] Add mid-match A+C roll helper (reuse `player_engine.injury_math`) and wire into `packages/match_engine/match_engine/v2_simulator.py`: queue pending on hit; at stoppage (`FOUL`/`GOAL`/`SAVE`/`HALF_TIME`/set-piece end) yield rich interactive `INJURY` payload per contract; minute ≥90 → record only, `interactive=false`; remove/replace non-authoritative cosmetic injury RNG for competitive path
- [x] T049 [US4] In `stream_match` loop, apply `sub_resolution` between iterations (swap squad/bench, 10-men, emergency GK flags, append `recorded_injuries`, bump `subs_used_*`) mirroring how `home_tactics_modifier` is read live

### Discord UI + live pause

- [x] T050 [US4] Create `apps/discord_bot/views/match_injury_prompt.py` — `InjurySubView` with bench Select + Play On, `timeout=30`, `interaction_check` for injured-side manager only, writes `sub_resolution` + sets sidecar `sub_wait_event` (non-persistent view; no `bot.add_view`)
- [x] T051 [US4] Hydrate benches at kickoff via `fetch_bench_ids` + card hydration; attach benches + `asyncio.Event` sidecar onto `MatchState` before `stream_match` in bot-battle and live-league paths in `apps/discord_bot/cogs/battle_cog.py`
- [x] T052 [US4] In bot-battle live `async for` in `apps/discord_bot/cogs/battle_cog.py`: on interactive human-side `INJURY`, post `InjurySubView`, `await asyncio.wait_for(event.wait(), 30)`, on timeout call pure auto-pick/10-men, write resolution, continue loop — **never** `send()`/`asend()`
- [x] T053 [US4] Mirror T052 for live human league stream loop(s) in `apps/discord_bot/cogs/battle_cog.py` (and `league_cog.py` only if it owns a live stream); prompt only injured side’s manager; other side sees commentary only
- [x] T054 [US4] AI / bot-opponent injuries: call `auto_resolve_injury` immediately (no Discord wait) in the same consumer paths
- [x] T055 [US4] Wire auto-sim / `collect_match_events` path (league silent + any `battle_cog` silent branch) to auto-resolve pending injuries inline with no UI hang

### Post-match persistence (no double-roll)

- [x] T056 [US4] Extend `apply_post_match_fitness` in `apps/discord_bot/core/injury_rpc.py` to accept `recorded_injuries`; when non-empty, pass to `process_post_match_injuries` and **skip** `select_post_match_injury` re-roll; when empty, keep Phase 2 post-match roll (compat)
- [x] T057 [US4] Pass `state.recorded_injuries` from bot/league reward callers in `apps/discord_bot/core/match_rewards.py` and `apps/discord_bot/core/league_rewards.py` (and battle_cog reward sites that call fitness directly); apply Play On tier-upgrade at persist time via `play_on_tier_upgrade`
- [x] T058 [US4] Confirm friendlies still skip fatigue/injury/sub prompts in `apps/discord_bot/cogs/battle_cog.py`

### Commentary + polish

- [x] T059 [P] [US4] Add commentary/context tags for `substitution`, `played_through_injury`, `down_to_ten_men`, `emergency_goalkeeper` in event rendering paths used by `apps/discord_bot/cogs/battle_cog.py` (and league live renderer if separate)
- [x] T060 [P] [US4] Update `change_log.md` with Phase 3 in-match injury stoppage / sub UX (player-facing)
- [x] T061 [US4] Run `pytest tests/test_match_substitution_resolve.py tests/test_fatigue_injury_math.py -q` and fix failures; grep to confirm zero `generator.send` / `asend` introductions
- [x] T062 [US4] Walk `specs/002-injury-fatigue-hospital/quickstart.md` §7 Phase 3 scenarios; mark gaps; reconcile US4 notes in `.specify/specs/v1.0.0/spec.md` / `plan.md` if behavior diverges

**Checkpoint**: Live human match can pause ≤30s for sub; auto-sim never hangs; one authoritative injury persist; Phases 1–2 Hospital/fatigue unchanged

---

## Phase 7: Polish & Cross-Cutting Concerns — SHIPPED (Phases 1–2)

**Purpose**: Verify, SDD, player copy, cleanup for Phases 1–2

- [x] T035 [US4] Document Phase 3 follow-up in plan / change_log “Coming later” — **superseded by Phase 6 Active (T043–T062)**
- [x] T036 [P] Update `change_log.md` with fatigue, injury (A+C), and Hospital facility player-facing notes
- [x] T037 [P] Reconcile feature into `.specify/specs/v1.0.0/spec.md` and `.specify/specs/v1.0.0/plan.md`
- [x] T038 Run `pytest tests/test_fatigue_injury_math.py -q` (and any extended match/economy tests touched) and fix failures
- [x] T039 Apply migration via `scratch/apply_migration_050.py` (create scratch script from existing pattern) and run `python scratch/verify_schema_full.py` or verify SQL
- [x] T040 Walk `specs/002-injury-fatigue-hospital/quickstart.md` Phase 1 then Phase 2 scenarios; note gaps
- [x] T041 Grep for GDD hallucinations (`clubs.coins`, `generator.send`, `/hospital` command, 100000 hospital cost) and remove any accidental introductions
- [x] T042 Remove temporary debug instrumentation from touched cogs/helpers

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup / Foundational / US1–US3 / Polish T035–T042**: **DONE**
- **US4 Phase 3 (T043–T062)**: After Phases 1–2 — **next implement target**
  - T043 → T044∥T045 → T046 → T047∥T048 → T049 → T050 → T051 → T052∥T053 → T054∥T055 → T056 → T057 → T058 → T059∥T060 → T061 → T062

### User Story Dependencies

```text
Foundational (050) ✅
    → US1 Fatigue ✅
        → US2 Injuries (A+C) ✅
            → US3 Hospital ✅
                → US4 In-match subs (Phase 3) ← ACTIVE
```

### Parallel Opportunities (Phase 3)

- T044 ∥ T045 (tests + pure module)
- T047 ∥ T048 after MatchState fields exist (T046)
- T052 ∥ T053 (bot vs league live loops) after T050–T051
- T054 ∥ T055 (AI auto vs collect_match_events)
- T059 ∥ T060 (commentary tags vs change_log)

### Parallel Example: User Story 4

```bash
# After T043 review:
Task: "tests/test_match_substitution_resolve.py"
Task: "packages/match_engine/.../substitution_resolve.py"
# Then MatchState + simulator, then Discord view, then wire both live loops:
Task: "battle_cog bot-battle injury pause"
Task: "battle_cog league live injury pause"
```

---

## Implementation Strategy

### Phases 1–2 (complete)

1. Fatigue MVP → injuries A+C → Hospital — **shipped**

### Phase 3 (US4) — next

1. Pure resolve + tests (T044–T045)
2. Authoritative mid-match injury + MatchState (T046–T049)
3. Discord pause UI + live loops (T050–T055)
4. Persist recordings without double-roll (T056–T058)
5. Commentary, change_log, pytest, quickstart §7 (T059–T062)
6. **STOP** — validate live prompt + auto-sim no-hang before further balance tweaks

### Economy safety (do not regress)

- No admit/treatment coin fee  
- Hospital costs stay 1.5k–60k + weekly shared cap + match gates  
- A+C eligibility still gates mid-match rolls  
- No energy/fatigue cross-spend  
- Phase 3 adds **no** new coin faucet/sink  

---

## Notes

- [P] = different files, no incomplete-task dependency
- Exact paths required in every task
- Phase 3: **no** `generator.send()`; pause = `asyncio.wait_for` on sidecar Event
- Phase 3: no new slash command; no Hospital ladder changes
- Ponytail: reuse `TouchlineView` mutation pattern + existing `fetch_bench_ids`
- Commit only when user requests
