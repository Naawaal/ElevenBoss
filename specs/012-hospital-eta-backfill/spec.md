# Feature Specification: Hospital ETA Backfill (Post-011 Fair Recalc)

**Feature Branch**: `012-hospital-eta-backfill`

**Created**: 2026-07-12

**Status**: Implemented

**Input**: User description: "Players already in hospital before the 011 injury-base compression still sit on old long ETAs and feel cheated. Ship a one-time fair recalculation: new total days from new bases + current Hospital level, subtract time already served since admission; if already served past the new max, discharge immediately; optionally DM managers on early discharge. Honor time served; never lengthen remaining waits; not a mass free heal."

## Background & Motivation

Feature **011** shortened injury bases (Minor/Moderate/Major → **1 / 4 / 7** days) for *new* admits only (**forward-only**). Managers who already had stars in Hospital keep the old 3 / 8 / 20-based `expected_recovery_date` values and feel punished for playing before the patch.

This feature is a **one-time live-state fairness pass**: apply the new recovery curves to open stays while **crediting days already spent**, early-discharging only when the new rules say the stay should already be over. No blanket instant heal for everyone still under their new total.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Fair Hospital ETA Recalculation (Priority: P1)

As a manager with a player already in Hospital under the old longer clocks, after the fairness pass my Hospital panel shows a shorter (or equal) return date that honors how long they've already been admitted under the new curve—not the old full ETA.

**Why this priority**: Without this, 011 creates two classes of managers and the loudest fairness complaint.

**Independent Test**: Seed an active hospital stay with a known admission time and old far-future ETA; run the one-time pass; confirm new ETA matches “new total − days served” (and never later than the prior ETA).

**Acceptance Scenarios**:

1. **Given** an active hospital patient (no discharge) admitted N days ago under old bases, **When** the fairness pass runs, **Then** their expected return is recalculated as: new total recovery days for their injury tier at the club’s **current** Hospital level, minus days already served since admission (fractional days allowed in the math; display remains calendar ETA).
2. **Given** that recalculation, **When** the new expected return would be **later** than the existing expected return, **Then** the existing earlier date is kept (never lengthen).
3. **Given** a Major (or other) patient whose days already served ≥ new total days under current Hospital level, **When** the pass runs, **Then** they are **discharged as recovered** (cleared from Hospital as healthy / injury resolved the same way a normal on-time discharge would), not left with a zero/negative ETA.
4. **Given** a patient already correctly aligned to the new curve (e.g. pass re-run), **When** the pass runs again, **Then** it is a no-op for that stay (idempotent; no second shortening beyond the formula).
5. **Given** the pass completes, **When** the manager opens Hospital / profile injury UI, **Then** they see the updated return date without needing a new admit.

---

### User Story 2 - Early-Discharge Manager Notice (Priority: P2)

As a manager whose player is discharged early by the fairness pass, I get a clear medical-update notice so I am not surprised when the star is suddenly available.

**Why this priority**: Shortened ETAs are visible in-panel; early discharge needs an explicit ping so it does not feel like a silent bug.

**Independent Test**: Force a stay that is past the new max; run pass; confirm a manager-facing notice is attempted for that club/player.

**Acceptance Scenarios**:

1. **Given** at least one of my players is early-discharged by the pass, **When** notifications run, **Then** I receive a Medical Update style message naming the player(s) and that they were discharged early under updated medical protocols.
2. **Given** my DMs are disabled or delivery fails, **When** the pass finishes, **Then** the discharge still persists in Hospital/squad state; notification failure must not roll back the fairness data changes.
3. **Given** only ETA shortenings (no early discharge), **When** the pass runs, **Then** no mandatory mass DM is required (panel ETA update is enough).

---

### User Story 3 - Overflow Untreated Clocks Stay Fair (Priority: P2)

As a manager with an injured player **not** in a Hospital bed (overflow / untreated) still sitting on an old long untreated day count, the same fairness pass shortens their remaining untreated recovery using the new base days and time already elapsed since the injury started—without giving a free full heal unless they have already “served” the new total.

**Why this priority**: Same fairness class as Hospital; smaller population but same “cheated by patch” risk.

**Independent Test**: Seed overflow injured card with old `injury_recovery_days` / start time; run pass; confirm remaining days match new untreated base − elapsed (floor at 0 → clear injury).

**Acceptance Scenarios**:

