# Data Model: Game Integrity Remainder

Informative — mostly overlays and catalogs, not new core entities.

## Marketplace listing (existing)

| State | Terminal? | Card effect |
|-------|-----------|-------------|
| `active` | No | Listed (busy) |
| `sold` | Yes | Buyer owns |
| `cancelled` | Yes | Seller roster |
| `expired` | Yes | Seller roster |

**Purchase**: atomic RPC; listing row `FOR UPDATE`; economy keys per listing.

## Registry entry (logical — W7 doc)

| Field | Meaning |
|-------|---------|
| `id` | Stable slug e.g. `match_bot_payout` |
| `direction` | faucet \| sink \| transfer |
| `asset` | coins \| energy \| tokens(N/A) |
| `pipeline` | `apply_club_economy` / RPC name |
| `idempotency_key` | Pattern string |
| `owner` | Spec / module |
| `notes` | Soft gaps |

## Job definition (logical — W8 doc)

| Field | Meaning |
|-------|---------|
| `name` | Scheduler job id |
| `module` | `apps/discord_bot/tasks/...` |
| `schedule_intent` | Human schedule |
| `run_key` | Durable uniqueness |
| `catch_up` | Rule on miss |
| `owner` | Feature |

## Job run

Existing: `league_operation_runs`, RPC idempotency, or job-local logs — catalog cites which.

## RpcContract (W9)

Checklist proof, not a table.

## EdgeCase / ThreatCase (W10)

Catalog rows: id, category, expected, recovery.

## Relationships

```text
Listing --purchase--> Economy ledger (buyer + seller keys)
JobDefinition --executes--> JobRun / RPC
RegistryEntry --documents--> Economy ledger reasons
```
