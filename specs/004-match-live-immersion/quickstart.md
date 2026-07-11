# Quickstart: Match Live Immersion Fixes

**Feature**: `004-match-live-immersion` | **Date**: 2026-07-11

Manual + automated validation after implementation. No migration required.

## Prerequisites

- Bot running with NSS live matches (`stream_match`)
- Registered manager with a starting XI
- pytest available at repo root

## 1. Unit / batch checks

```bash
pytest tests/test_bot_match_squad.py tests/test_probability_floor.py tests/test_nss_win_rates.py -q
```

**Expect**:
- Bot squad: 11 named players, no `Opponent Striker|Midfielder|Defender`
- Floor: `_probability_floor` always `0.05`
- Batch sims: no exact 0–100 possession for valid XIs; favorites still win majority when mismatched

## 2. Goal Scroll (ghost match)

1. Start a bot match (`/battle` or equivalent) and watch the live embed.
2. Let at least three goals occur, including one before ~60'.
3. After the ticker has rolled past early events, inspect the embed.

**Expect** ([live-embed-layout.md](./contracts/live-embed-layout.md)):
- Scoreboard shows the full score
- Goal Scroll lists each goal (`⚽ m' Name`) under the scoreboard
- Momentum + last ~5 commentary lines still present
- Early goals remain on the scroll after leaving the ticker

## 3. Half-time separator

1. Watch the same live match through 45'.

**Expect**: ticker contains a clear `--- HALF TIME ---` (or equivalent) line once; no duplicate break markers.

## 4. Bot identity

1. Play a bot match until a bot chance/goal appears.

**Expect** ([bot-squad-identity.md](./contracts/bot-squad-identity.md)):
- Commentary / Goal Scroll use real-looking names
- Zero occurrences of `Opponent Striker`, `Opponent Midfielder`, `Opponent Defender`

## 5. Possession sanity (feel check)

1. Complete a match where you are outmatched but not empty-squad.
2. Open post-match stats.

**Expect** ([transition-probability-floor.md](./contracts/transition-probability-floor.md)):
- Possession is not `0% - 100%`
- Weaker side usually shows some shots or chances across a few replays
- Stronger side still tends to dominate scoreline

## 6. League AI path

1. If a league fixture vs AI is available, run/watch live commentary.

**Expect**: same Goal Scroll + named AI players + half-time separator (shared handlers).

## 7. Regression smoke

1. Friendly (human vs human) if available — real card names still appear.
2. Confirm no new slash commands; press conference still shows possession/shots from live stats.

## Done when

- [ ] Automated tests above pass
- [ ] Manual Goal Scroll + half-time + bot names verified once in Discord
- [ ] Grep shows zero `Opponent Striker` / `Opponent Midfielder` / `Opponent Defender` card stubs
- [ ] `change_log.md` updated on ship
