# Feature Specification: Fix Contract Renew Stuck After First Renewal

**Feature Branch**: `047-fix-contract-renew`

**Created**: 2026-07-28

**Status**: Implemented — migration 087 applied; Discord smoke after bot restart

**Input**: User description: "Players report they can't renew contracts — match gate shows: Contract expired (past grace): Roy Thompson. Renew on /player-profile or replace via /squad before matching."

**Parent / related**: Extends Implemented `specs/019-contract-wage-system` (contract expiry gates + `renew_contract`). Does **not** reopen wage payroll design. Cite **US-42** economy integrity when changing renewal idempotency (single coin pipe via `apply_club_economy`).

**Root cause (investigation)**: `renew_contract` uses a **permanent** economy idempotency key `contract_renewal:{card_id}`. The first successful renew writes that key. Later renewals hit **replay**, return success, and **skip** extending `contract_expires_at`. Confirmed for Roy Thompson (Crimson FC): renewed 2026-07-14 (−722 coins), expiry stayed 2026-07-21, now past grace — further renews cannot take effect. At least ~10 human past-grace cards already have a prior one-shot renew ledger row; many more past-grace cards were never renewed (separate urgency, not blocked by this bug).

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Renew works every time a manager pays (Priority: P1)

A manager opens `/player-profile` for a card whose contract is in grace or past grace, presses Renew, pays the coin cost, and the contract expiry actually moves forward so the card can return to the XI / matches.

**Why this priority**: Match lock + false “renewed” success is a hard blocker for affected clubs (e.g. Crimson FC / Roy Thompson).

**Independent Test**: On a card that already has a historical `contract_renewal:{card_id}` ledger row and is past grace, renew once → coins charged (or fair double-tap handling) → `contract_expires_at` is in the future by the configured extension days → squad/match gate clears for that card.

**Acceptance Scenarios**:

1. **Given** a owned non-retired card under age 35 with an expired (past grace) contract and a prior renew ledger entry for that card, **When** the manager renews from `/player-profile`, **Then** `contract_expires_at` becomes at least “now + renewal days” (or from current expiry if still future) and the match/squad past-grace block for that card is cleared.
2. **Given** a card never renewed before, **When** renewed, **Then** behaviour remains: coins deducted via economy pipe, expiry extended, success feedback shown.
3. **Given** the manager double-taps Renew within a short window, **When** both requests run, **Then** they are not charged twice for the same intended renew (idempotent per attempt), and expiry is extended at most once for that attempt.
4. **Given** renew succeeds, **When** success copy is shown, **Then** it reflects a real extension (not a silent no-op replay that leaves expiry past grace).

---

### User Story 2 — Honest failure / age rules unchanged (Priority: P2)

Managers still cannot renew age 35+ cards; insufficient coins fail clearly; ownership checks remain.

**Why this priority**: Fix must not weaken lifecycle or economy gates while unblocking re-renew.

**Independent Test**: Age ≥35 still rejected; wrong owner rejected; low coins rejected with readable error.

**Acceptance Scenarios**:

1. **Given** a card age ≥ retirement warning age (35), **When** renew is attempted, **Then** it fails with the existing age message and coins are not taken.
2. **Given** insufficient coins, **When** renew is attempted, **Then** the manager sees a clear failure and expiry is unchanged.
3. **Given** another manager’s card, **When** renew is attempted, **Then** it fails (not owned).

---

### User Story 3 — Affected clubs can recover without manual SQL (Priority: P2)

Managers already stuck after a one-shot renew can recover by using the fixed renew path (or a one-time safe recovery path documented for ops if needed).

**Why this priority**: Live stuck cards (including Roy Thompson) need a player-facing recovery, not only a forward fix.

**Independent Test**: After fix is live, renew Roy Thompson (or equivalent stuck fixture) from profile → past-grace gate gone.

**Acceptance Scenarios**:

1. **Given** a stuck card (prior permanent idempotency key + past grace), **When** the fixed renew runs, **Then** the manager does not need a developer to edit `economy_ledger` manually.
2. **Given** ops needs an emergency unblock before bot deploy, **When** following the feature quickstart ops note, **Then** a documented safe SQL/RPC path exists (optional; prefer player renew after deploy).

---

### Edge Cases

- Card with `contract_expires_at` null — renew still establishes a new window from now + days (existing RPC behaviour).
- Replay of the **same** attempt key must not double-charge; a **new** intentional renew later must charge and extend again.
- AI clubs out of scope for player reports; human clubs only for recovery verification.
- Age 35+ remains non-renewable; replace via `/squad` remains the path.
- Stale profile view / bot restart: renew button may fail closed with re-run `/player-profile` (existing Discord view behaviour); not the primary bug.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `renew_contract` MUST allow a manager to renew the same card more than once over its lifetime (each intentional renew extends expiry and charges when not a duplicate attempt).
- **FR-002**: Economy idempotency for renew MUST prevent double-charge on duplicate/retry of the **same** attempt, and MUST NOT permanently block all future renewals for that card.
- **FR-003**: On a successful non-replay renew, `contract_expires_at` MUST be extended per existing rules (from now if null/expired, else from current expiry) by `p_extension_days`.
- **FR-004**: If an economy replay is returned, the system MUST NOT report a successful extension unless expiry is actually valid (not past grace); prefer fixing the key design so intentional renews are not classified as replay.
- **FR-005**: Player-facing renew UI (`/player-profile`) MUST surface success only when extension occurred (or show remaining/new expiry); must not claim renewal when the card remains past grace.
- **FR-006**: Age ≥35 renew rejection, ownership checks, and `apply_club_economy` as the sole coin pipe MUST remain in force.
- **FR-007**: No new slash command; extend existing renew path only.
- **FR-008**: Feature MUST include a migration (or forward RPC replace) for the renew idempotency fix; do not edit already-applied migrations in place on remote.
- **FR-009**: Document recovery for stuck cards (player renew after fix is enough if FR-001 holds).

### Key Entities

- **Contract renew attempt**: One manager action to pay coins and extend a card’s `contract_expires_at`.
- **Economy ledger idempotency key**: Unique per attempt (not forever per card).
- **Past-grace card**: `now ≥ expires_at + contract_grace_days` — blocked from XI/match until renewed or replaced.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A card with an existing historical `contract_renewal:{card_id}` ledger row can be renewed again and leave past-grace within one successful profile renew.
- **SC-002**: Double-tap renew within the attempt window charges at most once.
- **SC-003**: After successful renew, squad/match validity no longer names that card as past grace.
- **SC-004**: Age ≥35 renew still fails 100% of attempts in tests/smoke.
- **SC-005**: Roy Thompson (or equivalent stuck fixture) is unblocked without manual ledger deletion once the fix is deployed.

## Assumptions

- Root cause is permanent `contract_renewal:{card_id}` idempotency in `renew_contract` (047 / economy pipe), not the past-grace gate itself (gate is working as designed).
- Grace/renewal day configs (`contract_grace_days`, `contract_renewal_days`, default 7) stay unchanged unless a separate balance change is requested.
- `custom_id="renew_contract_profile"` reuse may cause secondary Discord UX issues after restart; primary ship is RPC idempotency — button hardening is optional polish if time allows.
- 286 never-renewed past-grace human cards are expected manager backlog, not this bug; messaging already points to `/player-profile`.

## Out of Scope

- Changing grace length or renewal cost formula
- Auto-renew / auto-release of expired contracts
- New hub or slash command for bulk renew
- Rewriting payroll / wage strikes