1. **Given** an injured card not in Hospital with elapsed time since injury start, **When** the pass runs, **Then** remaining untreated days become `max(0, new_untreated_base(tier) − days_elapsed)` and never increase vs prior remaining.
2. **Given** elapsed ≥ new untreated base, **When** the pass runs, **Then** the injury is cleared (player available) consistent with normal recovery completion.

---

### Edge Cases

- Days served computed from **admission_date** (Hospital) or **injury started** time (overflow); missing/null start → treat days served as **0** (apply full new total from now, still never lengthen past old ETA).
- Fractional days: use real elapsed time so a player admitted 1.5 days ago does not get charged a full 2 days served incorrectly; remaining ETA may land mid-day.
- Club Hospital level used for recalc is the **current** facility level (same as a fresh admit today).
- Bot-controlled clubs: same data rules; skip human DM if no deliverable owner.
- Multiple open patients per club: each stay recalculated independently; one DM may batch several early discharges for the same manager.
- Card retired / deleted mid-pass: skip safely; do not fail the whole batch.
- Pass must not create new injuries, change fatigue, coins, energy, or Hospital upgrade state.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A **one-time** fairness pass MUST recalculate every active Hospital stay (`discharge` not set) using new injury bases **1 / 4 / 7** and the existing Hospital shortening curve at the club’s current Hospital level.
- **FR-002**: Days already served MUST equal elapsed time from admission to pass runtime; remaining stay MUST be `new_total_days − days_served` (not “reset the full new clock from today ignoring time served”).
- **FR-003**: The pass MUST **never lengthen** an existing expected return date.
- **FR-004**: If `days_served ≥ new_total_days`, the pass MUST complete recovery / discharge that patient immediately (same end-state as a normal successful Hospital recovery completion).
- **FR-005**: Card-facing injury remaining-day fields MUST stay consistent with the updated Hospital ETA (managers must not see conflicting numbers).
- **FR-006**: The pass MUST be **idempotent** (safe to re-run without further unfair changes or duplicate discharges).
- **FR-007**: The pass MUST also fair-recalc **overflow / untreated** open injuries (not in Hospital) using new untreated bases and elapsed time since injury start (US3).
- **FR-008**: Early discharges MUST attempt a manager-facing Medical Update notice; delivery failure MUST NOT undo data changes (US2).
- **FR-009**: No new slash commands, hubs, Store items, or ongoing scheduler behavior beyond this one-time (or guarded idempotent) pass.
- **FR-010**: The pass MUST run **after** 011’s new bases are live in production formulas (dependency on 011 applied).

### Key Entities

- **Active hospital stay**: Open patient record with admission time, injury tier, expected return, owning club.
- **New total recovery window**: Days implied by new tier base ÷ Hospital multiplier (same curve as live admits).
- **Days already served**: Elapsed real time since admission (or injury start for overflow).
- **Early discharge**: Stay that should already be complete under the new window.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of active Hospital stays present at pass start are either shortened (or unchanged if already ≤ new ETA), early-discharged, or skipped with a logged reason (retired/missing)—none left with an ETA that still implies the old 20-day Major untreated-scale wait when the new formula says otherwise.
- **SC-002**: Zero active stays have a **later** expected return after the pass than before.
- **SC-003**: A stay with `days_served ≥ new_total` ends **discharged / recovered** within the same pass (no multi-day linger at 0 remaining).
- **SC-004**: Re-running the pass produces **no additional** early discharges for already-processed healthy outcomes and no ETA regressions.
- **SC-005**: Managers with early discharges who have DMs enabled can receive the Medical Update; those without still see correct Hospital/squad state on next `/profile` Hospital view.

## Assumptions

- New bases and Hospital multiplier match **011** (1 / 4 / 7; `ceil(base / (1 + 0.2 × H))`, minimum 1 day when still injured).
- “Discharge as recovered” means full clear of injury + hospital bed free—not “leave untreated with shortened days” (that path is for manual discharge UX, not this pass).
- Overflow fair-recalc is in scope even though the prompt focused on Hospital—same fairness class.
- Notification copy is player-facing (“medical protocols / updated recovery”), not internal migration jargon.
- Ops run this once soon after 011 on each environment; idempotency covers accidents.
- Fractional-day math is acceptable; UI may still show coarse “returns &lt;date&gt;”.

## Out of Scope

- Changing 011 bases, drain, passive, or bench again.
- Retroactive coin/refund for Hospital upgrades bought under old clocks.
- Instant Store heal consumables.
- Rewriting historical already-discharged patient rows.
- New ongoing daily job beyond existing `process_daily_recovery`.
- New Discord slash commands or hub buttons.
