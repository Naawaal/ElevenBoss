# Research: Match Live Immersion Fixes

## R1 — Goal Scroll lives in the Discord handler, not the simulator

**Decision**: Accumulate a capped `goal_scroll: list[str]` in the live event consumer and render it as an embed field between Scoreboard and Momentum in `StandardMatchHandler` / `LeagueMatchHandler`. Simulator continues to yield `GOAL` events only; it does not own scroll state.

**Rationale**: Spec layout is a presentation concern. Keeping scroll in the UI layer preserves sim → commentary → UI separation and avoids Discord types in `packages/`.

**Alternatives considered**:
- Persist goals on `MatchState` — rejected (state pollution for a Discord-only view).
- Expand ticker window to 20+ lines — rejected (spec keeps ~5-line ticker; Goal Scroll is the durable channel).

## R2 — Half-time separator vs existing HALF_TIME event

**Decision**: Keep the existing `v2_simulator` HALF_TIME yield at minute 45. Change **ticker formatting** so the live line is a clear separator (`⏸️ **--- HALF TIME ---**` or equivalent). Do not inject a second synthetic half-time event.

**Rationale**: Simulator already emits HALF_TIME; commentary bank prose (“players head to the dressing rooms”) is easy to miss in a 5-line scroll. Spec FR-004 asks for an unmistakable marker.

**Alternatives considered**:
- Only edit `commentary_bank.json` HALF_TIME strings — weaker visual break; still acceptable as a supplement.
- UI-only inject at minute==45 without sim event — rejected (risk of desync / double markers).

## R3 — Bot names: fix squad construction, not yield sites

**Decision**: Replace three-card stub squads (`Opponent Striker` / `Midfielder` / `Defender`) in `battle_cog` with `match_engine.bot_squad.build_bot_match_squad(target_ovr, rng)` returning **11 named `MatchPlayerCard`s**. Leave ATTACK / SCORING_OPP yields as-is — they already use `_pick_player` + `_get_name(actor)`.

**Rationale**: Grep shows stubs are created at bot-match and league-AI hydration sites. The simulator correctly passes `player.name` into `actor`. Fixing yields alone would still show “Opponent Striker” because that *is* the card name.

**Alternatives considered**:
- Map positional stubs to random names at yield time — rejected (hides root cause; MOTM/Goal Scroll still wrong if cards stay stub-named).
- Persist bot squads in DB — rejected (YAGNI; ephemeral match XI is enough).
- Call full `generate_starter_squad()` from gacha — heavier than needed (rarity/youth logic); prefer OVR-targeted match cards with shared name lists.

## R4 — Why 0% possession still happens despite an existing floor

**Decision**: (1) Lock `_probability_floor` to a constant **0.05** (remove large-gap `0.02` branch). (2) Record possession ticks on **set-piece** (foul → SET_PIECE) and **counter steals** (BUILD_UP fail → COUNTER_ATTACK), not only midfield contest resolution. Keep Markov phases and momentum/stagnation unchanged.

**Rationale**: Midfield-only ticks meant a side could create chances via counters/set-pieces yet show **0%** possession. Floor alone cannot fix missing tick sites. Spec SC-003/SC-004 require no exact 0–100 splits and a believable weaker-side band.

**Alternatives considered**:
- Soft-clamp post-match possession display only — rejected (FR-010).
- Raise floor to 8–10% without fixing tick gaps — rejected (masks root cause; still fails when counters dominate).
- Reduce midfield momentum ×2 → ×1 — deferred (win-rate gates sensitive; tick completeness was sufficient).

## R5 — Bot XI quality also feeds possession/shots feel

**Decision**: Generated bot cards set secondary attrs near `overall` (not left at MatchPlayerCard defaults of 50) and include a GK + full zones. This is part of bot identity work, not a separate balance project.

**Rationale**: Stub cards with `overall=84` but `dri/pas/sho=50` distort `phase_stat_value` vs human XIs and amplify “one side never creates a chance” feel even when club OVR looks competitive.

**Alternatives considered**: Only rename the three stubs — rejected (still no GK zone; still default-50 attrs).

## R6 — Scope of live UI surfaces

**Decision**: Update both `StandardMatchHandler` and `LeagueMatchHandler`, and every live consumer that calls `update_ticker` (bot match loop + league `_consume_event`). Grep for other ticker builders and align or document as dead.

**Rationale**: FR-011 — all standard live scoreboard+ticker presentations.

**Alternatives considered**: Bot-only Goal Scroll — rejected (league ghost-match is the same bug).
