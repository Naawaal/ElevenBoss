# Contract: Matchday Schedule (Guild Timezone)

**Feature**: `026-league-lifecycle-rulebook`  
**Pure helper**: `packages/leagues` schedule module  
**Frozen inputs (per season)**: IANA `timezone`, `resolution_hour_local` (0–23)

## Generation (preparation only)

For matchday `n` in `1..14`:

1. Determine local calendar date for matchday `n` from season start date in the frozen timezone (day 0 = first matchday local date).
2. Local resolution instant = that date at `resolution_hour_local:00:00`.
3. Apply DST rules:
   - **Nonexistent local time (spring gap)**: use the first valid local time after the gap.
   - **Ambiguous local time (fall overlap)**: use the **earlier** (DST) offset.
4. `window_end` = that instant as UTC.
5. `window_start` = previous matchday’s `window_end` (matchday 1: preparation→active boundary / published open time).
6. Persist UTC `window_start` / `window_end` on `league_matchdays` and copy onto fixtures for that matchday.

## Invariants

- Guild timezone/hour changes **after** preparation MUST NOT alter stored windows.
- Pause: add paused duration to all **unresolved** matchday/fixture `window_start`/`window_end`.
- Hub/announce MUST render deadlines via Discord timestamps from stored UTC `window_end`.

## Display

Managers see local time through Discord `<t:unix:F>` / relative formats — no manual UTC conversion required (SC-006).
