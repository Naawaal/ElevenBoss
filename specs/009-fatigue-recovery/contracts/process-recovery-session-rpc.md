# Contract: `process_recovery_session` RPC

**Feature**: `009-fatigue-recovery`  
**Migration**: `054_fatigue_recovery.sql` (planned)

## Signature

```sql
process_recovery_session(
  p_owner_id BIGINT,
  p_player_card_id UUID
) RETURNS JSONB
```

`SECURITY DEFINER`, `search_path = public`. GRANT to `anon`, `authenticated`, `service_role`.

## Behavior (ordered)

1. `sync_action_energy(p_owner_id)`
2. Lock club row (`players` FOR UPDATE); reset `daily_drill_count` if `daily_drill_reset_at < CURRENT_DATE`
3. `assert_not_in_match(p_owner_id)`
4. Reject if club `daily_drill_count >= 20` → `'Daily drill limit reached'`
5. Lock card FOR UPDATE; reject if not owned / retired → `'Player card not found or not owned'`
6. Reject if `injury_tier IS NOT NULL` OR `in_hospital` → `'Player is injured — use Hospital'`
7. Reject if `fatigue >= 100` → `'Player is already fully rested'`
8. Reject if active evolution on card → `'Player is in an active evolution track'`
9. Upsert `player_drill_daily_log`; reject if count > 5 → `'Daily drill limit reached for this player (max 5 per day)'` (same message family as drills)
10. Read energy cost from `fatigue_recovery_energy` (default 10); reject if insufficient → `'Insufficient action energy'`
11. `apply_club_economy(p_owner_id, 0, -energy, 'recovery_session', NULL, jsonb meta)` — **0 coins**
12. Increment `players.daily_drill_count`
13. `fatigue_gain := get_game_config_int('fatigue_recovery_session', 40)`
14. `UPDATE player_cards SET fatigue = LEAST(100, fatigue + fatigue_gain)` — **no XP / stats**
15. Return JSON:

```json
{
  "fatigue_gained": 40,
  "new_fatigue": 85,
  "energy_spent": 10,
  "coins_spent": 0,
  "xp_gained": 0,
  "economy": { "...": "apply_club_economy payload" }
}
```

`fatigue_gained` is the applied delta after clamp (may be &lt; config when near 100).

## Must not

- Call `apply_card_xp`
- Debit coins
- Bypass drill daily caps
- Touch Hospital tables
- Refill match `action_energy` beyond the normal sync at start

## Caller

`apps/discord_bot/cogs/development_cog.py` — Recovery Session confirm after defer; map exceptions via `api_errors.py`.
