# Contract: Seat & Prize Bounds

**Feature**: US-42.5 | INV-12, INV-15

## Seats

- ≤1 active human seat per guild season rules (US-42.3 / `register_league_season`)
- Re-register → already-seated idempotent
- Soft Inactive/Abandoned → Block **new** registration until Active
- Leave guild mid-season → **no** club/card delete; assistant continues (`026`)

## Prizes & promo

- Pay humans only (`is_ai = FALSE` in prize distribution)
- Economy keys: `season_prize:{season_id}:{player_id}` (and refund keys)
- AI never consumes human prize identity or human promo slots (`026` human-first + INV-15)
- Promo apply once via `promo_applied` (or equivalent durable flag)

## Non-goals

- Changing prize pool percentages
- Discord admin prize tools
