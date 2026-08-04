# Contract: Rivalry presentation

**Feature**: `053-pvp-matchmaking-rivalries`  
**Slice**: 2 (behind `pvp_rivalries_enabled`)

## Hard rule

Rivalry data affects **embeds/DMs/leaderboard copy only**. It MUST NOT change match probabilities, attributes, rewards, fitness, injuries, or LP formulas.

## Surfaces

| Surface | Content |
|---------|---------|
| Pre-match (active rivalry) | Meeting count + series lead |
| Full-time | Events from finalize (activated, tie, lead change, streak, revenge, milestones) |
| `/battle` → Rivalries | List active/dormant summaries |
| Rivalry detail | H2H, last 5 ranked from history, goals, streaks, badges, prefs, Block, Friendly Rematch |
| Server Rivalries board | Hottest pairs: meetings last 30d → closest series → most recent |
| Optional `/leaderboard` | Same board if flagged |

## Friendly Rematch

Opens existing Friendly challenge path; **does not** update rivalry.

## Notifications

- Result-based rivalry DMs only (rate-limited; pref off respected)
- **No** rival login / presence notifications

## Badge keys (examples)

`first_rival`, `revenge_served`, `old_enemies`, `rivalry_leader`, `streak_breaker` — stored on `players.pvp_badge_keys`; display only.
