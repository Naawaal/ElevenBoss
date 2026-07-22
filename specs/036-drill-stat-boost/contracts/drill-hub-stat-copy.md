# Contract: Training Drills hub copy (attribute boost)

**Feature**: `036-drill-stat-boost` | **Surface**: `/development` → **Training Drills**

## Menu blurb

Hub description MUST stop implying drills are XP-only. Example intent:

- Skill drills grant **XP** and attempt **+1** to the trained attribute (capped by attribute max / potential).

Recover remains fitness-only; no change to that sentence.

## Drill select options

For each of the six drills, option `description` SHOULD include:

| Card state for that drill’s attribute | Description intent |
|---------------------------------------|--------------------|
| Boost allowed | `+1 XXX` plus existing XP · energy preview |
| Boost not allowed | Explicit capped / at-potential hint (not a guaranteed `+1`) plus XP · energy |

Preview gate: reuse package `can_allocate_skill_point` (or equivalent) on the selected card’s stats — **does not** require available skill points.

## Post-drill summary

| Outcome | Required copy |
|---------|----------------|
| `stat_boosted` | Name player + drill; XP gained; **`+1 {STAT}`** (and new value if available); show **new OVR** when present; costs spent |
| Boost blocked | Name player + drill; XP gained; clear line that attribute did **not** increase + humanized `boost_block_reason`; costs spent; optional reminder that Allocate Skills still uses skill points when eligible |

### Reason → player text (minimum)

| `boost_block_reason` | Player-facing sense |
|----------------------|---------------------|
| `stat_at_maximum` | That attribute is already maxed |
| `at_potential` | Player is already at potential overall |
| `would_exceed_potential` | Raising that attribute would exceed potential |

Remove the unconditional line “OVR unchanged — spend skill points to raise stats” when a boost applied. When blocked / OVR flat, a short Allocate Skills hint remains OK.

## Non-goals

- New hub buttons or slash commands.
- Changing Recover / Fusion / Evolutions copy except if they incorrectly claim drills are the only XP path (out of scope unless they lie about drill rewards).
