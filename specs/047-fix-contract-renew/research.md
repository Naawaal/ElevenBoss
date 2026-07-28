# Research: Fix Contract Renew (`047`)

**Date**: 2026-07-28  
**Spec**: [spec.md](./spec.md)

## R1 — What broke?

**Decision**: Treat permanent idempotency key `contract_renewal:{card_id}` inside `renew_contract` (migration `047_audit_remediation.sql`) as the sole root cause of “renew does nothing / false success.”

**Evidence**:
- Roy Thompson (`854ec9e5-…`): ledger row 2026-07-14 with that key; expiry 2026-07-21; later renews replay and skip `UPDATE contract_expires_at`.
- ~10 human past-grace cards share “prior renew + still past grace.”
- Past-grace **match gate** is correct behaviour when expiry is stale.

**Alternatives considered**: Blaming Discord button `custom_id`, age gate, or grace math — secondary at most; RPC replay is sufficient to explain stuck renews.

---

## R2 — Idempotency key redesign

**Decision**: Use a **per-attempt** key:

```text
COALESCE(
  client p_idempotency_key,
  'contract_renewal:' || card_id || ':' || YYYYMMDDHH24MI  -- UTC minute bucket
)
```

- **New intentional renew** (next minute or new client UUID) → new ledger row → charge → extend.
- **Double-tap / HTTP retry** same minute (or same client UUID) → replay → no double charge.
- **Old permanent keys** remain in `economy_ledger` but are never reused → stuck cards self-heal on next renew.

**Alternatives considered**:

| Option | Why rejected / deferred |
|--------|-------------------------|
| Delete old ledger rows | Ops risk; unnecessary once key format changes |
| Daily bucket only | Blocks two legitimate renews same UTC day (edge but real for testing) |
| No idempotency key | Violates economy integrity / double-charge on retry |
| Only client UUID | Fine, but server default keeps old bot callers safe if they omit the arg |

---

## R3 — RPC signature & return type

**Decision**:
1. `DROP FUNCTION` old `(bigint,uuid,bigint,integer)` overload.
2. Recreate with `p_idempotency_key TEXT DEFAULT NULL` (5th arg optional).
3. Keep **`RETURNS BOOLEAN`** for minimal churn.
4. Bot **re-fetches** `contract_expires_at` after call for honest UI (FR-004/005).

**Alternatives considered**: JSONB envelope with `new_expires_at` — nicer, deferred unless BOOLEAN+refetch proves awkward.

---

## R4 — Replay branch behaviour

**Decision**: On economy `replay`, RPC may still `RETURN TRUE` (same-attempt retry). Bot must **not** celebrate if card remains past grace; show error asking to retry (or show that nothing changed). Prefer this over silently extending on replay without charge (would desync ledger).

**Rationale**: Replay means “this attempt already paid.” Extending again on replay without a new payment would be a free extend exploit if keys collide wrongly; minute/UUID keys make collisions intentional duplicates only.

---

## R5 — Discord UI honesty

**Decision**: In `PlayerProfileView.renew_callback`:
1. Generate `uuid4()` as `p_idempotency_key` per click (preferred) **or** rely on server minute key.
2. Call RPC.
3. Reload card expiry + `contract_grace_days`.
4. If `contract_blocks_xi(...)` still true → `error_embed` (renew did not clear past grace).
5. Else success embed including new expiry timestamp.

Optional polish: stop using fixed `custom_id="renew_contract_profile"` (use unique/none) so stale views fail cleanly — not required for P1.

---

## R6 — Ops recovery

**Decision**: Primary recovery = apply migration + bot deploy + manager renews on `/player-profile`.  
Document optional emergency SQL in quickstart: call fixed `renew_contract(...)` once for a card (still charges coins). **Do not** delete ledger rows as the default path.

---

## R7 — Migration number

**Decision**: `087_fix_contract_renew_idempotency.sql` (after `086_marketplace_intelligence.sql`). Extend `verify_required_schema.sql` only if the function signature guard still expects the 4-arg overload — update to 5-arg with default.

---

## Resolved clarifications

No open `NEEDS CLARIFICATION` items — defaults above match the approved spec.
