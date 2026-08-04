# Contract: PvP queue RPCs

**Feature**: `053-pvp-matchmaking-rivalries`  
**Migration**: 098

## `get_battle_hub_state(p_owner_id, p_guild_id)`

Returns JSON including: feature flags, queue status, energy costs (pvp/practice), global_lp, division, daily PvP count/cap, daily rewarded Practice count/cap, active rivalry count, unresolved run if any, requeue_available_at.

## `join_pvp_queue(p_owner_id, p_guild_id, p_channel_id)`

1. Require `battle_pvp_enabled`
2. Validate manager, XI, energy ≥ cost (no debit), not locked, under daily ranked cap, not duplicate active queue, requeue delay elapsed
3. Snapshot LP / division / xi_rating
4. Insert `searching` row with `expires_at = now() + pvp_search_timeout_seconds`
5. Return queue payload

**Must not** charge energy.

## `cancel_pvp_queue(p_owner_id, p_queue_id?)`

- Owner-only; only `searching` (idempotent if already cancelled)
- Set 15s requeue delay
- No energy charge

## `expire_pvp_queue_rows()` (helper)

Marks past-due `searching` as `expired` (called by matchmaker / join cleanup).

## `try_match_pvp_queue(p_guild_id?)` 

Optional guild filter for shadow tests; production may scan all guilds with ≥2 searching.

1. SKIP LOCKED eligible `searching` rows
2. Apply widening by `now() - joined_at`
3. Exclude blocks, same-pair cooldown, pair daily cap, self
4. Revalidate both managers (authoritative)
5. Sorted dual `acquire_match_lock(..., 'pvp')`
6. Create immutable snapshots + `match_runs` (`run_type='pvp'`, server seed)
7. Mark both queue rows `matched` + `matched_run_id`
8. Return run metadata for Discord stadium dispatch

On failure after locks: release locks, restore/cancel queue appropriately, **no** energy.

## Widening schedule (config mirrors)

| Queue age | Division | LP | XI OVR |
|-----------|----------|----|--------|
| 0–15s | same | ±100 | ±4 |
| 15–30s | ±1 | ±200 | ±7 |
| 30–60s | ±2 | ±350 | ±10 |
| continued | max | ±500 | ±12 |

## Config keys (insert defaults; flag false)

`battle_pvp_enabled`, `pvp_rewards_enabled`, `pvp_rivalries_enabled`, `pvp_rivalry_dms_enabled`, `pvp_server_leaderboard_enabled`, `ai_practice_rewards_enabled`, `pvp_search_timeout_seconds`, `pvp_matchmaker_interval_seconds`, `pvp_energy_cost`, `pvp_rewarded_matches_daily`, `pvp_same_pair_cooldown_minutes`, `pvp_same_pair_matches_daily`, widening/max ranges, `pvp_provisional_matches`, coin multipliers, Practice energy/multipliers/daily, rivalry 3/30/60.
