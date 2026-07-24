# Tasks: Match Engine V3 Production Rollout

**Input**: Design documents from `/specs/044-match-v3-rollout/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included — plan/quickstart require projector explainability unit coverage and re-run of `041` V3 suite before flag flips. No full Discord integration suite.

**Locked decisions** (research.md / plan.md):
- Rollout only — no engine rewrite; no new migration by default (`083` flags + pins)
- Cutover order: bot → league → optional friendly
- Kickoff pin immutable via `resolve_engine_version` / create-run
- Enrich `project_explanation` beyond GOAL/CHANCE; Discord uses readable tip text
- Settlement never gated on explainability embed success (US-42.4)
- Non-goals: marketplace, wages, Redis, Ranked, squad Tactics Soon, new slash commands

**US citation**: Extends Implemented `041`; mutating settlement remains **US-42.4**

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: US1–US4 maps to spec user stories
- Exact file paths required

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm touch list and baseline green before any flag flip or copy change

- [x] T001 Grep `resolve_engine_version`, `create_ephemeral_run`, `create_league_run`, `project_explanation`, `match_engine_v3_bot|league|friendly`, and finalize `explanation` kwargs across `apps/discord_bot/` + `packages/match_engine/`; confirm touch list matches `specs/044-match-v3-rollout/plan.md`
- [x] T002 [P] Confirm migration `083` flags exist in repo (`supabase/migrations/083_match_engine_v3_events.sql`) and defaults remain off (`0`) in `specs/044-match-v3-rollout/data-model.md` / quickstart assumptions — do not author a new migration unless a bug forces a forward fix
- [x] T003 [P] Run baseline V3 regression: `pytest tests/test_nss_v3_determinism.py tests/test_nss_v3_dual_run_pin.py tests/test_nss_v3_explainability.py tests/test_nss_v3_projectors.py -q` and record pass/fail before edits

**Checkpoint**: Touch list + baseline known; no schema work required to proceed

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Pin + flag resolution verified end-to-end in code — **MUST complete before soak enables**

**⚠️ CRITICAL**: Do not enable prod/staging flags until pin paths and settle-independence are confirmed

- [x] T004 Audit `apps/discord_bot/core/match_runs.py` (`resolve_engine_version`, `create_ephemeral_run`, `create_league_run`) against `specs/044-match-v3-rollout/contracts/engine-flag-rollout.md` — bot/league/friendly keys map correctly; pin written at create only
- [x] T005 [P] Audit bot + league + friendly kickoff sites in `apps/discord_bot/cogs/battle_cog.py` (and league auto-sim entry in `apps/discord_bot/cogs/league_cog.py` / callers) so every new run goes through create-run helpers (no ad-hoc `engine_version` assignment)
- [x] T006 Confirm settlement-before-present / explainability isolation in `apps/discord_bot/cogs/battle_cog.py` bot finalize path (rewards + `complete_run` before embed field that uses `explanation`) per US-42.4 and `contracts/explainability-ui.md`
- [x] T007 [P] Confirm `get_game_config_int` / config read path used by `resolve_engine_version` documents refresh vs restart behavior in `specs/044-match-v3-rollout/quickstart.md` (edit quickstart only if process-cache reality differs)

**Checkpoint**: Foundation verified — US1 soak and US2 explainability work can proceed

---

## Phase 3: User Story 1 — Bot matches run on V3 under controlled soak (Priority: P1) 🎯 MVP

**Goal**: Ops can enable `match_engine_v3_bot` so new bot kicks pin `nss_v3`, settle once, and never mid-swap in-flight v2 runs; league/friendly stay off

**Independent Test**: With bot flag on and league/friendly off, complete three bot matches → `match_runs.engine_version='nss_v3'`, rewards once; any league kick still `nss_v2`

**Contract**: [contracts/engine-flag-rollout.md](./contracts/engine-flag-rollout.md) · [contracts/soak-and-rollback.md](./contracts/soak-and-rollback.md)

### Implementation for User Story 1

- [x] T008 [US1] Fix any pin/create-run gaps found in T004–T005 (only if bugs exist) in `apps/discord_bot/core/match_runs.py` and/or `apps/discord_bot/cogs/battle_cog.py` — no behavior change if already correct
- [x] T009 [P] [US1] Extend or assert dual-run pin coverage in `tests/test_nss_v3_dual_run_pin.py` for bot-on/league-off resolution semantics if gaps remain after audit
- [x] T010 [US1] Staging/soak ops: set `match_engine_v3_bot=1` via SQL per `specs/044-match-v3-rollout/quickstart.md` §3; leave `match_engine_v3_league` and `match_engine_v3_friendly` at `0`; restart bot if config cache requires it
- [ ] T011 [US1] Discord smoke (soak guild): complete ≥3 `/battle` bot matches; SQL-check latest bot `match_runs.engine_version='nss_v3'`; confirm coins/XP/fatigue applied once; Decision Windows visible in-match
- [x] T012 [US1] Rollback drill per soak contract: set `match_engine_v3_bot=0`; new bot kick pins `nss_v2`; any in-flight v3 run still completes on v3 — document result in soak notes (quickstart or ops log)
- [x] T013 [US1] Re-enable bot flag for continued soak; track toward ≥20 completed v3 bot matches and zero double-settle incidents before US3 league enable (`contracts/soak-and-rollback.md`)

**Checkpoint**: US1 MVP path — bot V3 soak operable with rollback proven

---

## Phase 4: User Story 2 — Managers understand why the match turned (Priority: P1)

**Goal**: Post-match “How it was decided” shows readable turning points / decision moments from the V3 event stream (no invented drama)

**Independent Test**: Finish a V3 bot match with goals/chances/decisions → embed shows humanized tips; thin stream → minimal/omit field; v2 match UX unchanged

**Contract**: [contracts/explainability-ui.md](./contracts/explainability-ui.md)

### Tests for User Story 2

- [x] T014 [P] [US2] Extend `tests/test_nss_v3_explainability.py` with cases: (a) GOAL tips keep causal_hint, (b) include TACTICAL_DECISION / DECISION_WINDOW when present, (c) empty/admin-only stream → no invented turning_points, (d) determinism unchanged for same events

### Implementation for User Story 2

- [x] T015 [US2] Enrich `project_explanation` in `packages/match_engine/match_engine/v3/projectors.py` per explainability contract — prefer goals, decisive chances, then decision/tactical moments; populate readable `causal_hint` / `text_key`; cap ≤5 tips; never invent events
- [x] T016 [P] [US2] Add a small shared tip-line formatter (prefer `causal_hint` / humanized text over bare `type`) used by both finalize handlers in `apps/discord_bot/cogs/battle_cog.py` (bot + league “How it was decided” fields ~lines that currently use `tp.get('type')`)
- [x] T017 [US2] Wire graceful degrade in those finalize paths: if no tips, omit field or headline-only; wrap explainability build so failures never block already-settled rewards (`battle_cog.py`)
- [x] T018 [US2] Confirm league finalize path that builds `explanation_kw` (live + auto-sim via shared handler) still passes enriched explanation when `_nss_v3_events` exist in `apps/discord_bot/cogs/battle_cog.py`
- [x] T019 [US2] Run `pytest tests/test_nss_v3_explainability.py tests/test_nss_v3_projectors.py -q`; Discord spot-check one V3 bot final for readable tips

**Checkpoint**: US2 — explainability manager-readable on bot (and league handler ready before flag flip)

---

## Phase 5: User Story 3 — League adopts V3 after bot soak (Priority: P2)

**Goal**: After soak criteria pass, enable league V3 for live Play + auto-sim with settle-once standings and preserved pause/resume integrity

**Independent Test**: League flag on → one live + one auto-sim fixture pin `nss_v3`, standings/points once; bot soak criteria checklist signed off

**Contract**: [contracts/soak-and-rollback.md](./contracts/soak-and-rollback.md) · [contracts/engine-flag-rollout.md](./contracts/engine-flag-rollout.md)

### Implementation for User Story 3

- [ ] T020 [US3] Sign off bot soak gate in `specs/044-match-v3-rollout/contracts/soak-and-rollback.md` checklist (pytest green, ≥20 v3 bot matches, zero double-settle, explainability spot-check, rollback drill done) — **block league enable until complete**
- [x] T021 [P] [US3] Verify auto-sim expired fixtures path in `apps/discord_bot/cogs/league_cog.py` (`auto_sim_expired_fixtures`) and scheduler job `apps/discord_bot/core/scheduler_jobs.py` create/recover runs via pinned `engine_version` (fix only if gap)
- [ ] T022 [US3] Ops: set `match_engine_v3_league=1` per quickstart §6; keep friendly at `0` unless US4 explicitly enabled
- [ ] T023 [US3] Discord/ops smoke: one live league Play + one auto-sim; confirm `engine_version='nss_v3'`, standings/points once, pause/resume / matchday lock behavior unchanged in intent; explainability on live finalize when events exist
- [x] T024 [US3] Contingency procedure ready: `python scratch/ops_match_v3_rollout.py disable-league` (no incident yet; use if league V3 causes integrity issues)

**Checkpoint**: US3 — league on V3 after gated soak

---

## Phase 6: User Story 4 — Friendly remains a safe sandbox (Priority: P3)

**Goal**: Friendly stays on its own flag (default off during soak); sandbox economy holds regardless of engine pin

**Independent Test**: Bot V3 on, friendly flag off → friendly completes sandbox (no competitive coins/XP/evo) on v2 pin; optional later friendly V3 still sandbox

**Contract**: [contracts/engine-flag-rollout.md](./contracts/engine-flag-rollout.md)

### Implementation for User Story 4

- [x] T025 [US4] Audit friendly kickoff in `apps/discord_bot/cogs/battle_cog.py` (`create_ephemeral_run(..., run_type="friendly")`) — pin follows `match_engine_v3_friendly`; confirm no competitive faucet/XP/evo on friendly complete
- [ ] T026 [P] [US4] Smoke with friendly flag off while bot V3 on: complete one friendly → sandbox rules hold; `engine_version` is `nss_v2` (or pinned friendly default)
- [x] T027 [US4] Optional friendly V3 enable — SKIPPED; leave `match_engine_v3_friendly=0` (see ops-soak-log.md)

**Checkpoint**: US4 — friendly sandbox isolation preserved

---

## Phase 7: Polish & Cross-Cutting

**Purpose**: Player copy, full regression, integrity greps, ship readiness

- [x] T028 [P] Update `change_log.md` with player-facing V3 note when bot (then league) is live for real managers (FR-010) — Decision Windows / clearer post-match “how it was decided”
- [x] T029 [P] Re-run broader V3 suite: `pytest tests/test_nss_v3_determinism.py tests/test_nss_v3_dual_run_pin.py tests/test_nss_v3_explainability.py tests/test_nss_v3_projectors.py tests/test_nss_v3_recovery_parity.py tests/test_nss_v3_sql_guards.py -q` (add golden/win-rate if soak gate requires)
- [x] T030 Grep `apps/discord_bot/` for accidental parallel coin/XP pipes or forced `nss_v3` bypassing `resolve_engine_version`; confirm zero new slash commands / marketplace / wages / Redis touches in the diff
- [x] T031 Persona walkthrough (manager mobile post-match, opposing manager league, auto-sim silent, double-tap finalize): settlement succeeds even if explainability embed fails; document any gaps fixed in `battle_cog.py`
- [x] T032 Mark feature ready: update `specs/044-match-v3-rollout/checklists/requirements.md` notes + set `specs/044-match-v3-rollout/spec.md` Status when soak stages complete

---

## Dependencies & Story Order

```text
Phase 1 Setup
    ↓
