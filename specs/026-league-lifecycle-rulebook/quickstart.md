# Quickstart: League Lifecycle Rulebook V1

**Feature**: `026-league-lifecycle-rulebook`  
**Purpose**: Validate the rulebook engine end-to-end on a pilot guild after implementation.

## Prerequisites

- Migration `070_league_lifecycle_v1.sql` applied; `verify_required_schema.sql` passes
- Pilot Discord guild with bot admin, announce channel, mention role
- Guild `league_timezone` + `league_resolution_hour_local` set in `/admin`
- Global + guild `league_lifecycle_v1_enabled` effective
- No living 020/021 open season on that guild (or wait until it completes)

## Pure tests (no Discord)

```bash
pytest tests/test_league_schedule_windows.py \
       tests/test_double_forfeit_standings.py \
       tests/test_assistant_lineup_priority.py \
       tests/test_lifecycle_idempotency.py \
       tests/test_pause_resume_rebase.py \
       tests/test_cutover_grandfathering.py -q
```

Expected: DST gap/overlap fixtures green; double_forfeit deltas match contract; 100× `process_due_transitions` idempotent.

## Smoke (DB)

```bash
python scratch/apply_migration_070.py
python scratch/smoke_league_lifecycle_v1.py
```

Expected: season statuses, operation_keys uniqueness, sample prepare→activate windows stored in UTC.

## Pilot cycle (shortened hours optional via game_config for test)

1. Enable cutover on pilot guild; confirm `/admin` shows TZ/hour.  
2. Open registration (auto wake-up or shared admin transition).  
3. Register ≥4 humans via `/league`.  
4. After lock: preparation charges deposit, seats 8-club table, publishes 14 matchdays with local-hour deadlines.  
5. Leave one fixture unplayed until after `window_end` → assistant resolves; illegal both sides → double_forfeit.  
6. Pause mid-matchday for >1 hour → resume → confirm unresolved windows shifted, not instantly expired.  
7. Complete / force-sim remaining matchdays → settlement writes `league_final_standings`, prizes once, promo once.  
8. Offseason elapses → next registration opens without admin Start.  
9. Kill bot for 6+ hours past a deadline → restart → catch-up settles once (SC-004).

## Pilot walkthrough notes (implementation)

| Step | What to watch | Pass criteria |
|------|---------------|---------------|
| Cutover | `guild_config.league_lifecycle_v1_enabled` + global flag | New seasons get `pacing_mode=lifecycle_v1` |
| Open reg | `/admin` Open Registration **or** 5‑min wake-up | Status `registration_open`; outbox `registration_open` |
| Register | `/league` Register | Row in `league_registrations` |
| Lock/prep | Wake-up after `registration_end` | `registration_locked` → `preparing` → fixtures + `league_matchdays` UTC windows |
| Deadline | Unplayed past `window_end` | Fixture `is_played`; seed persisted; forfeit uses `result_type` |
| Pause | Admin Pause / Resume | Windows rebase by pause duration |
| Force End | Admin Force End on V1 | Status `cancelled` — **no** prizes |
| Dynamics guild | Non-cutover season | Dynamics tick only; no V1 status rewrite |

**Follow-ups (do not invent dual modes):** live Discord pilot not executed in CI — run the table above on a cutover guild before broad rollout. Shortened `game_config` hours are fine for QA.

Integrity fixes applied post-T057 (still no dual modes):
- Fixture resolve / season settle ops are **retryable** (failed lease cleared; recovery deletes burned `fixture:*:resolve` keys for unplayed fixtures).
- Returning `league_members` can register into `league_registrations` during `registration_open`.
- Hub `fetch_standings` uses `apply_fixture_to_row` (double_forfeit = L / 0 pts, not draw).
- Deadline resolve acquires club match locks; prepare seats fixtures for **all** tiers; `preparation_end` set (+24h).

## Regression checks

- Non-cutover guild with Dynamics season: windows unchanged; no V1 status rewrite.  
- Weekly Division Rank still updates only from `/battle bot`.  
- No new player slash commands in command tree.  
- Discord channel delete: season still settles; outbox retries/fails soft.

## References

- [lifecycle-transitions.md](./contracts/lifecycle-transitions.md)
- [matchday-schedule.md](./contracts/matchday-schedule.md)
- [fixture-resolution.md](./contracts/fixture-resolution.md)
- [cutover-and-rollback.md](./contracts/cutover-and-rollback.md)
- [data-model.md](./data-model.md)
