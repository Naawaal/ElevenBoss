# Contract: `process_recovery_batch` RPC

**Feature**: `023-dev-hub-recovery`  
**Migration**: `066_dev_hub_recovery.sql` (planned)

## Signature

```sql
process_recovery_batch(
  p_owner_id BIGINT,
  p_card_ids UUID[]
) RETURNS JSONB
```

`SECURITY DEFINER`, `search_path = public`. GRANT to `anon`, `authenticated`, `service_role`.

## Behavior (ordered)

1. Reject if `p_card_ids` is NULL or `cardinality` not in 1..3 → `'Select between 1 and 3 players'`
2. Reject if array has duplicates → `'Duplicate players in recovery selection'`
3. `sync_action_energy(p_owner_id)`
4. Lock club row (`players` FOR UPDATE)
5. `assert_not_in_match(p_owner_id)`
6. For each card id (stable input order):
   - Lock `player_cards` FOR UPDATE
   - Reject if not owned / retired / `in_academy` → `'Player card not found or not owned'` (or academy-specific message if preferred)
   - `assert_card_not_on_transfer_list(card_id)`
   - Reject if `injury_tier IS NOT NULL` OR `in_hospital` → `'Player is injured — use Hospital'`
   - Reject if `fatigue >= 100` → `'Player is already fully rested'`
   - Reject if active evolution → `'Player is in an active evolution track'`
7. `v_cost_each := get_game_config_int('fatigue_recovery_energy', 5)`
8. `v_grant := get_game_config_int('fatigue_recovery_session', 40)`
9. `v_total := cardinality(p_card_ids) * v_cost_each`
10. Reject if `action_energy < v_total` → `'Insufficient action energy'`
11. **Single** `apply_club_economy(p_owner_id, 0, -v_total, 'recovery_batch', NULL, meta)` — **0 coins**
12. For each card: `UPDATE fatigue = LEAST(100, fatigue + v_grant)`; record applied delta
13. **Must not** modify `daily_drill_count`, `daily_drill_reset_at`, or `player_drill_daily_log`
14. **Must not** call `apply_card_xp`
15. Return JSON:

```json
{
  "energy_spent": 15,
  "coins_spent": 0,
  "xp_gained": 0,
  "recovery_amount": 40,
  "players": [
    {
      "card_id": "...",
      "fatigue_gained": 40,
      "new_fatigue": 85
    }
  ],
  "economy": { "...": "apply_club_economy payload" }
}
```

## Single-card wrapper (optional)

```sql
process_recovery_session(p_owner_id BIGINT, p_player_card_id UUID)
  RETURNS JSONB
```

May be redefined as:

```sql
SELECT public.process_recovery_batch(p_owner_id, ARRAY[p_player_card_id]);
```

(shape-normalize return if old callers expect flat `fatigue_gained` / `new_fatigue` — only if wrappers kept). Prefer updating Discord to call batch only and DROP old function after grep is clean.

## Must not

- Consume skill-drill daily capacity
- Debit coins
- Partial apply (any failure before economy → no writes; after economy starts, transaction rolls back on error)
- Touch Hospital admit/discharge tables
- Accept &gt;3 or 0 cards

## Caller

`apps/discord_bot/cogs/development_cog.py` — Recover confirm after defer; map exceptions via `api_errors.py`.

## Schema guard

Extend `verify_required_schema.sql` / migration DO block:

- `function:process_recovery_batch`
- Keep or replace `function:process_recovery_session` per wrapper decision
