# Contract: Live embed layout (Goal Scroll + ticker)

## Surfaces

- `StandardMatchHandler.start_match` / `update_ticker`
- `LeagueMatchHandler.start_match` / `update_ticker`
- Callers: bot match loop and league `_consume_event` in `battle_cog.py`

## Embed field order

| Order | Field name (approx.) | Content |
|-------|----------------------|---------|
| 1 | Scoreboard | `🏟️ **Home** \`H - A\` **Away**` |
| 2 | Goal Scroll | Up to 10 lines `⚽ {m}' {scorer}`; **omit field if empty** |
| 3 | Momentum | Existing `get_momentum_bar(state.momentum)` |
| 4 | Commentary Ticker / Live Commentary | Last ~5 ticker lines |

## Handler signature

```text
update_ticker(ev, state, recent_ticker, touchline_view, goal_scroll: list[str] | None = None)
```

Callers always pass the current scroll list (possibly empty).

## HALF_TIME ticker line

When `ev["type"] == "HALF_TIME"`, the line appended to ticker history MUST be a clear separator, e.g.:

```text
⏸️ **--- HALF TIME ---**
```

Do not rely solely on soft commentary prose for the visible ticker line. Do not emit a second half-time event from the UI.

## Guarantees

- Early goals remain visible in Goal Scroll after they leave the 5-line ticker.
- Scoreboard totals remain authoritative if scroll is capped at 10.
- No extra Discord messages for goals (same edited live message).

## Non-goals

- Changing ticker window size from ~5
- Persisting Goal Scroll after the live message is replaced by press conference
- New slash commands
