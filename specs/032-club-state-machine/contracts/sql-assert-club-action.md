# Contract: SQL `assert_club_action_allowed`

**Feature**: US-42.3 | **Migration**: `076_club_state_guards.sql`

## Signature (target)

```sql
assert_club_action_allowed(p_club_id BIGINT, p_action TEXT) RETURNS VOID
```

## Behavior

1. Lock `players` row `FOR UPDATE`.
2. If missing → raise not found.
3. If `is_ai` and action is a human hub mutation / `league_join` / `store_faucet` → `CLUB_STATE: AI blocks …`.
4. Optionally refresh soft label via same day math as `classify_club_identity_status` (or require caller to classify first — prefer assert self-classifies for fail-closed join).
5. If action is mutation (not `view_hub`) and MatchLocked applies per matrix → `PERFORM assert_not_in_match(p_club_id)`.
6. If action = `league_join` and soft status ∈ (`inactive`,`abandoned`) → raise `CLUB_STATE: Inactive/Abandoned blocks league_join`.
7. Return void on Allow.

## Grants / verify

`to_regprocedure('public.assert_club_action_allowed(bigint,text)')`.

## Non-goals

- Card busy matrix (075)
- Season calendar / deposit math beyond calling existing helpers if any
