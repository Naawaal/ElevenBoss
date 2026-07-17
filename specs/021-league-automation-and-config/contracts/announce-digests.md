# Contract: Announce Digests

**Feature**: `021-league-automation-and-config`  
**Channel**: `guild_config.league_channel_id`  
**Ping**: `announcement_role_id` when resolvable (AllowedMentions roles=True)

## Post types

### Registration open

`Season {N} registration is open! Use /league to join. Closes <t:closes:F> (<t:closes:R>).`

### Registration failed (under min)

`Season {N} registration closed — need at least {min} managers (had {n}). Next registration: Monday <t:next:F>.`

### Season start / schedule

Kickoff: Dynamics length, midnight UTC rule, division count; optional short “MD1–MD14” summary or pointer to `/league hub` fixtures (avoid megadump — standings table + first matchday OK).

### Daily tick digest

After settlement for matchday M:

- If MoMD awarded: `🏅 Manager of the Matchday: **Club** (score) — +X coins`
- Standings snapshot: viewer-agnostic — post **each Seasonal Division** table (limit 8–10 rows) or Div1 only if single tier
- Line: `Matchday M complete` / `Matchday M+1 open — play before 00:00 UTC`

Journal MoMD from 020 may still fire — **coins once**; digest is announce-channel copy.

### Season concluded

Champion / promo notes brief + “Registration for Season N+1 is open…” if opened same run.

## Failure

Send failures logged; set `automation_last_error`; do not abort sim/settlement.
