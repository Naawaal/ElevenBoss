# Contract: League State Machine Job

**Feature**: `021-league-automation-and-config`  
**Schedule**: Cron **00:05 UTC** daily — `league_state_machine_job(bot)`

## Effective automation

```
global = league_automation_enabled()
guild_flag = guild_config.league_automation_enabled  # NULL | true | false
effective = global AND (guild_flag IS NULL OR guild_flag IS TRUE)
```

Channel required to **open registration** or post digests. Missing channel → set `automation_last_error`, skip open; still run Dynamics tick for active dynamics seasons (no digest).

## Per-run phases (order)

### A. Dynamics tick (all guilds with active `pacing_mode='dynamics'`)

For each such season (skip `paused`):

1. `auto_sim_expired_fixtures(season)`
2. `update_current_matchday` (MoMD + advance / complete + prizes)
3. If season just completed and automation-owned → queue **open registration** (phase C) for that guild
4. If automation effective + channel OK + matchday settled + `last_digest_matchday < completed_md` → **announce digest**, then set `last_digest_matchday`

### B. Close registration windows

For each `status=registration` with `config_json.automation=true` and `now >= registration_closes_at`:

- Count registered humans (`league_members` / registration roster — same source as admin start).
- If `count >= league_min_humans` → call shared **start Dynamics season**; announce schedule.
- Else → fail registration (delete or status completed + marker); announce under-min; set `next_auto_registration_at = next_monday_00_05_utc(now)`.

### C. Open registration

For each guild where `effective` and channel resolvable and no `active`/`registration` season and (`next_auto_registration_at` IS NULL OR `now >= next_auto_registration_at`):

- Insert registration season: `automation=true`, `registration_closes_at = now+48h`, clear `next_auto_registration_at`, clear error.
- Announce open + close time + `/league` CTA + role ping.

## Idempotency

- Open only if no conflicting season.
- Start only once past close (registration row still present until started/failed).
- Digest once per matchday via `last_digest_matchday`.
- Monday reopen: only when `next_auto_registration_at` elapsed.

## Folding 020 tick

Unregister `dynamics_daily_tick_job` from `main.py`. All Dynamics auto-sim lives here.
