# Contract: Card Ownership History

**Feature**: `043-marketplace-intelligence`  
**Table**: `card_ownership_history` — see [data-model.md](../data-model.md)

## Helpers (SECURITY DEFINER)

### `ensure_card_ownership_open(p_card_id uuid, p_owner_id bigint, p_via text) → void`

- If an open segment exists for `p_card_id`, no-op (optionally assert `owner_id` matches).  
- Else INSERT open segment with `club_name` from `players`, `acquired_via = p_via`, `started_at = now()`.

### Close + transfer (inline or helper)

On successful P2P purchase (after `owner_id` update + sales log insert):

1. UPDATE open segment for card SET `ended_at = now()`, `ended_via = 'p2p_transfer'`, `transfer_sales_log_id = <id>` WHERE `ended_at IS NULL`.  
2. If no open segment existed for seller, optionally INSERT a closed seller segment spanning unknown start → now (YAGNI: prefer `ensure` at list time / lazy UI instead of inventing start).  
3. INSERT open buyer segment: `acquired_via = 'p2p_transfer'`, `transfer_sales_log_id = <id>`, club name snapshot.

### Agent sale

Inside `process_agent_sale`, **before** `DELETE FROM player_cards`:

- Close open segment: `ended_at = now()`, `ended_via = 'agent_sale'`.

### Optional acquisition opens (same migration if REPLACE already done)

- `purchase_scouting_player` → `ensure_card_ownership_open(new_card, buyer, 'scouting')`  
- `sign_youth_scout_prospect` → `ensure_card_ownership_open(new_card, owner, 'youth_scout')`

Pack claim paths: **out of scope**; career UI calls `ensure_card_ownership_open(..., 'legacy_bootstrap')` when zero rows.

## Read

### Manager UI / bot query

- SELECT segments for `card_id` ORDER BY `started_at ASC`.  
- Display `club_name` chain; mark open segment as current.

### RPC (optional convenience)

`get_card_ownership_history(p_card_id uuid) → jsonb`  
Returns ordered array of `{club_name, owner_id, acquired_via, started_at, ended_at, ended_via}`.

## Invariants

- At most one open segment per card (unique partial index).  
- History rows survive `player_cards` deletion.  
- Failed purchases do not close/open segments.

## RLS

Enable + SELECT/INSERT/UPDATE policies for bot roles; writes preferred through SECURITY DEFINER paths.
