# Feature Specification: Daily Drill Cap Desync Fix

**Feature Branch**: `013-daily-drill-reset`

**Created**: 2026-07-12

**Status**: Implemented

**Input**: User description: "Training Drills UI shows Daily Drills 6/20 and energy/recovery copy, but running a drill/recovery fails with 'You've hit today's club drill limit (20). Try again tomorrow.' Suspected stale daily counter not reset at UTC midnight after recovery/fatigue RPC work; proposed fixing process_daily_recovery and manually zeroing a clubs.daily_drills_used column."

## Background & Motivation

Managers see **6/20** (or another under-cap number) on the Training Drills hub, then get blocked by the club drill gate as if they were at **20/20**. That is a trust-breaking desync between what the hub displays and what the mutation RPC enforces.

### What is true in ElevenBoss (correcting the proposed diagnosis)

- Club drill usage lives on **`players.daily_drill_count`** with day boundary **`players.daily_drill_reset_at`** (DATE, UTC via Postgres `CURRENT_DATE`). There is **no** `clubs.daily_drills_used` column.
- Skill drills and Recovery Sessions share the **same** club cap (20) and per-card log (`player_drill_daily_log`, max 5/card/day).
- Day rollover is designed as a **lazy soft-reset inside drill RPCs** (`process_stat_drill`, `process_recovery_session`): if `daily_drill_reset_at < CURRENT_DATE` (and null-safe variants), treat count as 0 for that call, then write count+1 and today’s reset date.
- **`process_daily_recovery`** is the fatigue / Hospital discharge job. It was **not** the historical owner of drill-counter reset. Blaming its 009/054 rewrite for “removing midnight drill resets” is the wrong root story — but managers still need the **display and gate to use one rule**, and stuck rows need a repair path.

Likely failure modes to cover (product outcomes, not implementation guesses):

1. Hub reads raw `daily_drill_count` **without** applying the same UTC day soft-reset the RPC uses → wrong “used today” number.
2. Soft-reset logic differs across RPCs (e.g. null `daily_drill_reset_at` handled in one path and not another) → one action blocked while another would allow.
3. Soft-reset happens only in memory and a failed call never persists → column stays high across the day while true “today” usage is lower (or the reverse after partial writes).
4. Column is stuck high with `reset_at` already “today” while today’s real usage (from drill log) is lower → gate blocks even though the hub looks fine if it were recomputed.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Hub Count Matches the Gate (Priority: P1)

As a manager, the Daily Drills `used/20` on Training Drills is the same number the server uses when I run a Skill Drill or Recovery Session on that UTC day.

**Why this priority**: Desync is the reported bug; fixing display+gate alignment is the core fix.

**Independent Test**: With a club whose stored count/reset date imply “new UTC day” or “mid-day usage,” open Training Drills and attempt a drill; displayed used count and allow/deny match.

**Acceptance Scenarios**:

1. **Given** it is a new UTC calendar day relative to the club’s last drill reset date, **When** I open Training Drills, **Then** Daily Drills shows **0/20** (not yesterday’s leftover count).
2. **Given** I have successfully completed N club drills/recoveries today under the shared cap, **When** I open Training Drills, **Then** Daily Drills shows **N/20**.
3. **Given** the hub shows used &lt; 20 for today, **When** I run an otherwise-valid Skill Drill or Recovery Session, **Then** I am **not** rejected solely for the club drill limit of 20.
4. **Given** the hub shows **20/20** for today, **When** I try another club drill/recovery, **Then** I get the club-limit message and no partial charge.

---

### User Story 2 - All Drill Pipes Soft-Reset the Same Way (Priority: P1)

As a manager, Skill Drills and Recovery Sessions apply the same UTC day boundary and shared 20-cap rules so I cannot be blocked on one path while the other would still allow under the same club state.

**Why this priority**: Recovery and skill drills share capacity; inconsistent reset is a silent trap.

**Independent Test**: Same club state; attempt both action types across a simulated day boundary; both reset and increment the shared club counter consistently.

**Acceptance Scenarios**:

1. **Given** last reset date is before today (UTC), **When** I run either a Skill Drill or a Recovery Session, **Then** the action counts as the first use of the new day (not blocked by yesterday’s 20).
2. **Given** missing/unknown last reset date, **When** either action runs, **Then** the club is treated as needing a fresh day boundary (not permanently stuck at the cap).
3. **Given** a successful action after soft-reset, **When** I reopen Training Drills, **Then** the stored club state reflects today’s count (display stays correct without relying on a hidden in-memory-only reset).

---

