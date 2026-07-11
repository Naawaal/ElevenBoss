# Contract: `transfer_mentor_xp` RPC

**Feature**: `006-mentor-transfusion`  
**Migration**: `052_mentor_transfusion.sql` (forward-only after `051`)

## Signature

```text
transfer_mentor_xp(
  p_owner_id      BIGINT,
  p_source_card_id UUID,
  p_target_card_id UUID,
  p_mentor_units   INTEGER
) RETURNS JSONB
```

**SECURITY DEFINER** (same class as other progression mutators). Validate ownership inside the function; do not trust client beyond IDs + units.

## Preconditions (raise clear EXCEPTION messages)

| Check | Example message fragment |
|-------|---------------------------|
| `p_mentor_units < 1` | Invalid mentor unit amount |
| Source missing / wrong owner | Source card not found / not owned |
| Target missing / wrong owner | Target card not found / not owned |
| `source_id = target_id` | Source and target must differ |
| Source `overall < potential` | Source card has not reached potential ceiling |
| Source `skill_points < 5 * N` | Insufficient skill points |
| Target `overall >= potential` | Target card is already maxed |
| Target `level >= 100` | Target cannot receive more XP |
| XP headroom &lt; `500 * N` | Target cannot absorb mentor XP |
| Daily `COUNT(*) >= 3` for club/today | Daily mentor transfer limit (3) reached |

Prefer stable, greppable message prefixes so `api_errors.py` can map them.

## Transaction body (order)

1. `SELECT … FOR UPDATE` source and target rows (deterministic lock order by `id` to avoid deadlock).
2. Re-validate preconditions on locked rows.
3. Count today’s successful transfers for `p_owner_id`; reject if `>= 3`.
4. Compute `sp_spent = 5 * N`, `xp_granted = 500 * N`.
5. Update source: `skill_points = skill_points - sp_spent`, `skill_points_spent = skill_points_spent + sp_spent` (guard `skill_points >= sp_spent`).
6. `v_xp := apply_card_xp(p_target_card_id, xp_granted, 'mentor_transfer')`.
7. If `v_xp` indicates waste (`xp_wasted > 0`) — **should not happen** after headroom check; if it does, `RAISE` to roll back entire transaction.
8. `INSERT INTO mentor_transfer_log (...)`.
9. Return JSONB:

```json
{
  "source_card_id": "...",
  "target_card_id": "...",
  "mentor_units": 3,
  "sp_spent": 15,
  "xp_granted": 1500,
  "source_skill_points": 12,
  "xp_result": { "old_level": 24, "new_level": 27, "levels_gained": 3, "skill_points_granted": 9, "xp_added": 1500, "xp_wasted": 0, "new_xp": 12345 },
  "transfers_used_today": 2,
  "transfers_remaining_today": 1
}
```

## Explicit non-effects

- No `apply_club_economy` / coins
- No energy changes
- No match XP daily cap (`p_source` is not `match_simulation`)
- No allocation daily cap interaction
- Injury/fatigue columns ignored

## Schema guard

Migration ends with guard entries for:

- `table:public.mentor_transfer_log`
- `function:transfer_mentor_xp` (use `split_part(..., 2)` pattern — not `:3`)
- RLS policy entries if required by `031` / verify script conventions

Extend `supabase/scripts/verify_required_schema.sql` similarly.

## Bot call site

Only from Development mentor confirm callback (after `defer` + `assert_not_in_match`). Never from match reward paths.
