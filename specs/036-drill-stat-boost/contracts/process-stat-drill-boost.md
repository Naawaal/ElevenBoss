# Contract: `process_stat_drill` attribute boost

**Feature**: `036-drill-stat-boost` | **RPC**: `public.process_stat_drill(p_owner_id bigint, p_card_id uuid, p_drill_id text) → jsonb`

## Signature

Unchanged. Callers continue to pass `p_owner_id`, `p_card_id`, `p_drill_id`.

## Preconditions (unchanged)

- Club / card daily drill caps, energy, coins, level tier, ownership, not retired.
- `assert_not_in_match`, `assert_card_not_on_transfer_list`, `assert_card_action_allowed(..., 'drill')`.
- Not in active evolution; known `p_drill_id`.

Hard failures continue to `RAISE EXCEPTION` with existing messages (insufficient energy/coins, limits, unknown drill, etc.).

## Attribute boost semantics

| Drill id | Stat column |
|----------|-------------|
| `pac_sprint` | `pac` |
| `sho_finishing` | `sho` |
| `pas_distribution` | `pas` |
| `dri_dribble` | `dri` |
| `def_tackling` | `def` |
| `phy_strength` | `phy` |

1. Attempt **exactly +1** on the mapped column after drill gates pass.
2. Soft-fail (no raise) when:
   - current stat ≥ 99 → `boost_block_reason = 'stat_at_maximum'`
   - `overall >= potential` → `'at_potential'`
   - `peek_card_ovr(card, col, stat+1) > potential` → `'would_exceed_potential'`
3. On success: update column, `recalculate_card_ovr(card)`, set `stat_boosted = true`, `stat_delta = 1`.
4. Never decrement `skill_points`.
5. Always run existing `apply_club_economy` + daily counter updates + `apply_card_xp` when hard gates passed — including when boost is soft-failed.

## Success JSON (additive)

Keep existing keys (`xp_gain` / `cost` / `daily_drill_count` / `daily_drill_limit` / `training_ground_bonus` / `economy` / `progression`). Add:

| Key | Type | When |
|-----|------|------|
| `stat_boosted` | boolean | always on success |
| `stat` | string | uppercase code (`SHO`, …); always when drill id known |
| `stat_delta` | integer | `1` or `0` |
| `new_stat_value` | integer \| null | set when boosted; null when blocked |
| `new_ovr` | integer | post-drill overall |
| `boost_block_reason` | string \| null | null when boosted; one of the reason codes above when blocked |

### Example — boosted

```json
{
  "xp_gain": 28,
  "cost": 220,
  "stat_boosted": true,
  "stat": "SHO",
  "stat_delta": 1,
  "new_stat_value": 71,
  "new_ovr": 68,
  "boost_block_reason": null,
  "progression": { "xp_added": 28, "levels_gained": 0 },
  "economy": {}
}
```

### Example — blocked at potential

```json
{
  "xp_gain": 28,
  "stat_boosted": false,
  "stat": "SHO",
  "stat_delta": 0,
  "new_stat_value": null,
  "new_ovr": 82,
  "boost_block_reason": "would_exceed_potential",
  "progression": { "xp_added": 28 }
}
```

## Client parser contract

`parse_stat_drill_result` MUST expose at least:

- existing XP/economy fields
- `stat_boosted` (default `false` if missing)
- `stat`, `stat_delta`, `new_stat_value`, `new_ovr`, `boost_block_reason`

Missing keys on older payloads MUST not crash the hub.

## Non-goals

- Changing 20/5 caps, energy/coin formulas, or XP curve.
- Consuming skill points.
- New drill ids or multi-stat targets.
