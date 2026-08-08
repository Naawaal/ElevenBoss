# Contract: Stadium Presentation

**Feature**: `057-competitive-bot-match`  
**Layer**: `apps/discord_bot/` only

## Principles

- Engine may emit many events; Discord message rate stays within existing Bot Battle cadence.
- Simulation state is authoritative; failed sends never rewind football.

## Tiering

| Tier | Examples | Discord |
|------|----------|---------|
| A | goals, reds, major injuries, ET transitions, pen kicks, FT | always publish / high priority |
| B | yellows, dangerous FK, major corners, notable offsides | selective |
| C | routine foul/corner/offside | stats / next digest only |

## Phase banners (one each)

1. Extra time start (show 90' score)  
2. ET break (95')  
3. Penalty shootout start (AET score)  
4. Final: `H–A` or `H–A (pens hp–ap)`  

## Shootout UI (v1)

Single reusable message/embed updated in place:

```text
🥅 SHOOTOUT
Home   ✅ ✅ ❌ …
Away   ✅ ❌ …
```

Sudden death header when applicable. No new image pipeline.

## Buffering

Presenter holds a short queue of Tier B/C lines and flushes on next Tier A tick or digest interval — mirror existing ticker sleep pattern in `execute_bot_battle`.
