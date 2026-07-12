# Feature Specification: Recovery Energy, Hub Cleanup & Energy Cap

**Feature Branch**: `010-recovery-energy-cleanup`

**Created**: 2026-07-12

**Status**: Draft

**Input**: User description: "Reduce Recovery Session energy cost from 10 to 5; remove Hospital panel from Store/Club Facilities; delete the dedicated club-finance slash command; raise maximum action energy cap from 100 to 120. Update all relevant config, data, UI, and remove stale references."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Cheaper Recovery Sessions (Priority: P1)

As a manager, starting a Recovery Session costs **5** action energy (not 10), so resting a tired starter is a lighter spend relative to skill drills.

**Why this priority**: Directly adjusts the just-shipped Recovery Session balance; managers feel this every session.

**Independent Test**: Open Training Drills, select Recovery Session, confirm preview and successful run debit **5** energy; skill Basic drill energy is unchanged.

**Acceptance Scenarios**:

1. **Given** a fatigued eligible player and enough energy, **When** the manager starts a Recovery Session, **Then** the session costs **5** action energy and the success/preview copy shows 5⚡ (not 10⚡).
2. **Given** a club with exactly 5 action energy, **When** they run Recovery Session, **Then** it succeeds and energy reaches 0 (subject to other gates).
3. **Given** a club with 4 action energy, **When** they attempt Recovery Session, **Then** it is rejected for insufficient energy.
4. **Given** skill drills still use Basic/Advanced energy config, **When** a Basic drill runs, **Then** its energy cost is unchanged by this feature (still the Basic drill setting, typically 10).

---

### User Story 2 - Higher Action Energy Cap (Priority: P1)

As a manager, my club’s action energy can fill up to **120** (not 100), so I can bank more actions between matches and training.

**Why this priority**: Affects every energy-gated action; must be consistent in storage, regen ceiling, refills, and UI.

**Independent Test**: Club at full energy shows **/120**; refill and regen stop at 120; displays that previously hardcoded `/100` for action energy show 120.

**Acceptance Scenarios**:

1. **Given** any registered club after this change, **When** energy is displayed (Store, Development, battle/energy status), **Then** the maximum shown is **120**.
2. **Given** a club with energy below 120, **When** passive regen runs, **Then** energy increases until **120** and does not exceed it.
3. **Given** an energy refill purchase, **When** applied, **Then** the resulting balance never exceeds **120**.
4. **Given** existing clubs that still had a stored max of 100, **When** the change is applied, **Then** their effective max becomes **120** (no club left stuck at a 100 ceiling).

---

### User Story 3 - Hospital Only via Profile (Priority: P2)

As a manager, I no longer see or open a Hospital panel under **Store → Club Facilities**. Hospital care and upgrades remain available from **`/profile` → Manage Hospital**.

**Why this priority**: Declutters Store facilities without removing injury care; profile remains the medical hub.

**Independent Test**: Open Store Club Facilities — no Hospital row/panel/button; open `/profile` → Manage Hospital still works for admit/upgrade/patients.

**Acceptance Scenarios**:

1. **Given** the Store Club Facilities view, **When** it is opened, **Then** Youth Academy and Training Ground remain, and **no Hospital facility entry or Hospital panel** is offered.
2. **Given** an injured player and a Hospital level ≥ 0, **When** the manager uses `/profile` → Manage Hospital, **Then** they can still view patients, admit/overflow flows, and upgrade Hospital as before.
3. **Given** player-facing error or empty-state copy that previously pointed managers to Store facilities for Hospital, **When** shown after this change, **Then** it points to **`/profile`** (or Manage Hospital) — not Store Club Facilities.
4. **Given** facility upgrade weekly slot messaging on Store facilities, **When** Hospital is removed from that hub, **Then** copy no longer lists Hospital as upgradable from Store (profile upgrade path remains valid).

---

### User Story 4 - Remove Dedicated Club Finance Command (Priority: P2)

As a manager, I no longer have a dedicated slash command for club finances. Wallet and finance detail live on **`/profile`** (and related profile Finances actions).

**Why this priority**: Removes a soft-deprecated duplicate surface; reduces command clutter.

**Independent Test**: Slash command picker has no `club-finances` (or equivalent); `/profile` Finances still opens the finance detail view.

**Acceptance Scenarios**:

1. **Given** the bot’s registered application commands, **When** a manager searches for club finance, **Then** there is **no** dedicated `/club-finances` (or `/club-finance`) slash command.
2. **Given** `/profile`, **When** the manager opens Finances, **Then** balance / wage / facility summary still appears (same substance as the old command’s useful content).
3. **Given** old changelog, help, or in-bot pointers that told managers to use `/club-finances`, **When** updated for this release, **Then** they point to `/profile` instead and do not advertise the removed command.

