# Contract: League Time Settings

**Feature**: `027-league-autonomous-admin`

## Navigation

```text
/admin → Server Settings → League Time
```

## Fields

| Field | Input | Stored |
|-------|-------|--------|
| Timezone | IANA id (e.g. `Asia/Kathmandu`) | `guild_config.league_timezone` |
| Daily resolution time | Local time; V1 hour `0–23` (e.g. `20` or `20:00` → hour 20) | `guild_config.league_resolution_hour_local` |

## Validation

1. Resolve timezone with installed tz database (`zoneinfo`).
2. Reject raw offsets: patterns such as `UTC+5:45`, `UTC-04:00`, `GMT+1`, bare `+0545`.
3. Reject unknown IANA names with a clear ephemeral error.
4. Hour must be in `0..23`.

## Preview (required copy shape)

On view and after successful save, show meaning equivalent to:

```text
League matches will resolve daily at {local_time} {timezone}.
Current UTC equivalent: {utc_time} UTC.
This change will apply from the next season.
```

If guild settings are NULL (defaults in effect), preview MUST state that defaults (`UTC`, `00:00`) are active and that configuring League Time applies from the next season.

## Persistence rules

- Upsert **only** `guild_config` League Time columns.
- MUST NOT update `league_seasons.timezone`, `resolution_hour_local`, `ruleset_snapshot`, `phase_deadlines`, or any `league_matchdays` / fixture windows for an active/living season.
- MUST NOT write `league_lifecycle_v1_enabled` from this UI.

## Engine consume rules

At season preparation:

1. Read guild League Time columns.
2. Coalesce NULL → `UTC` / `0`.
3. Freeze effective values onto the season snapshot and precompute UTC windows (per `026` DST rules).
4. MUST NOT fail preparation solely because League Time was never configured.

## Defaults

| Setting | Default when unconfigured |
|---------|---------------------------|
| Timezone | `UTC` |
| Resolution hour | `0` (`00:00` local) |

Defaults MUST NOT block lifecycle progression. Optional admin notice is non-blocking.
