# Contract: SQL `assert_card_action_allowed`

**Feature**: US-42.2 | **Migration**: `075_player_card_state_guards.sql`

## Signature (target)

```sql
assert_card_action_allowed(p_owner_id BIGINT, p_card_id UUID, p_action TEXT) RETURNS VOID
```

## Behavior

1. Lock card row `FOR UPDATE` (and owner as needed).
2. Verify `owner_id = p_owner_id` (except actions that are N/A for non-owners — default raise `Not owner` / ownership fail).
3. If `assert_not_in_match` would fire and action is a mutation → raise MatchLocked family (may `PERFORM assert_not_in_match` for mutations).
4. Derive busy proofs; if conflicting exclusives → raise `state_conflict`.
5. Apply matrix: if Block → raise clear exception including state + action (e.g. `CARD_STATE: Listed blocks drill`).
6. Return void on Allow.

## Wiring policy

- **Must call** from RPCs that audit marks as gaps.
- **May** also call from RPCs already partially guarded (idempotent safety) where cheap.
- Do not remove `assert_card_not_on_transfer_list` where it encodes listing-specific messages — shared assert should be compatible (listed blocks same set).

## Grants / verify

Guard `function:assert_card_action_allowed` with `to_regprocedure('public.assert_card_action_allowed(bigint,uuid,text)')`.

## Non-goals

- Replacing economy debit logic  
- Purchase race locking (42.6) beyond calling assert on seller/buyer card actions  
