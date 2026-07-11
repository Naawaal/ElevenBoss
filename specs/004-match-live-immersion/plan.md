# Implementation Plan: Match Live Immersion Fixes

**Branch**: `004-match-live-immersion` | **Date**: 2026-07-11 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-match-live-immersion/spec.md`

## Summary

Fix three live-match immersion breaks **without rewriting NSS Markov structure**: (1) persistent **Goal Scroll** under the scoreboard so early goals survive the 5-line ticker, (2) **named bot XIs** instead of “Opponent Striker” stubs, (3) a **hard 5% transition floor** so possession/shots cannot snowball to 0%–100% in normal play. Half-time already exists as a sim event — make the ticker line an unmistakable separator.

**Technical approach**: Extend `IMatchOutputHandler` live embeds (`StandardMatchHandler` + `LeagueMatchHandler`) with a capped goal list; special-case `HALF_TIME` ticker formatting; add `build_bot_match_squad()` in `match_engine` and replace all three-card “Opponent …” constructions in `battle_cog`; lock `_probability_floor` at `0.05` (remove the large-gap `0.02` branch that enables zero-possession outcomes). No migrations, no new slash commands.

## Technical Context

**Language/Version**: Python 3.11+ (CPython)

**Primary Dependencies**: discord.py ≥2.7, pydantic ≥2.0, local `match_engine` (NSS `v2_simulator`, `CommentaryEngine`, `MatchPlayerCard`)

**Storage**: N/A — no schema / RPC changes

**Testing**: pytest — bot squad naming, probability floor, Goal Scroll formatting helper, batch possession sanity (extend `tests/test_nss_win_rates.py` or small new file)

**Target Platform**: Discord bot (Render) + hosted Supabase (unchanged)

**Project Type**: Monorepo — `packages/match_engine` (pure) + `apps/discord_bot` live UI

**Performance Goals**: Live embed edits stay within existing pacing sleeps; Goal Scroll ≤10 lines; no extra Discord messages

**Constraints**: AGENTS.md — no `discord` in `packages/`; preserve sim → commentary → UI separation; do not rewrite Markov phases; no new commands/tables; SDD reconcile `.specify/specs/v1.0.0/` on implement; update `change_log.md` on ship

**Scale/Scope**: ~6–10 files; three call sites for bot stubs; two live handlers + shared interface; one floor constant

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| I. Monorepo — no `discord` in `packages/` | PASS | Goal Scroll / ticker UI in `battle_cog` handlers; bot squad + floor in `match_engine` |
| II. DB mutations via RPC | PASS | No DB writes |
| III. Typing / Pydantic at boundaries | PASS | `MatchPlayerCard` remains the squad contract; type-hint handler signature change |
| IV. Slash + defer | PASS | No new commands; existing match flows already defer |
| V. APScheduler | PASS | No new jobs |
| VI. User-friendly errors | PASS | Unchanged error paths; empty Goal Scroll omitted cleanly |
| VII. YAGNI | PASS | No commentary rewrite, no new naming service, no schema; reuse existing HALF_TIME yield |

**Post-Phase 1 re-check**: PASS — contracts are live-embed + bot-squad + floor only; architecture layers stay separated.

## Project Structure

### Documentation (this feature)

```text
specs/004-match-live-immersion/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1 (live view / event entities)
├── quickstart.md        # Phase 1
├── contracts/
│   ├── live-embed-layout.md
│   ├── bot-squad-identity.md
│   └── transition-probability-floor.md
└── tasks.md             # /speckit.tasks (not this command)
```

### Source Code (repository root)

```text
packages/match_engine/match_engine/
├── bot_squad.py              # NEW — build_bot_match_squad(target_ovr, rng) → 11 MatchPlayerCards
├── v2_simulator.py           # MODIFY — lock _probability_floor at 0.05 (remove 0.02 gap branch)
├── __init__.py               # MODIFY — export build_bot_match_squad
└── commentary_bank.json      # OPTIONAL — tighten HALF_TIME copy if ticker special-case is insufficient

apps/discord_bot/cogs/
└── battle_cog.py             # MODIFY — Goal Scroll on handlers; HALF_TIME separator; replace Opponent stubs;
                              #           pass goal_scroll into update_ticker (bot + league + any shared loop)

tests/
├── test_bot_match_squad.py           # NEW — names not stubs; 11 players; zones covered; stats near OVR
├── test_probability_floor.py         # NEW or extend — floor always ≥0.05; no 0.02 branch
└── test_nss_win_rates.py             # EXTEND — batch: no exact 0–100 possession with valid XIs

change_log.md                         # MODIFY — player-facing live match note on ship
.specify/specs/v1.0.0/spec.md + plan.md  # RECONCILE on implement
```

**Structure Decision**: Keep Goal Scroll in the Discord handler layer (presentation). Keep bot identity + probability floor in `match_engine` (pure). Do **not** invent actor names inside yield sites — research shows yields already call `_pick_player` / `_get_name`; stubs come from battle_cog squad construction.

## Complexity Tracking

> No constitution violations requiring justification.

## Implementation Notes (for `/speckit.tasks`)

1. **`IMatchOutputHandler.update_ticker`** — add `goal_scroll: list[str] | None = None` (or required list). Field order: Scoreboard → Goal Scroll (omit if empty) → Momentum → Commentary Ticker. Same for `start_match` initial embed (no Goal Scroll field until first goal).
2. **Goal Scroll accumulation** — in each live consumer (`_consume_event`, bot `/battle` loop, any duplicate friendly path): on `GOAL`, append `⚽ {minute}' {actor}` (optionally include team if needed for clarity); keep `goal_scroll[-10:]`. Pass into every `update_ticker` call.
3. **HALF_TIME ticker line** — when `ev["type"] == "HALF_TIME"`, append a fixed separator such as `⏸️ **--- HALF TIME ---**` (may still run commentary for key_events, but ticker line must be the separator per FR-004). Simulator already yields HALF_TIME at 45' — do not double-inject.
4. **`build_bot_match_squad(target_ovr, rng)`** — 11 cards, 4-4-2-ish positions (1 GK / 4 DEF / 4 MID / 2 FWD), unique display names from `gacha` name JSON (load file; avoid pulling full pack generator if possible), `overall ≈ target_ovr ± small noise`, secondary attrs (`pac/sho/pas/dri/def/phy`) derived near overall so `phase_stat_value` is not stuck at default 50. Export from `match_engine.__init__`.
5. **Replace stubs** — all `Opponent Striker/Midfielder/Defender` constructions in `battle_cog` (bot match ~1384, league AI home/away ~740/757). Grep to confirm zero remain.
6. **Floor** — `_probability_floor` always returns `0.05`; delete gap→`0.02` branch. Leave Markov phases, stagnation, and momentum decay as-is. Validate with ≥20 seeded sims that exact 0–100 possession does not occur for valid XIs; favorites still win majority when mismatched.
7. **Shared helper (optional ponytail)** — if bot + league loops duplicate Goal Scroll / HALF_TIME formatting, extract a tiny `_format_ticker_line(ev, text) -> str` in `battle_cog` — only if it shrinks duplication; otherwise leave inline.
8. **Out of scope** — commentary bank rewrite, injury/sub UX, economy/XP, schema, new commands, changing ticker window size from ~5.