### User Story 3 - Stuck Clubs Can Be Unblocked (Priority: P2)

As a manager (or ops), if a club is already stuck mid-day with a false “at 20” gate while true today’s usage is lower, there is a safe one-time repair so play can resume without waiting for another calendar day.

**Why this priority**: Unblocks live managers immediately; does not replace the systemic fix.

**Independent Test**: Seed or identify a stuck club; run repair; hub and next drill agree under the true remaining capacity.

**Acceptance Scenarios**:

1. **Given** a club blocked by the club drill limit while today’s real usage is below 20, **When** the repair runs, **Then** the club can drill again up to the true remaining slots for today.
2. **Given** the repair runs, **When** it completes, **Then** it does **not** grant free drills beyond the real remaining capacity for today (no wipe that ignores today’s successful drills/recoveries).
3. **Given** a healthy club already aligned, **When** repair is re-run, **Then** it is a no-op or leaves them correctly capped (idempotent / safe).

---

### Edge Cases

- UTC midnight boundary: soft-reset uses the same “today” as drill logs (`CURRENT_DATE` / UTC day).
- Per-card cap (5) remains separate; its error must stay the per-card message, not the club-limit message.
- Bot clubs with drill RPCs: same rules.
- Concurrent double-tap: still cannot exceed 20 successful club uses in a day.
- Energy/coin failures after a soft-reset decision must not strand managers in a permanent false 20 if that was a contributing bug — persisted state after the day boundary must be coherent.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Training Drills Daily Drills display MUST use the **same UTC day soft-reset rule** as the club drill gate (so used/20 never implies remaining capacity the RPC will deny for club-cap reasons alone).
- **FR-002**: `process_stat_drill` and `process_recovery_session` MUST apply identical club soft-reset + cap-20 rules (including null/missing reset date).
- **FR-003**: After a successful drill/recovery that soft-resets the day, persisted `daily_drill_count` / `daily_drill_reset_at` MUST reflect the new UTC day so the next hub open matches.
- **FR-004**: Per-card daily limit (5 via `player_drill_daily_log`) MUST remain enforced and MUST keep distinct player-facing copy from the club limit.
- **FR-005**: A one-time (or idempotent ops) repair MUST realign stuck clubs whose persisted club count falsely blocks under today’s true usage, without erasing today’s real successful uses.
- **FR-006**: Do **not** introduce a `clubs.daily_drills_used` column or move drill caps onto a non-existent clubs table.
- **FR-007**: No new slash commands or hubs; fix existing `/development` Training Drills + existing RPCs/ops script only.
- **FR-008**: Optional hygiene: a daily job may **persist** soft-resets for all clubs at UTC day change, but MUST NOT be the only place the gate works — lazy RPC reset remains correct if the job lags.

### Key Entities

- **Club drill counter**: `players.daily_drill_count` + `players.daily_drill_reset_at`.
- **Per-card drill log**: `player_drill_daily_log` for the UTC day.
- **Shared drill actions**: Skill Drill and Recovery Session.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In reproduction (reset date yesterday, count 20), hub shows **0/20** after open (or after first successful soft-reset path), and a valid drill is allowed.
- **SC-002**: Zero reports of “hub shows used &lt; 20 but club limit 20 error” after ship for the same interaction session.
- **SC-003**: Skill Drill and Recovery Session agree on allow/deny for the same club counter state.
- **SC-004**: Stuck-club repair restores remaining capacity equal to `20 − today’s true club uses` (within rounding of how “true uses” is defined in the plan).
- **SC-005**: Re-running repair on healthy clubs does not inflate remaining drills above 20 − true uses.

## Assumptions

- Cap remains **20 club drills/recoveries per UTC day** and **5 per card per UTC day**.
- Postgres `CURRENT_DATE` (UTC on hosted Supabase) remains the day boundary.
- User’s pasted SQL against `clubs` is **illustrative only** and must be rewritten to ElevenBoss schema in plan/implement.
- Immediate manual unblock for one manager is allowed via ops SQL/script against `players` (and/or reconciling from today’s drill log), documented in quickstart — not a player-facing command.
- The earlier “process_daily_recovery ate the reset” narrative is **incorrect as stated**; this feature still may add optional nightly persist for hygiene without making fatigue recovery the source of truth for drill caps.

## Out of Scope

- Changing the 20 or 5 caps.
- New Store items or drill energy economy retunes.
- Redesigning Training Drills UI layout.
- Rewriting fatigue/Hospital logic in `process_daily_recovery` beyond optional counter hygiene.
- New Discord slash commands.
