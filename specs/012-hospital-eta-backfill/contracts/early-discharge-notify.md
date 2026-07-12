# Contract: early-discharge manager notify

**Surface**: Ops scratch script (preferred) or one-shot bot helper — **not** a slash command.

## Input

`early_discharged` entries from `backfill_injury_eta_fairness()`:

- `owner_id` (Discord snowflake)
- `player_card_id`
- `name`
- `tier`

## Behavior

1. Group by `owner_id`.
2. For each owner with ≥1 early discharge, best-effort DM:

```text
🏥 Medical Update: <Name>[, <Name>…] discharged early due to advancements in our medical protocols.
Check /profile → Manage Hospital if you need the latest roster status.
```

3. On DM failure (closed DMs, fetch error): log and continue; **do not** re-open injury.
4. Bot clubs / invalid owners: skip silently.
5. Shorten-only (no early discharge): **no** DM required.

## Wiring

- Call **after** migration apply / RPC commit.
- Do not register a persistent view or scheduler job for this.
- Optional: delete/archive the notify script after production run (keep in repo for staging replay).
