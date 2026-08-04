# Contract: Capacity cutover & aging

**Feature**: `051-youth-academy-rarity`  
**Migration**: `095_youth_academy_rarity_v2.sql` (+ ops verify)

## Cutover steps (ordered)

1. Enable integrity helpers already present (049); ensure academy RPCs call them.
2. **Audit** academy cards with `potential > rarity_potential_cap(rarity)` or `overall > potential`.
3. **Repair** where `overall ≤ cap`: `potential = LEAST(potential, cap)` (and ≥ overall). Rows with `overall > cap` → leave for global 049 / manual; do not invent rarity.
4. **Init** `pot_visible_lo/hi` containing true POT from level width table; set `scout_assessment_level = none`; `academy_origin = migration` if null.
5. **Do not** delete over-capacity seats; acquisition paths use strict `occupied < cap`.
6. Flip `youth_academy_v2_enabled` when bot build that understands ranges is deployed.

## Capacity helper

```text
academy_slot_cap(level): 1→3, 2→3, 3→4, 4→4, 5→5
free_seats = max(0, cap - occupied)   # over-cap ⇒ 0
```

## Aging (replace promote-or-delete@20)

| Stage | Trigger | Behavior |
|-------|---------|----------|
| Warn | age ≥ `academy_age_warn` (20) | Hub warning copy; stamp warned_at once |
| Decay | season aging + unpromoted + age ≥ warn | POT − at most `academy_aging_decay_max` (1), not below OVR, not above cap |
| Pending | age ≥ `academy_age_out` (21) | set `academy_age_out_pending_at` if null |
| Auto-release | pending + grace elapsed | release seat (same as manager release economics: no refund); not forced senior |

Managers can promote or release during grace subject to weekly promote cap / normal rules.
