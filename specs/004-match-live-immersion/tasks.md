# Tasks: Match Live Immersion Fixes

**Input**: Design documents from `/specs/004-match-live-immersion/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included — plan/quickstart require pytest for bot squad identity, probability floor, and batch possession sanity (`tests/test_bot_match_squad.py`, `tests/test_probability_floor.py`, extend `tests/test_nss_win_rates.py`). Discord live UX validated via quickstart.

**Organization**: Tasks grouped by user story (US1–US4) for incremental delivery.

**Locked decisions** (from research.md):
- Goal Scroll = Discord handler presentation only (not `MatchState`)
- HALF_TIME already yielded by sim — ticker line becomes `--- HALF TIME ---` separator (no second inject)
- Bot names = fix `battle_cog` stub squads via `build_bot_match_squad()`; yields already use `_get_name`
- Floor = lock `_probability_floor` at `0.05`; remove large-gap `0.02` branch
- No migrations, no new slash commands, no Markov rewrite

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 / US2 / US3 / US4
- Include exact file paths in descriptions

## Path Conventions

- Pure engine: `packages/match_engine/match_engine/`
- Bot UI: `apps/discord_bot/cogs/battle_cog.py`
- Tests: `tests/` at repo root
- SDD: `.specify/specs/v1.0.0/`
- Feature docs: `specs/004-match-live-immersion/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm scope and call sites before code

- [x] T001 Review `specs/004-match-live-immersion/plan.md` against `contracts/live-embed-layout.md`, `contracts/bot-squad-identity.md`, and `contracts/transition-probability-floor.md`; note any drift in `specs/004-match-live-immersion/research.md` if found
- [x] T002 [P] Grep `apps/discord_bot/` and `packages/` for `Opponent Striker`, `Opponent Midfielder`, `Opponent Defender`, and all `update_ticker(` call sites; list exact line locations for US1–US3 wiring (expect stubs only in `battle_cog.py`)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared live-embed contract and ticker helpers that US1/US2 both need

**⚠️ CRITICAL**: Do not ship Goal Scroll / half-time consumer wiring until the handler signature and layout order exist

- [x] T003 Extend `IMatchOutputHandler.update_ticker` in `apps/discord_bot/cogs/battle_cog.py` to accept `goal_scroll: list[str] | None = None` (or required `list[str]`); update abstract signature and both concrete handlers
- [x] T004 Update `StandardMatchHandler.start_match` / `update_ticker` and `LeagueMatchHandler.start_match` / `update_ticker` in `apps/discord_bot/cogs/battle_cog.py` so embed field order is Scoreboard → Goal Scroll (omit if empty) → Momentum → Commentary Ticker per `contracts/live-embed-layout.md`
- [x] T005 [P] Add pure helpers in `apps/discord_bot/cogs/battle_cog.py` (module-level): `format_goal_scroll_line(minute, actor) -> str` and `format_ticker_line(ev_type, minute, text) -> str` where `HALF_TIME` returns the fixed separator `⏸️ **--- HALF TIME ---**` (other types keep emoji + minute + text)

**Checkpoint**: Handlers accept/render Goal Scroll; helpers ready; live match behavior unchanged until consumers pass scroll + use helpers

---

## Phase 3: User Story 1 — Persistent Goal Scroll (Priority: P1) 🎯 MVP

**Goal**: Early goals stay visible under the scoreboard while the 5-line ticker rolls

