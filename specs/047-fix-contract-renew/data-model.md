# Data Model: Fix Contract Renew (`047`)

**Storage**: No new tables or columns. Behaviour change only on `renew_contract` + ledger **key strings**.

## Existing entities (unchanged shape)

### `player_cards`

| Field | Role in renew |
|-------|----------------|
| `id` | Card identity |
| `owner_id` | Must equal `p_club_id` |
| `date_of_birth` / age helpers | Block renew if age ≥ `retirement_warning_age` (35) |
| `is_retired` | Must be false |
| `contract_expires_at` | Extended on successful non-replay renew |

### `economy_ledger`

| Field | Role |
|-------|------|
| `idempotency_key` | Unique when present; **new** renews use per-attempt keys |
| `source` | `contract_renewal` |
| `amount` | Negative coin debit (`-p_cost`) |

Legacy rows with `contract_renewal:{uuid}` (no time suffix) remain historical; they must not block new keys.

### `game_config`

| Key | Default | Role |
|-----|---------|------|
| `contract_renewal_days` | 7 | `p_extension_days` from bot |
| `contract_grace_days` | 7 | Past-grace UI / squad gate (unchanged) |
| `retirement_warning_age` | 35 | Renew blocked at/above |

## Renew attempt (logical)

| Attribute | Rule |
|-----------|------|
| Attempt key | Client UUID **or** `contract_renewal:{card_id}:{UTC_YYYYMMDDHH24MI}` |
| Charge | Once per distinct attempt key |
| Expiry update | Only on non-replay economy path |
| Success (player-facing) | Expiry not past grace after renew (bot verifies) |

## State transitions

```text
[Past grace / in grace / active]
        │ renew (new attempt key)
        ▼
  apply_club_economy(-cost)
        ├─ replay → no expiry change → UI must not claim extension if still past grace
        └─ fresh  → expiry = max(now, old_expiry) + days → playable if not past grace
```

## Non-entities

- No `contract_renewals` table
- No backfill migration of old keys
