# Contract: Penalty Shootout

**Feature**: `057-competitive-bot-match`  
**Module**: `packages/match_engine/penalty_shootout.py` (pure)

## Inputs

- Eligible XI at end of ET (on pitch, not sent off, not removed injured)
- Per-player: SHO, consistency, morale (optional), fitness, is_gk / DEF for keeper
- `shootout_seed` (deterministic)
- Club ids for home/away

## Derived ratings

```text
composure = consistency * 0.70 + morale * 0.30   # else consistency
reflexes  = effective_DEF_or_OVR for current GK
```

## Taker order

```text
score = SHO*0.55 + composure*0.30 + fitness*0.10 + consistency*0.05
(+ small seeded jitter)
sort descending; store order arrays on PenaltyShootoutState
```

Sudden death: cycle order; no second kick until all eligible have taken one (unless fewer than needed).

## Kick resolution

```text
taker_quality = SHO*0.55 + composure*0.30 + consistency*0.10 + fitness*0.05
keeper_quality = DEF*0.40 + reflexes*0.40 + consistency*0.10 + fitness*0.10
P(goal) = clamp(f(taker_quality - keeper_quality), 0.58, 0.90)
```

On failure: classify `saved` vs `missed` from relative keeper contribution vs weak taker roll (commentary only).

## Control flow

```text
alternate kicks (home first unless product already defines otherwise — match existing coin toss if any; else home first)
after each kick: append PenaltyKickEvent; persist; check early win
after 5 each: if tied → sudden_death=true; continue
on complete: set winner_club_id; football score unchanged
```

## Outputs

- Updated `PenaltyShootoutState`
- Events for stadium adapter
- Final `home_penalties` / `away_penalties` / winner

## Non-goals

Manual direction/dive; shootout XP; AI shootout bonuses.