**Independent Test**: Live match with 3+ goals (one before 60'); after ticker advances, Goal Scroll still lists each `⚽ m' Name`

### Tests for User Story 1

- [x] T006 [P] [US1] Add unit coverage in `tests/test_live_match_ticker.py` (new) for `format_goal_scroll_line` and a tiny “append + cap at 10” helper behavior (oldest drops first; empty list means omit)

### Implementation for User Story 1

- [x] T007 [US1] In league `_consume_event` inside `apps/discord_bot/cogs/battle_cog.py`, maintain `goal_scroll: list[str]`; on `GOAL` append via `format_goal_scroll_line`; keep `goal_scroll[-10:]`; pass into every `handler.update_ticker(...)`
- [x] T008 [US1] In the bot-match live loop in `apps/discord_bot/cogs/battle_cog.py`, same Goal Scroll accumulation and `update_ticker(..., goal_scroll=...)` wiring as T007
- [x] T009 [US1] Grep `apps/discord_bot/cogs/battle_cog.py` for any other live `update_ticker` / ticker_history loops (friendly or legacy); wire Goal Scroll the same way or document as unused dead path in a one-line comment only if truly unreachable

**Checkpoint**: US1 shippable alone — ghost-match fixed even if bot names/floor unchanged

---

## Phase 4: User Story 2 — Half-Time Marker in the Ticker (Priority: P1)

**Goal**: Managers see a clear half-time break in the live ticker at ~45'

**Independent Test**: Watch live match through 45'; ticker shows `--- HALF TIME ---` once; no duplicate markers

### Implementation for User Story 2

- [x] T010 [US2] Switch league `_consume_event` ticker append in `apps/discord_bot/cogs/battle_cog.py` to `format_ticker_line(ev["type"], ev["minute"], text)` so HALF_TIME uses the separator (do not double-yield half-time from UI)
- [x] T011 [US2] Switch bot-match live loop ticker append in `apps/discord_bot/cogs/battle_cog.py` to the same `format_ticker_line` path as T010
- [x] T012 [P] [US2] Extend `tests/test_live_match_ticker.py` to assert `format_ticker_line("HALF_TIME", 45, anything)` contains `--- HALF TIME ---` and non-HALF_TIME types still include minute + text

**Checkpoint**: US1 + US2 — Goal Scroll + half-time separator on all standard live handlers

---

## Phase 5: User Story 3 — Real Bot Player Names (Priority: P1)

**Goal**: Bot/AI opponents use generated roster names, never `Opponent Striker`-style stubs

**Independent Test**: Bot match chance/goal commentary and Goal Scroll show human-like names; grep finds zero stub card names

### Tests for User Story 3

- [x] T013 [P] [US3] Create `tests/test_bot_match_squad.py` asserting `build_bot_match_squad` returns 11 cards, unique-ish names, no `Opponent Striker|Midfielder|Defender`, zone coverage (GK/DEF/MID/FWD), overall near target, secondary attrs near overall, and same seed → same squad

### Implementation for User Story 3

- [x] T014 [US3] Implement `build_bot_match_squad(target_ovr: int, rng: random.Random) -> list[MatchPlayerCard]` in `packages/match_engine/match_engine/bot_squad.py` per `contracts/bot-squad-identity.md` (4-4-2 blueprint; load names from gacha `player_names.json` without importing full pack generator if possible)
- [x] T015 [US3] Export `build_bot_match_squad` from `packages/match_engine/match_engine/__init__.py`
- [x] T016 [US3] Replace bot-match `opp_squad` three-card stubs in `apps/discord_bot/cogs/battle_cog.py` with `build_bot_match_squad(int(opp_rating), match_rng)` (or equivalent seeded rng)
- [x] T017 [US3] Replace league AI home/away three-card stubs in `apps/discord_bot/cogs/battle_cog.py` with `build_bot_match_squad(...)` using each side’s `ai_rating` and the match rng
- [x] T018 [US3] Grep repo for `Opponent Striker`, `Opponent Midfielder`, `Opponent Defender` used as card names; confirm **zero** remain (update any leftover call sites)

**Checkpoint**: US3 independent — named bots even without Goal Scroll if tested via event actors alone

---

## Phase 6: User Story 4 — No Total Possession Snowball (Priority: P2)

**Goal**: Contested transitions never collapse below ~5%; post-match possession is not exact 0–100 for valid XIs

**Independent Test**: `pytest` floor unit + ≥20 seeded full sims with valid XIs show no exact 0–100 possession; favorites still win majority when mismatched

### Tests for User Story 4

- [x] T019 [P] [US4] Create `tests/test_probability_floor.py` asserting `_probability_floor` always returns `0.05` for both small and large stat gaps (no `0.02` branch)
- [x] T020 [P] [US4] Extend `tests/test_nss_win_rates.py` (or add adjacent test) with a batch of ≥20 full `stream_match`/`collect_match_events` runs using valid 11-a-side squads: assert zero exact `0/100` possession splits; assert heavily favored side still wins a clear majority

### Implementation for User Story 4

- [x] T021 [US4] In `packages/match_engine/match_engine/v2_simulator.py`, change `_probability_floor` to always return `0.05` and delete the large-gap `0.02` branch per `contracts/transition-probability-floor.md`; leave Markov phases / stagnation / momentum decay unchanged
- [x] T022 [US4] Run `pytest tests/test_probability_floor.py tests/test_nss_win_rates.py tests/test_bot_match_squad.py -q` and fix any regressions without softening the floor below 5%

**Checkpoint**: US4 complete — stats feel fair; favorites still dominate mismatches

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Ship hygiene across all stories

- [x] T023 [P] Update player-facing note in `change_log.md` for Goal Scroll, named bot XIs, and fairer possession
- [x] T024 [P] Reconcile live-match immersion behavior into `.specify/specs/v1.0.0/spec.md` and `.specify/specs/v1.0.0/plan.md` (SDD single source of truth)
- [x] T025 Run through `specs/004-match-live-immersion/quickstart.md` checklist (unit + one Discord bot match smoke for Goal Scroll / half-time / bot names / possession)
- [x] T026 Confirm no new slash commands, hubs, tables, or migrations were added; confirm `packages/` has no new `discord` imports

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS US1 and US2** (handler signature + helpers)
- **US1 (Phase 3)**: Depends on Phase 2
- **US2 (Phase 4)**: Depends on Phase 2 (ideally after US1 helpers exist; can follow US1 in same files)
- **US3 (Phase 5)**: Independent of Phase 2 UI work — can start after Setup in parallel with Phase 2/US1 if staffed (different files: `bot_squad.py` vs `battle_cog` handlers). Stub replacement in `battle_cog` should land after or carefully merge with US1/US2 edits
- **US4 (Phase 6)**: Independent — `v2_simulator.py` only; parallel with US1–US3 after Setup
- **Polish (Phase 7)**: After desired stories complete

### User Story Dependencies

| Story | Depends on | Notes |
|-------|------------|-------|
| US1 Goal Scroll | Phase 2 | MVP |
| US2 Half-time | Phase 2 (+ T005 helper) | Same consumer loops as US1 |
| US3 Bot names | Setup (T002) | Pure engine first; battle_cog replace last |
| US4 Floor | Setup | Fully independent package change |

### Parallel Opportunities

```text
After T002:
  → T014–T015 + T013 (US3 engine+tests)  ||  T003–T005 (foundation)  ||  T019+T021 (US4 floor)
After Phase 2:
  → T006–T009 (US1) then T010–T012 (US2)  [same file — sequential preferred]
After US3 engine ready:
  → T016–T018 (wire battle_cog) once US1/US2 consumer edits settle
```

### Parallel Example: US3 + US4

```bash
# Different packages/files — safe in parallel after Setup:
Task: "Implement build_bot_match_squad in packages/match_engine/match_engine/bot_squad.py"
Task: "Lock _probability_floor at 0.05 in packages/match_engine/match_engine/v2_simulator.py"
Task: "Create tests/test_bot_match_squad.py"
Task: "Create tests/test_probability_floor.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 Setup  
2. Phase 2 Foundational  
3. Phase 3 US1 Goal Scroll  
4. **STOP and VALIDATE** — ghost-match fixed in Discord  
5. Demo / ship MVP if needed  

### Incremental Delivery

1. Setup + Foundational → handler contract ready  
2. US1 Goal Scroll → validate ghost-match fix (MVP)  
3. US2 Half-time → validate separator  
4. US3 Bot names → validate no stub actors  
5. US4 Floor → validate possession batch  
6. Polish → changelog + SDD + quickstart  

### Suggested MVP Scope

**US1 only** (Goal Scroll) — highest immersion win for the reported `0–4` with missing early goals. US2 is a small follow-on in the same loops; US3/US4 are independent package/UI fixes.

---

## Notes

- [P] = different files, no incomplete-task dependencies  
- Do **not** rewrite ATTACK/SCORING_OPP yields for names — fix squad construction  
- Do **not** inject a second HALF_TIME event from the UI  
- Do **not** soft-clamp displayed possession without changing `_roll_chance`  
- Commit after each story checkpoint when asked; avoid drive-by refactors outside listed files  
