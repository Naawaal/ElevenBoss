# Contract: Club finances soft-deprecation

## Surface

- **Keep**: `/club-finances` slash command (`economy_cog.py`)
- **Add**: Profile hub **Finances** button → same content as a sub-view
- **Pointer**: Slash response must mention unified dashboard on `/profile`

## Shared builder

Extract a single embed (and optional view) builder used by:

1. `/club-finances` followup send
2. Profile **Finances** → `edit_message` / `edit_original_response` with **Back to Profile**

### Required fields (parity with today)

- Wallet: coins + gems (`tokens`)
- Starting XI wage forecast via `calculate_weekly_wages` (not auto-deducted copy)
- Facility levels line: YA · Training Ground · Hospital

### Explicitly out of scope

- `economy_ledger` transaction browser
- New finance slash aliases

## Soft-deprecation copy

On `/club-finances` embed footer or description, include a short line such as:

> Unified club dashboard (finance + hospital): `/profile`

Do **not** delete or rename the command in v1.

## Guarantees

- Functional parity between slash and Finances button content
- No coin mutations from this read-only surface
