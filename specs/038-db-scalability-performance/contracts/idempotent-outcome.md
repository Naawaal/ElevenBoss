# Contract: Idempotent Outcome (FR-006a)

**Parent**: [../spec.md](../spec.md) | **Related**: [../../029-game-integrity/contracts/idempotency-anchor-map.md](../../029-game-integrity/contracts/idempotency-anchor-map.md)

## Purpose

Managers must never see a **false failure** when a mutation already committed (successful retry / dropped HTTP response). Invokes INV-08 with explicit UX.

## JSON envelope (canonical)

```json
{
  "status": "applied | already_applied | rejected",
  "reason": null,
  "data": {}
}
```

| `status` | Meaning | UI |
|----------|---------|-----|
| `applied` | First durable success for this key | Success embed from `data` |
| `already_applied` | Key seen before; no second grant | **Success** (or “already done”) using `data` — **not** an error |
| `rejected` | Business rule failed (insufficient coins, cooldown, etc.) | Friendly ephemeral error from `reason` |

`data` MUST include fields needed to refresh the hub (balances, granted items, cooldown timestamps, etc.) for both `applied` and `already_applied`.

## Mapping from legacy economy JSON

| Legacy field | Canonical |
|--------------|-----------|
| `replay: true` (and success body) | `status: already_applied`, map body → `data` |
| `replay: false` / first success | `status: applied` |
| Raised SQL / PostgREST error on unique violation for known key | **Forbidden** for FR-006a paths — catch inside RPC and return `already_applied` |

## Python adapter

`apps/discord_bot/core/idempotent_outcome.py`:

- `parse_idempotent_outcome(raw: dict) -> IdempotentOutcome`
- Used by touched cogs after RPCs; Phase 1 may wrap `apply_club_economy` results without changing SQL signatures.

## Phase gates

| Phase | Requirement |
|-------|-------------|
| 1 | Adapter + use on at least one hot mutation path; document map |
| 2 | `claim_daily_pack` (and other gap list items) return envelope natively |
| 3+ | All interactive mutations in multi-instance deploy obey envelope |

## Test anchors

- Replay same key twice → second `already_applied`, balances unchanged vs first.
- Dropped-response simulation → UI treats second click as success.
- Reject path still shows friendly reason (not stack trace).
