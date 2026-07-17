# Contract: Manager of the Matchday

**Feature**: `020-league-dynamics`  
**Economy**: All credits via `apply_club_economy`

## Pure helper — `select_momd_winner(fixtures_with_clubs) → Winner | None`

### Eligibility (Q3=A / D10)

Include fixture iff:

1. `is_played`
2. `resolved_by = 'manual'`
3. Winner club `is_ai = false`
4. Scoreline is a win (not draw)

AI opponent OK. Auto-sim human wins **out**.

### Ranking

1. Margin `|home_score - away_score|` DESC  
2. Winner goals-for DESC  
3. Winner `player_id` ASC (deterministic)

Return none if empty eligible set.

## RPC — `award_manager_of_the_matchday(p_season_id uuid, p_matchday int) → jsonb`

### Preconditions

1. Season exists.
2. All fixtures for `(season_id, matchday)` have `is_played = true` (else raise / return `{status:'pending'}`).
3. Idempotent: if row exists in `league_matchday_manager_awards` for pair → return existing (`status:'already_awarded'`).

### Effects

1. Select winner via rules above (SQL or bot calls pure helper then RPC with club id — prefer **RPC owns selection** for one source of truth).
2. If none → insert nothing; return `{status:'no_eligible'}`.
3. Else:
   - `coins = get_game_config('league_momd_coins')` default 2000
   - `apply_club_economy(player_id, +coins, 0, 'league_momd', 'momd:'||season_id||':'||matchday, meta)`
   - INSERT award row

### Returns

```json
{
  "status": "awarded | already_awarded | no_eligible | pending",
  "player_id": 123,
  "fixture_id": "…",
  "margin": 3,
  "coins": 2000
}
```

### Call site

After matchday fully resolved (auto-sim tick **and** last manual result that completes the MD), before or after Journal standings bump — must run exactly once per MD (UNIQUE + ledger key).

### Journal

Bot posts one short line/embed in Journal when `status='awarded'` only. No MatchDay spam.
