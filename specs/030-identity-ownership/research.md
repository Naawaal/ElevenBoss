# Research: US-42.1 Identity & Ownership

**Feature**: `030-identity-ownership`  
**Date**: 2026-07-22  
**Status**: Complete

## R1 — Is INV-01 already enforced?

**Decision**: Largely yes via `players.discord_id` PRIMARY KEY and `register_new_player` pre-check raising `ALREADY_REGISTERED`. **Gap**: EXISTS-then-INSERT race under concurrency can surface as raw unique_violation instead of clean already-registered, and theoretically confuse callers.

**Rationale**: Spec SC-001 requires ≤1 club under concurrent register; UX requires stable `ALREADY_REGISTERED` mapping in `onboarding_cog.py`.

**Alternatives considered**:
- App-only lock — rejected (not durable across processes).
- Leave as-is — rejected (fails integrity bar).

**Fix**: In migration 074, wrap insert path so unique_violation on `players_pkey` (or discord_id) raises `ALREADY_REGISTERED`; optionally `INSERT … ON CONFLICT DO NOTHING` + existence check returning void/raise. Prefer single transaction with exception handler for clarity matching current void return.

---

## R2 — Soft lifecycle: columns now or defer all to US-42.3?

**Decision**: Add **minimal columns + classify/recover RPCs** in US-42.1; keep day thresholds as config or package constants (30/90). Defer heavy scheduler productization / league-seat consequences to US-42.3 / US-42.5.

**Rationale**: Spec FR-014/015 require Inactive/Abandoned without hard delete. Without columns, labels cannot be durable. Automation polish is not required for identity SoT.

**Alternatives considered**:
- Docs-only soft states — rejected (not enforceable).
- Full inactivity job in this child — deferred (YAGNI; 42.3 owns club automation depth).

---

## R3 — How to update `last_qualifying_activity_at`?

**Decision**: Provide RPC `touch_club_activity(p_club_id)` (and/or set Active on touch). Wire **thinly** from one or two central paths (e.g. after successful `apply_club_economy` wrapper and/or match settlement) — not every cog. Document that incomplete wiring is OK for MVP if classify can also use `created_at` / existing logs as fallback; prefer explicit touch for correctness.

**Rationale**: Sprinkling updates in every cog is brittle; central economy wrapper covers most faucets/sinks.

**Alternatives considered**: Trigger on `economy_ledger` insert — possible but heavier; reserved if wrapper miss rate is high.

---

## R4 — Guild leave / bot remove

**Decision**: **Verify-only** for delete absence: `on_guild_remove` → `pause_seasons_for_guild` only. Add contract test/grep that no code path deletes `players` on guild events. Do not add club rows per guild.

**Rationale**: Current code already matches FR-010/011; identity work is proof + freeze, not a rewrite.

**Alternatives considered**: Soft-delete club on leave — rejected (epic + spec forbid).

---

## R5 — Pending rewards / ownership

**Decision**: Treat `claim_pending_level_rewards(p_owner_id)` filtering on `player_cards.owner_id` as already correct (US-24). Add/extend a focused regression test; no RPC rewrite unless audit finds stale `club_id` credit path.

**Rationale**: INV-14 already remediated; US-42.1 makes it a permanent acceptance test.

---

## R6 — AI clubs

**Decision**: `players.is_ai = true` remains the discriminator. `/register` must never set `is_ai`. Classify soft lifecycle applies to humans only (`is_ai = false`).

**Rationale**: Matches INV-15 binding in spec.

---

## R7 — Migration number & package home

**Decision**: `074_identity_ownership.sql`. Pure logic in `packages/player_engine/player_engine/identity.py` (thresholds + classify pure function). No `packages/integrity`.

**Rationale**: Next after 073; player_engine already owns player-domain pure math.

---

## R8 — Hard delete / CASCADE

**Decision**: Keep FK `ON DELETE CASCADE` from cards→players for **intentional** admin/ops deletion only. Product P0 offers no manager-facing delete. Document that guild events must never `DELETE FROM players`.

**Rationale**: Changing CASCADE is out of scope and risky; policy is “don’t call delete.”

---

## Open items (non-blocking)

| Item | Owner |
|------|-------|
| League eligibility when Inactive | US-42.3 / 42.5 |
| Exact qualifying-activity event list completeness | Iterate after touch wiring |
| Manager rename rate limits | Optional polish; not MVP |
