# Research: Daily Drill Cap Desync

**Feature**: `013-daily-drill-reset` | **Date**: 2026-07-12

---

## R1 — Why UI can show 6/20 while the toast says “club limit 20”

**Decision**: Treat **mis-mapped per-card limit errors** as a primary, confirmed bug; still ship soft-reset/display alignment for real counter drift.

**Evidence**:
- RPC per-card raise: `'Daily drill limit reached for this player (max % per day)'`
- Club raise: `'Daily drill limit reached'`
- `api_error_message` falls through to `if key in raw` over `_FRIENDLY` in **insertion order**. The shorter club key is listed **before** the per-card key, so the per-card exception matches the **club** friendly string.
- Hub shows raw `daily_drill_count` (e.g. 6) — consistent with club capacity remaining while **that card** is at 5/5.

**Alternatives**:
| Option | Rejected because |
|--------|------------------|
| Only fix soft-reset, ignore mapping | Leaves the reported UX intact for the common per-card case |
| Change SQL exception text only | Still need robust matching; mapping fix is smaller and covers current prod strings |

---

## R2 — Soft-reset display vs gate

**Decision**: Add pure `effective_daily_drill_count` and use it in Training Drills; select `daily_drill_reset_at`.

**Rationale**: Spec FR-001. Today the hub never soft-resets for display, so after UTC midnight (before any successful drill) managers can see yesterday’s 20/20 even when the next RPC would allow — or other confusing states.

---

## R3 — Align `process_stat_drill` null handling with recovery

**Decision**: In migration `058`, replace soft-reset with:

```sql
IF v_reset IS NULL OR v_reset < CURRENT_DATE THEN
    v_daily := 0;
    v_reset := CURRENT_DATE;
END IF;
```

Same as `process_recovery_session` (055). Keep writing `daily_drill_count` / `daily_drill_reset_at` on success.

**Rationale**: `NULL < CURRENT_DATE` is unknown in SQL → branch skipped → NULL reset_at + high count permanently blocks skill drills while recovery might still soft-reset.

---

## R4 — Stuck-column repair source of truth

**Decision**: Today’s true club uses ≈ `SUM(player_drill_daily_log.count)` for the owner’s cards where `drill_date = CURRENT_DATE` (capped at 20). Set `daily_drill_count` to that sum and `daily_drill_reset_at = CURRENT_DATE` when:
- `reset_at < CURRENT_DATE` (or null) → force count 0 (or sum for today, usually 0), or
- `reset_at = CURRENT_DATE` and `daily_drill_count` ≠ sum (especially count ≥ 20 and sum &lt; 20).

**Rationale**: Spec FR-005 — don’t blind-zero and gift free drills if they already logged uses today. Log rows are written inside the same transactional RPC as successful attempts (failed RPC rolls back), so sum is a fair proxy.

**Caveat**: Historical partial bugs outside transactions are out of scope; document in quickstart.

---

## R5 — Nightly persist in `process_daily_recovery`?

**Decision**: **Skip for MVP** (YAGNI). Lazy RPC reset + display helper + repair is enough. Optional follow-up: zero counts where `reset_at < CURRENT_DATE` inside daily job.

**Rationale**: Spec FR-008 marks nightly as optional; user’s diagnosis that fatigue recovery “removed” drill reset is incorrect.

---

## Spec reconcile on implement

- Note AC for drill soft-reset + error mapping in `.specify/specs/v1.0.0/spec.md`
- `change_log.md`: short “drill limit message / daily counter” note if player-visible
