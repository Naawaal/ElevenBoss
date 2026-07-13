# Contract: Match AI Intensity Parity

**Feature**: `016-tier-fatigue-rebalance`

## Human vs bot (and human league)

1. Resolve **human** club `intensity_tier` for the match.
2. Use that tier for:
   - Starter drain math applied to the **human** XI
   - Injury probability for mid-match / post-match rolls on **both** sides in the simulator (same base chance table)
3. Persist fatigue + injuries only for human clubs (existing `is_ai` skip).

AI “parity” means **shared intensity parameters**, not mirrored RNG outcomes or persisted bot fitness.

## League human vs human

Each club uses **its own** `intensity_tier` for its own drain/injury persistence. (Do not force both sides onto one tier.)

# Forward-compat: when a cup match path is added, pass the human club's
# primary `intensity_tier` into the same fitness helpers (no cup downgrade).
# This feature does **not** implement cups.

## Explicit non-goals

- Creating bot `player_cards` fatigue rows
- Soft-lock emergency fillers
