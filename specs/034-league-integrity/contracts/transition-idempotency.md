# Contract: Transition Idempotency

**Feature**: US-42.5

## Pattern

| Layer | Mechanism |
|-------|-----------|
| Lifecycle transitions | `league_operation_runs.operation_key` unique + `_run_once` |
| Fixture settle | `is_played` / active `match_runs` skip |
| Season prizes | Economy idempotency keys + award unique |
| Promotion | `config_json.promo_applied` |

## Rules

1. Second wake with same key → acquire fails → no-op success path for caller.
2. Retryable infra failure MAY delete started row so catch-up can retry — must not double-apply succeeded side effects (rely on lower-level keys).
3. Presentation / outbox retries MUST NOT re-enter prize or fixture settle.

## Acceptance

Double catch-up against frozen “now” → 0 duplicate fixture settlements, 0 duplicate prize ledger rows.
