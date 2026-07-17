# Contract: Daily Tick & UTC Windows

**Feature**: `020-league-dynamics`

## Pure helper — `assign_dynamics_windows(start_time, total_matchdays) → list[{matchday, window_start, window_end}]`

### Rules (D4)

- Let `day0 = date_trunc('day', start_time)` in UTC.
- For matchday `N` in `1..total_matchdays`:
  - `window_end = day0 + N days` (00:00 UTC)
  - `window_start = start_time` if `N == 1` else `day0 + (N-1) days`

### Play gate

- Manual play allowed iff `window_start ≤ now ≤ window_end` and `is_played = false` (existing battle_cog pattern).
- After `window_end`, only auto-sim may resolve.

## Scheduler — `dynamics_daily_tick_job` (~00:05 UTC)

### Preconditions

1. Bot up; DB reachable.
2. For each `league_seasons` where `status='active'` AND `pacing_mode='dynamics'`:
   - Skip if paused / guild unreachable (existing pause helpers).

### Effects

1. Call existing `auto_sim_expired_fixtures` (sets `resolved_by='auto_sim'` on sim path).
2. When current matchday fully played → settlement: Journal notify + `award_manager_of_the_matchday` + `update_current_matchday` (may complete season).

### Legacy job

- `auto_sim_expired_fixtures_job` (interval 10 min) **filters** `pacing_mode='legacy'` (or NULL treated as legacy).
- Hub-open opportunistic sim: all active seasons (unchanged).

## Admin start (Dynamics branch)

When `league_dynamics_enabled`:

1. Force `duration_days=14`, seat into 8-club tiers (see division contract).
2. `total_matchdays=14` per tier tables (same index).
3. Insert fixtures with dynamics windows (not `duration/matchdays` slice).
4. Set `pacing_mode='dynamics'`.

When flag off: existing rolling window path; `pacing_mode='legacy'`.