---

### Edge Cases

- Recovery Session at energy exactly 5 vs 4 — succeed vs reject.
- Clubs mid-refill when max rises to 120 — next sync/refill respects 120.
- Hardcoded `…/100` strings that refer to **morale** or other non-energy gauges must **not** be changed to 120.
- Store facilities with only YA + TG — empty Hospital must not leave a broken button or dead custom_id.
- Profile L0 Hospital empty-state that said “build in the Store” must be rewritten so managers are not sent to a removed Store panel.
- Bot restart after removing slash command — command must not remain registered (sync/unregister as the project normally does).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Recovery Session action energy cost MUST be **5** everywhere managers see or pay it (runtime config, defaults, Development preview, and success messaging).
- **FR-002**: Skill drill energy costs MUST remain independently configured; this feature MUST NOT silently change Basic/Advanced drill energy by coupling them to Recovery.
- **FR-003**: Club action energy maximum MUST be **120** for regen ceiling, refill cap, status displays, and stored club max values.
- **FR-004**: All existing clubs MUST be updated so their effective energy maximum is **120** (no lingering 100 max).
- **FR-005**: Store → Club Facilities MUST NOT present a Hospital facility row, Hospital detail panel, or Hospital-only navigation from that hub.
- **FR-006**: Hospital injury care and Hospital upgrades MUST remain available via `/profile` → Manage Hospital (system not deleted).
- **FR-007**: Player-facing copy that directed users to Store Club Facilities for Hospital MUST be updated to `/profile` / Manage Hospital.
- **FR-008**: The dedicated slash command `/club-finances` (and any `/club-finance` alias if present) MUST be removed from the bot.
- **FR-009**: Club finance information MUST remain reachable from `/profile` (Finances), without requiring the removed slash command.
- **FR-010**: Grep-level cleanup MUST remove or rewrite stale references to the removed Store Hospital panel and the removed finance slash command in bot UI strings and player-facing changelog; implementation docs may note deprecation historically but must not instruct managers to use removed surfaces.
- **FR-011**: Non-energy uses of “/100” (e.g. morale) MUST remain unchanged.

### Key Entities

- **Recovery Session cost**: Tunable energy debit for fitness restore (target value 5).
- **Action energy pool**: Club resource with max capacity (target max 120).
- **Store Club Facilities hub**: YA + Training Ground only after this change.
- **Profile Hospital**: Remaining management surface for medical care.
- **Profile Finances**: Remaining surface for wallet/wage/facility summary after slash command removal.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of successful Recovery Session runs debit exactly **5** energy under default config.
- **SC-002**: 100% of clubs show energy max **120** in primary energy status surfaces after deploy.
- **SC-003**: Store Club Facilities UI contains **zero** Hospital panel entry points (manual UI checklist).
- **SC-004**: Slash command inventory contains **zero** `club-finance` / `club-finances` commands after deploy.
- **SC-005**: Managers can still complete Hospital admit/upgrade and view finances without the removed Store panel or finance slash command (via `/profile`).
- **SC-006**: Automated search of bot UI strings finds no remaining “Hospital in Store/Club Facilities” or “use `/club-finances`” player instructions.

## Assumptions

- Command to remove is the existing **`/club-finances`** (plural), not a separate `/club-finance` — remove whichever dedicated finance slash command exists.
- Hospital **game system** (injuries, beds, upgrades, daily recovery) stays; only the **Store facilities Hospital panel** is removed.
- `/profile` remains the canonical place for Manage Hospital and Finances.
- Recovery energy 5 is a deliberate discount vs Basic skill drills (~10); not a global energy rebalance.
- Energy cap 120 updates both the global config default and each club’s stored max.
- Regen rate (e.g. +1 per 4 minutes) is unchanged; only the ceiling rises.
- Energy refill pricing/amounts may stay as-is unless they hardcode a 100 cap in logic (any hard 100 ceiling for action energy must become 120).

## Out of Scope

- Removing Hospital from `/profile` or deleting injury/Hospital RPCs.
- Changing Recovery Session fatigue amount (+40) or drill daily caps.
- Changing Basic/Advanced skill drill energy or coin costs (except ensuring they stay independent).
- Changing energy regen interval.
- New slash commands or new Store panels.
- Physio consumables or other fatigue features beyond the Recovery energy tweak.
