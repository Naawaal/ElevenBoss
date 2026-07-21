# Contract: Promotion, Relegation & Bots

**Feature**: `026-league-lifecycle-rulebook`

## Eight-club table movement

| Position | Outcome |
|---------:|---------|
| 1 | Champion **and** promoted |
| 2 | Promoted |
| 3–6 | Remain |
| 7–8 | Relegated |

## Boundary rules

- No promotion above highest division; no relegation below lowest.
- Promotion and relegation sets MUST NOT overlap.
- Bots NEVER consume human promotion slots or human promotion rewards.
- Bots receive no economy rewards and are marked in standings.
- When too few active/eligible humans, **reduce movement** rather than force full 2-up/2-down.
- Promo eligibility requires minimum eligible fixtures (default 7); double_forfeit matches do not count.
- No playoffs in V1.

## Division formation (preparation)

- Max 8 humans per division; fill to 8 with bots.
- Deterministic seating from membership `seasonal_division_tier` / prior finals, then stable tie-breaks.
- Bot rating = division human median × config modifier; **snapshot at season start**.

## Settlement outputs

- Immutable `league_final_standings` rows.
- Update membership division levels for next season.
- Outbox promotion/relegation/champion events (presentation only).
- Operation keys: `season:{id}:promotion`, `season:{id}:rewards` — once each.
