# Data Model: Match Live Immersion Fixes

No database tables. Entities below are **in-memory / view** contracts for the live match stream.

## GoalScrollEntry (view)

| Field | Type | Rules |
|-------|------|-------|
| minute | int | Match minute of the goal (0–90+) |
| scorer | str | Display name from event `actor` (never positional stub) |
| line | str | Rendered form, e.g. `⚽ 14' Ada Okonkwo` |

**Collection rules**:
- Append on each `GOAL` event in chronological order.
- Cap at **10** entries (drop oldest).
- Empty collection → omit Goal Scroll embed field entirely.

## LiveEmbedSnapshot (view)

Ordered fields on the updating live message:

1. **Scoreboard** — club names + `score_update`
2. **Goal Scroll** — joined GoalScrollEntry lines (optional)
3. **Momentum** — existing bar from `MatchState.momentum`
4. **Commentary Ticker** — last ~5 formatted lines (includes half-time separator when present)

## MatchEvent (existing sim payload — relevant fields)

| Field | Notes |
|-------|-------|
| type | Includes `GOAL`, `HALF_TIME`, `CHANCE`, … |
| minute | Clock |
| actor | Must be roster display name for player events |
| team | Club name string |
| score_update | `H - A` string |

No new event types required. HALF_TIME already exists.

## BotMatchSquad (ephemeral)

| Field | Rules |
|-------|-------|
| cards | Exactly **11** `MatchPlayerCard` |
| names | Unique-enough display names; **forbidden**: `Opponent Striker`, `Opponent Midfielder`, `Opponent Defender`, and other `Opponent <Role>` stubs |
| positions | Full zone coverage: ≥1 GK, DEF, MID, FWD |
| overall | Centered on target AI/bot rating |
| secondary attrs | Near overall so phase rolls are meaningful |

Built per match; not persisted.

## TransitionProbabilityFloor (config constant)

| Name | Value | Applies to |
|------|-------|------------|
| `MIN_TRANSITION_P` | `0.05` | All `_roll_chance` outcomes after formula + clamp to ≤0.95 |

No per-match mutable entity — module constant / function return only.

## Relationships

```text
stream_match ──yields──► MatchEvent
                │
                ├─ GOAL ──► GoalScrollEntry (UI list)
                ├─ HALF_TIME ──► ticker separator line
                └─ actor ◄── BotMatchSquad / human XI card.name

_roll_chance ──uses──► TransitionProbabilityFloor
                │
                └──► midfield possession ticks ──► post-match possession %
```
