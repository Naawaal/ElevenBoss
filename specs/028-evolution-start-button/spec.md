# Feature Specification: Evolution Start Button Fix

**Feature Branch**: `028-evolution-start-button`

**Created**: 2026-07-22

**Status**: Draft

**Input**: User description: "Bug/Issue — start new evolution button is unclickable it's not clickable i want you to analyze our workspace and find out it's a bug or something else?"

## Analysis Verdict *(investigation result)*

**Both: intentional gating and a real bug.**

| Situation | Expected? | What the manager sees |
|-----------|-----------|------------------------|
| Club has **3/3** active evolution slots | Intentional | Greyed-out **Start New Evolution** button; slots field shows full |
| Cold-start cooldown still running (no cancel→replacement) | Intentional | Greyed-out button; Cooldown field shows remaining time |
| Replacement start available after cancel | Intentional (enabled) | Button clickable; Cooldown says replacement available |
| Cooldown **already finished** under the published live rule, but hub still treats start as blocked | **Bug** | Button stays unclickable even though a new evolution should be allowed |
| Hub Cooldown copy says ready / remaining time that does not match the rule used when starting | **Bug** | Confusing or contradictory readiness vs button state |

Workspace investigation found that the Evolution Command Center **deliberately disables** the Start button when hub status says start is not allowed. That is correct product behavior for full slots and active cooldown. Separately, hub readiness and the actual start rule are **out of sync** on cooldown length: the start path uses the live configured cooldown (published as **6 hours**), while the hub status path still uses an older hardcoded **10-hour** window. After the real cooldown ends, the button can remain greyed out for several more hours — which matches the reported “unclickable” symptom when the manager believes they should be able to start.

Related honesty gap (same hub surface): start-cost copy on the hub can still describe an outdated coin formula while the live start rule uses a different one. That does not by itself disable the button, but it erodes trust in the same screen.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Click Start when eligible (Priority: P1)

A manager opens `/development` → Evolutions after their cold-start cooldown has ended (and they have a free slot). The **Start New Evolution** button is clickable and opens the track picker.

**Why this priority**: The reported failure is that eligible managers cannot start; restoring clickability when rules allow is the core fix.

**Independent Test**: With fewer than 3 active tracks and cooldown elapsed under the published live cooldown rule, open the Evolution hub and press Start — track selection appears.

**Acceptance Scenarios**:

1. **Given** a club with fewer than 3 active evolutions and cold-start cooldown elapsed under the live configured rule, **When** the manager opens the Evolution Command Center, **Then** **Start New Evolution** is enabled and clickable.
2. **Given** that same eligible state, **When** they press **Start New Evolution**, **Then** they reach the evolution track / player selection flow (not a silent no-op).
3. **Given** the hub Cooldown field, **When** start is allowed, **Then** the field communicates readiness (or replacement availability) consistently with the enabled button.

---

### User Story 2 - Understand why Start is blocked (Priority: P1)

When start is not allowed, the manager still understands *why* without needing to guess whether Discord is broken.

**Why this priority**: Full slots and real cooldown are valid blocks; greyed-out Discord buttons cannot show a click error, so the embed must carry the reason.

**Independent Test**: Force each block reason (full slots; active cooldown with no replacement) and confirm the hub embed explains it while the button stays disabled.

**Acceptance Scenarios**:

1. **Given** 3 active evolutions, **When** the manager opens the hub, **Then** **Start New Evolution** is disabled and the slots / gate copy clearly says the club is at the active limit.
2. **Given** an active cold-start cooldown and no cancel→replacement credit, **When** they open the hub, **Then** the button is disabled and the Cooldown field shows remaining time that matches the live cooldown rule used for starts.
3. **Given** a cancel that grants replacement start while slots remain, **When** they open the hub, **Then** the button is enabled and copy indicates replacement start is available.

---

### User Story 3 - Hub readiness matches start enforcement (Priority: P1)

Whatever rule decides “you may start now” on the hub must be the same rule that allows or rejects an actual start.

**Why this priority**: Spec 018 already required identical cooldown enforcement in hub + start; drift is the root cause of false “unclickable” states.

**Independent Test**: For scripted clubs at known times after last start, hub `can_start` / Cooldown remaining and start success/failure agree in every case.

