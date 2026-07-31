# Quickstart: Fix League Expired Auto-Sim (`048`)

## Prerequisites

- Bot can reach the guild; season #2 (or test season) `pacing_mode=legacy`, `status=active`
- Known pending fixtures (e.g. Bhavs vs Majestic AI; MANCHESTER vs Dragon Club) still unplayed **before** deploy smoke

## 1. Unit checks

```powershell
pytest tests/test_league_expired_settle.py tests/test_double_forfeit_standings.py -q
```

Expect: decision matrix + forfeit scorelines green.

## 2. DB snapshot (before)

```sql
SELECT id, is_played, home_score, away_score, result_type, resolved_by, window_end
FROM league_fixtures
WHERE season_id = 'eea8660e-7e50-461d-b9ce-78f8299b96fc' AND matchday = 5
ORDER BY is_played, window_end;
```

## 3. Deploy bot with settle helper

Restart bot so hub-on-open / 10-min job load new code.

## 4. Discord smoke

1. `/league hub` in the guild (triggers auto-sim for legacy).
2. Open **Fixtures** for Matchday 5.
3. Expect former Pending rows to show scores — either Full Time (sim) or **Forfeit** / **Double Forfeit**.
4. Hub matchday should advance when all MD5 fixtures are played (or after next settle + `update_current_matchday`).

## 5. Integrity checks

- Re-open hub: scores unchanged (settle-once).
- Guild leave / unreachable: must **not** mass-forfeit; pause/skip only.
- Club with past-grace XI: forfeit against that side (or double if both bad), not infinite Pending.

## 6. Changelog

Add a short `change_log.md` note: expired league fixtures now resolve; if your XI is illegal after the window (e.g. expired contracts), the match is forfeited 3–0 rather than stuck pending.