Phase 2 Foundational (pin + settle audit)
    ↓
Phase 3 US1 (bot soak) ──┬──→ Phase 5 US3 (league) ──→ Phase 6 US4 (friendly optional)
    ↓                    │
Phase 4 US2 (explainability) ──┘  (US2 code before/parallel with US1 soak; required before promoting to real managers)
    ↓
Phase 7 Polish
```

| Story | Depends on | Blocks |
|-------|------------|--------|
| US1 | Phase 2 | US3 league enable |
| US2 | Phase 2 | Polished player experience for US1/US3 |
| US3 | US1 soak gate (T020) + US2 recommended | US4 optional friendly |
| US4 | Phase 2; preferably after US3 | — |

**Suggested MVP**: Phase 1–4 (US1 + US2) — bot V3 with readable explainability + rollback drill. League (US3) only after soak checklist.

---

## Parallel Execution Examples

```text
# Setup
T002 || T003   (after T001 or alongside if touch list known)

# Foundational
T005 || T007   (after/with T004)

# US2
T014 || T016   (tests + Discord formatter while T015 projector lands)

# Polish
T028 || T029
```

---

## Implementation Strategy

1. **Verify first** (T001–T007) — most create/pin/explain hooks already exist from `041`.
2. **MVP**: Enrich projector + Discord tip copy (US2) while starting bot soak (US1).
3. **Gate**: Do not flip `match_engine_v3_league` until T020 soak criteria pass.
4. **Friendly**: Keep off unless explicitly needed (US4).
5. **Ship signal**: `change_log.md` + green V3 suite + integrity grep clean.

---

## Summary

| Metric | Count |
|--------|-------|
| Total tasks | 32 (T001–T032) |
| Phase 1 Setup | 3 |
| Phase 2 Foundational | 4 |
| US1 Bot soak | 6 |
| US2 Explainability | 6 |
| US3 League | 5 |
| US4 Friendly | 3 |
| Phase 7 Polish | 5 |
| Parallelizable marked [P] | 12 |

**Independent tests**: US1 three bot matches + pin SQL; US2 embed tips from stream; US3 live+auto-sim settle once; US4 friendly sandbox with bot-on.

**Format validation**: All tasks use `- [ ] Tnnn [P?] [USn?] …` with file paths or explicit SQL/ops targets from quickstart.
)