**Acceptance Scenarios**:

1. **Given** time since last cold start is past the live configured cooldown and a slot is free, **When** hub status is evaluated, **Then** start is allowed (`can_start` true) and the Start button is enabled.
2. **Given** time since last cold start is still inside the live configured cooldown and no replacement credit, **When** hub status is evaluated, **Then** start is blocked, remaining time is shown, and the Start button is disabled.
3. **Given** any mismatch between published cooldown and hub display would previously leave a multi-hour false lockout, **When** this fix ships, **Then** that false lockout window no longer occurs.

---

### Edge Cases

- Manager refreshes the hub mid-cooldown: remaining time and button state update together.
- Manager cancels one track while still in cold-start cooldown: replacement path enables Start if a slot is free.
- Manager has more than 3 legacy active tracks: Start stays blocked until they cancel down to the limit; copy explains over-slot.
- Hub message is stale after bot restart / view timeout: manager re-opens Evolutions from `/development` and sees fresh eligibility (out of scope to make expired ephemeral views permanently clickable).
- Another manager cannot use this club’s hub controls (ownership check unchanged).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Evolution Command Center MUST enable **Start New Evolution** exactly when the club is allowed to start a new evolution under the live start rules (free slot + cold-start cooldown elapsed, or valid replacement start).
- **FR-002**: The Evolution Command Center MUST disable **Start New Evolution** when start is not allowed (full slots, over-slot legacy overflow, or active cold-start cooldown without replacement).
- **FR-003**: Hub cooldown remaining time and readiness flags MUST use the same live cooldown duration that the start action enforces (no hardcoded older duration that disagrees with config).
- **FR-004**: When Start is disabled, the hub embed MUST explain the blocking reason in plain language (slots and/or cooldown), because a disabled Discord button cannot deliver a click message.
- **FR-005**: Hub Cooldown / readiness copy MUST not claim the club is ready to start while the Start button remains disabled for cooldown or slot reasons (except transient network race while refreshing).
- **FR-006**: Start-cost copy on the Evolution hub MUST match the live start cost rule (energy + coins), so the same screen does not show conflicting numbers.
- **FR-007**: Existing intentional behaviors MUST be preserved: max active slots, cancel fee, cancel→replacement start, and ownership-only hub interactions.

### Key Entities

- **Club Evolution Hub Status**: Slot usage, cooldown remaining, whether cold start or replacement start is allowed, resource summary for display.
- **Active Evolution Slot**: One in-progress track consuming a club slot until complete or cancel.
- **Cold-Start Cooldown**: Waiting period after starting a new evolution before another cold start is allowed (unless replacement credit applies).
- **Replacement Start Credit**: Permission to start after a cancel without waiting out the full cold-start cooldown, while slots remain.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100% of scripted eligibility cases after the live cooldown has elapsed with a free slot, managers can click **Start New Evolution** and reach track selection on the first hub open.
- **SC-002**: False lockout after real cooldown expiry (hub still blocking while start rules would allow) is reduced to **0** in QA cases that previously reproduced the 10h-vs-6h style drift.
- **SC-003**: For blocked cases (full slots; active cooldown), 100% of QA scripted hubs show an embed reason that matches why Start is disabled.
- **SC-004**: Hub-displayed cooldown remaining and start rejection timing agree within **1 minute** in scripted clock tests (same duration source).
- **SC-005**: Support / player reports of “Start New Evolution does nothing / won’t click” after cooldown should have ended drop once the fix is live (qualitative: no reproducible false grey-out in the documented window).

## Assumptions

- The published live cold-start cooldown is the configured game value currently seeded at **6 hours** (not the older hardcoded **10 hours** still present on the hub status path).
- Max active evolutions remains **3** unless operators deliberately change live config; this fix does not redesign slot limits.
- Cancel→replacement semantics stay as today; this fix aligns display/gating with that model rather than removing cooldown.
- Managers reach the surface via `/development` → Evolutions; no new slash command is required.
- View timeout / stale ephemeral Discord messages remain a platform limitation; the fix targets incorrect disable-while-eligible and mismatched readiness copy on a freshly opened hub.
- Cost-copy alignment (FR-006) is in scope as part of the same hub honesty pass because incorrect cost text lives on the same Evolution Command Center screen as the Start button.
