# Implementation Plan: Phase 3 — In-Match Injury Substitution UI

**Branch**: `002-injury-fatigue-hospital` (Phase 3 addendum) | **Date**: 2026-07-11  
**Spec**: [spec.md](./spec.md) US4 / FR-013 / FR-014 / SC-008  
**Depends on**: Phases 1–2 shipped (fatigue, post-match injury, Hospital)

**Input**: User request to plan Phase 3 in-match substitution UI

## Summary

Make mid-match injuries **authoritative** on the live NSS stream: at a natural stoppage, pause Discord consumption of `async for`, show a 30s Select Menu (+ Play On), apply the choice by mutating shared `MatchState` / squad lists (same pattern as `TouchlineView`), then resume. Auto-sim and AI sides auto-resolve without UI. Persist in-match injuries post-match **without a second A+C roll**.

**Non-goals**: `generator.send()` / `asend()`; new slash commands; career-ending; friendlies; changing Hospital economy.

## Technical Context

**Language/Version**: Python 3.11+  

**Primary Dependencies**: discord.py ≥2.7, NSS `stream_match` / `MatchState`, existing `player_engine.injury_math` (A+C), `fetch_bench_ids`

**Storage**: No new tables required. Reuse `process_post_match_injuries` with injuries collected during the match. Optional: store `subs_used` only in match memory.

**Testing**: pytest for pure sub/auto-pick/Play On / 10-men helpers; Discord path via quickstart manual + optional unit test of decision resolver

**Target Platform**: Discord bot match threads (bot battle + human league); silent auto-sim

**Project Type**: Monorepo — `packages/match_engine` + `apps/discord_bot`

**Performance Goals**: Sub decision ≤30s wall clock; match thread must not hang past timeout; auto-sim adds negligible delay

**Constraints**: No `discord` in packages; packages stay pure; mutate `MatchState` like tactics; A+C soft-cap still applies to *who* can be injured mid-match; max **3** subs/match; bench ≤7; minute ≥90 → no prompt

**Scale/Scope**: Isolated PR; ~8–12 files; highest Discord risk area

## Constitution Check

| Gate | Status | Notes |
|------|--------|-------|
| I. Monorepo boundary | PASS | Engine pure; UI in `battle_cog` / new view module |
| II. RPC mutations | PASS | Persist via existing injury RPCs post-match |
| III. Pydantic boundaries | PASS | Extend event dict / optional small models |
| IV. Defer / interactions | PASS | Injury view responds within 3s; match already deferred |
| V. APScheduler | N/A | No new jobs |
| VI. Errors | PASS | Timeout → auto-pick; empty bench → 10-men / emergency GK |
| VII. YAGNI | PASS | No send(); reuse Touchline mutation pattern |

## Project Structure

```text
specs/002-injury-fatigue-hospital/
├── plan-phase3.md              # This file
├── contracts/in-match-injury-sub.md
├── research.md                 # + Phase 3 decisions
├── data-model.md               # + MatchState sub fields
└── quickstart.md               # + Phase 3 scenarios

packages/match_engine/match_engine/
├── v2_simulator.py             # Authoritative injury + stoppage yield; squad mutate hooks
├── models.py                   # Optional richer INJURY payload fields on events
└── substitution_resolve.py     # NEW pure: auto-pick, emergency GK, Play On flags

packages/player_engine/player_engine/
└── injury_math.py              # Reuse A+C; optional mid-match roll helper

apps/discord_bot/
├── views/match_injury_prompt.py   # NEW Select + Play On + 30s
├── cogs/battle_cog.py             # Pause loop on INJURY_STOPPAGE; wire bench into state
└── core/injury_rpc.py             # Persist state.recorded_injuries; skip re-roll when present

tests/test_match_substitution_resolve.py
```

## Complexity Tracking

| Concern | Why needed | Simpler alternative rejected |
|---------|------------|------------------------------|
| Pause `async for` with `asyncio.Event` | Discord must await manager | `generator.send()` — does not exist on live path |
| Dual path live vs auto-sim | League silent sims cannot show UI | Always prompt — hangs auto-sim |

## Phase 3 Design Decisions (locked for tasks)

1. **Injection pattern**: `InjurySubView` sets `state.sub_decision = ...` and `state.sub_decision_event.set()` — mirror `TouchlineView` → `home_tactics_modifier`.
2. **Stoppage definition** (NSS has no DEAD_BALL): yield interactive `INJURY` / `INJURY_STOPPAGE` only when pending injury exists and current event is one of `FOUL`, `GOAL`, `SAVE`, `HALF_TIME`, or end of a set-piece resolution. If injury rolls mid-open-play, hold until next stoppage.
3. **Authoritative source**: Mid-match A+C rolls replace cosmetic random INJURY for competitive live/auto-sim. Post-match: persist `recorded_injuries`; **do not** call `select_post_match_injury` again for that club/match.
4. **Subs**: Max 3 per human club per match. Bench list attached to `MatchState` (or team side bag) at kickoff via existing `fetch_bench_ids` + card hydration.
5. **Timeout 30s**: Auto-pick highest OVR eligible bench (prefer same position group); if none → 10-men (remove from squad / zone contrib 0).
6. **Play On**: Keep player; `compromised_ids` → phase-attr ×0.50; at persist, +60% chance tier += 1 (cap Major).
7. **GK**: If GK injured and bench has GK → auto-sub GK (skip UI wait or show pre-selected). If no GK on bench → prompt outfield emergency GK (−40% GK effectiveness / def×0.60 as GDD).
8. **Simultaneous**: Queue pending injuries; prompt sequentially.
9. **90+**: Record injury, no prompt, continue to FULL_TIME.
10. **League two humans**: Only the injured side’s manager gets the view (`owner_id` check); other side sees commentary only.
11. **AI / bot opponent injuries**: Auto-resolve immediately (no Discord wait).
12. **Friendlies**: Still no fatigue/injury (unchanged).

## Implementation Approach (for `/speckit.tasks`)

1. Pure `substitution_resolve.py` + tests (auto-pick, emergency GK, Play On tier bump, 10-men).
2. Extend `MatchState` with bench, subs_used, pending_injuries, recorded_injuries, compromised_ids, decision event fields (event object held outside Pydantic if needed — `asyncio.Event` is not serializable; keep on a small `MatchRuntime` sidecar or `state` monkey-patch attribute set by Discord before stream).
3. `v2_simulator.py`: A+C injury roll on pitch players; queue pending; at stoppage yield rich INJURY event; apply squad swap when `state.pending_sub_resolution` set between iterations (read each loop like tactics).
4. `match_injury_prompt.py` + battle_cog bot/league live loops: on INJURY event for human side, pause, wait ≤30s, write resolution onto state, continue.
5. Auto-sim / `collect_match_events`: call pure auto-resolve inline (no wait).
6. `injury_rpc.apply_post_match_fitness`: if `recorded_injuries` provided, persist those; else keep Phase 2 post-match roll (backward compatible for paths that don’t pass recordings).
7. Commentary tags: `substitution`, `played_through_injury`, `down_to_ten_men`, `emergency_goalkeeper`.
8. Quickstart Phase 3 + `change_log.md`.

**Tasks**: See [tasks.md](./tasks.md) **T043–T062** (US4 Phase 3 Active).

## Economy / balance note

Phase 3 does **not** add coin sinks/faucets. It may slightly change win rates (subs vs Play On). Keep A+C. Monitor injuries/match after ship; no Hospital cost changes.
