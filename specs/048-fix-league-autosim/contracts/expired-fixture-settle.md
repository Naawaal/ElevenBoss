# Contract: Expired Fixture Settle

**Feature**: `048-fix-league-autosim`  
**Consumers**: `auto_sim_expired_fixtures`, hub-on-open / legacy 10-min job / Dynamics tick callers  
**Integrity**: **US-42.5** + [absence-vs-outage](../../034-league-integrity/contracts/absence-vs-outage.md) + `026` forfeit rules

## Preconditions for sporting settle

Fixture is eligible for this contract when:

- `window_end` is set and `now > window_end`
- `is_played` is false
- No **active** `match_runs` for the fixture
- Season is active (caller already scopes this)
- Guild is **reachable** (if not → infra skip / pause path — **no** forfeit)

## Decision matrix

Let `home_ok` / `away_ok` be true for AI always; for humans iff `human_club_xi_ok`.

| home_ok | away_ok | Action |
|---------|---------|--------|
| T | T | `run_league_match_simulation` (silent OK if threads missing) |
| F | T | `single_forfeit(illegal_is_home=True)` → 0–3 |
| T | F | `single_forfeit(illegal_is_home=False)` → 3–0 |
| F | F | `double_forfeit()` → 0–0 |

## Forfeit write (settle-once)

Update fixture only if still unplayed:

- scores from `ForfeitOutcome`
- `is_played = true`
- `status = 'forfeit'` (or equivalent terminal)
- `result_type = 'forfeit' | 'double_forfeit'`
- `resolved_by = 'auto_sim'` (DB CHECK from 064 only allows `manual`|`auto_sim`; forfeit is distinguished by `result_type`)
- `played_at = now`

Do **not** grant match XP/coins on forfeit (table result only), matching lifecycle forfeit behaviour.

## Forbidden

- Silent `return` after eligibility failure that leaves `is_played=false` forever
- Sporting forfeit because guild/threads unavailable
- Double application of points for the same fixture

## Matchday advance

After a settle cycle that marks one or more fixtures played, call existing `update_current_matchday` (already at end of `auto_sim_expired_fixtures`).
