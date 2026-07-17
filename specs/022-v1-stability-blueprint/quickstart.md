# Quickstart: v1 Stability Blueprint

**Feature**: `022-v1-stability-blueprint`  
**Purpose**: Runnable validation that Waves 0–3 exit gates hold. Not an implementation guide.

## Prerequisites

- Repo checkout with editable packages installed (`pip install -e packages/...` as your env already uses)
- `pytest` available
- Optional: `DATABASE_URL` / Supabase for RPC smokes and schema verify
- Discord pilot guild only when testing Select UX / flags (keep production flags default-off)

## Wave 0 — Verify batch

1. Follow [contracts/wave0-verify-greps.md](./contracts/wave0-verify-greps.md).
2. Run the pytest batch listed there.
3. Confirm `apps/discord_bot/main.py` schedules:
   - `league_state_machine_job` cron `00:05` once
   - `auto_sim_expired_fixtures_job` interval 10m (must skip dynamics)
   - **no** second dynamics-only cron
4. Update Issue Registry statuses in [spec.md](./spec.md).

**Pass**: Critical Verify items Closed or explicitly reopened Open with bundle.

## Wave 1 — Money races

| Step | Action | Expect |
|------|--------|--------|
| 1 | `pytest tests/test_transfer_market_race.py -q` | Green |
| 2 | Re-run payroll for same week key (scratch/smoke or SQL) | Second run no extra debit |
| 3 | Force MoMD settle twice for same MD | Coins + award row unchanged |
| 4 | Flag-on automation: attempt Start while owned by job | Hidden/disabled; no duplicate season |

**Pass**: SC-001–SC-003 evidence noted.

## Wave 2 — OVR & match parity

| Step | Action | Expect |
|------|--------|--------|
| 1 | Factory/new-card OVR asserts (pytest) | overall == True OVR |
| 2 | Dry-run `python scripts/fix_inflated_player_stats.py` | Count recorded; disposition chosen |
| 3 | Bot match / league match / friendly checklist | Contracts: bot+league pipes; friendly sandbox |
| 4 | Evolution: one match → progress +1 stage tick only once | No second tick |
| 5 | Evo hub copy vs real cost/slots | No PlayStyle lie; numbers match config |

## Wave 3 — Select UX + edges

| Step | Action | Expect |
|------|--------|--------|
| 1 | Hospital: discharge last patient | Empty-state copy + Back ([select-empty-state](./contracts/select-empty-state.md)) |
| 2 | Academy empty / Transfer filter zero | Same |
| 3 | Walk [edge-case-matrix](./contracts/edge-case-matrix.md) E1–E12 | All Verdicts set |

## Schema guard (any Conditional migration)

```text
# after apply 066_* if used
psql "$DATABASE_URL" -f supabase/scripts/verify_required_schema.sql
# or project’s scratch/verify_schema_full.py equivalent
```

## Done when

Spec SC-001–SC-008 evidence collected; Low-only leftovers listed as backlog; `change_log.md` updated only for manager-visible fixes shipped during the waves.

## Wave Exit Gate checklist (US7)

| SC | Result (2026-07-15 implement) |
|----|--------------------------------|
| SC-001 Critical Closed/Verify-passed | **Pass** — C1–C5 Closed |
| SC-002 Transfer race ≤1 success | **Pass** — race tests green |
| SC-003 Payroll/MoMD no double grant | **Pass** (unit); live re-settle smoke still ops/pilot |
| SC-004 New-card OVR = True OVR | **Pass** — factory batch ≥200; legacy dry-run deferred (no DB) |
| SC-005 Match-type contracts | **Pass** — Wave 0 friendly sandbox + bot rewards path present |
| SC-006 Evolution tick once | **Pass** — no app-level double tick |
| SC-007 Select empty-state | **Pass** — helper + hub wiring + unit test |
| SC-008 E1–E12 Verdicts | **Pass** — High edges Disproven; E10 fixed; remaining Intentional/Disproven; only M4 pilot Suspect left |
| SC-010 No new slash/tables | **Pass** — fix/verify only |
