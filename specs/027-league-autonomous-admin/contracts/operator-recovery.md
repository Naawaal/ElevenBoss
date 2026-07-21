# Contract: Operator Recovery

**Feature**: `027-league-autonomous-admin`

## Principle

Emergency recovery is **not** a Discord admin feature. Trusted operators retry work through the **same** `LeagueLifecycleEngine` / recovery / outbox paths used by automation.

## Allowed mechanisms (V1)

| Mechanism | Role |
|-----------|------|
| APScheduler wake (~5 min) | Calls stalled-op recovery + `process_due_transitions` + outbox publish |
| Bot startup recovery | Same catch-up path |
| `scripts/league_lifecycle_recover.py` | Manual operator invocation of the same three steps |

## Script contract

```text
scripts/league_lifecycle_recover.py [--guild-id GUILD_ID]
```

Behavior:

1. Authenticate with service/server credentials (env) — never Discord interaction tokens from a guild admin session.
2. Optionally scope to one guild; default = all V1-eligible guilds (same as wake).
3. Run `recover_stalled_operations` then `process_due_transitions` then outbox publish.
4. Every competitive transition continues to require an **idempotency key** and SHOULD append **transition journal** rows with trigger distinguishing `scheduler` vs `startup` vs `operator_recover`.
5. Exit non-zero on hard failure; print summary counts (ops recovered, transitions run, outbox published/failed).

## Forbidden recovery actions

Operator tooling MUST NOT:

- `UPDATE` standings, scores, or prize ledger rows directly
- Re-pay rewards or re-apply promotion outside engine settle
- Convert a living season’s `ruleset_version` / pacing mode to another ruleset
- Expose equivalent controls via Discord (including “owner-only” slash commands)

## Retry / stuck / alerts

- Transient failures: retryable ops delete/re-acquire per existing engine semantics.
- Stalled `started` operations: mark failed / requeue per `league_recovery` rules; wake must run this regularly (not startup-only).
- When retry limits are exceeded: structured ERROR log including `guild_id`, `operation_key`, season id — sufficient for ops alerting in V1.
- Discord guild admins receive no bypass button when alerts fire.

## Pause / cancel (optional operator)

If later exposed on the CLI:

- Must call `pause_season` / `resume_season` / force-cancel **engine** methods only
- Must journal + use operation keys where applicable
- Must not appear in Discord

V1 script MAY omit pause/cancel and ship wake/retry only.
