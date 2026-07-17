# Feature Specification: Contract & Wage System

**Feature Branch**: `019-contract-wage-system`

**Created**: 2026-07-14

**Status**: Implemented (T001–T037; flag default off)

**Input**: User description: "Pre-integration assessment and design for Contract & Wage system: audit forecast-only wages and renew_contract, study FCM wage models, design weekly payroll sink, renewal/expiry with real stakes, non-payment consequences that are fair for Discord casuals, feature-flagged migration of existing cards."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See and understand the wage bill (Priority: P1)

A manager opens club finances and sees a real weekly wage obligation for the relevant squad set, with enough breakdown to make roster decisions.

**Why this priority**: Today wages are forecast-only and labeled as not deducted; commitment starts with truth in the UI.

**Independent Test**: `/profile` → Finances shows weekly wage total for Starting XI (`squad_assignments`) only. Wage/contract freeze applies to Starting XI only. The full senior roster is not frozen (not billed in v1).

**Acceptance Scenarios**:

1. **Given** a registered club with XI cards, **When** they open Finances, **Then** they see weekly wage total and (at least) count of wage-paying players.
2. **Given** wages change after a squad save or OVR change, **When** they reopen Finances, **Then** the forecast reflects the new figures.

---

### User Story 2 - Weekly payroll runs automatically (Priority: P1)

Each week (aligned to existing Monday/scheduler cadence), the club is charged wages via the economy pipe; managers see the deduction and remaining balance.

**Why this priority**: Without automatic deduction there is no contract/wage “system” — only a calculator.

**Independent Test**: After scheduler/RPC run, ledger shows a payroll debit and coins decrease by the billed amount (or deferred/debt rule fires).

**Acceptance Scenarios**:

1. **Given** a club with positive coins ≥ wage bill, **When** weekly payroll processes, **Then** coins decrease by the bill via `apply_club_economy` (or equivalent single pipe) and finances reflect payment.
2. **Given** the feature flag is off, **When** the weekly job runs, **Then** no payroll deductions occur (forecast-only remains).

---

### User Story 3 - Can’t pay — fair, readable consequences (Priority: P1)

If coins are insufficient, the manager faces clear, progressive consequences designed for Discord (not instant club death), with a path back to healthy finances.

**Why this priority**: FM/Top Eleven–style debt can wipe alts and frustrate casuals; ElevenBoss needs soft pressure.

**Independent Test**: Force a club under the bill; after payroll, consequence tier is applied and messaging explains how to recover.

**Acceptance Scenarios**:

1. **Given** coins are less than the weekly bill, **When** payroll runs, **Then** the system does not silently skip without a recorded outcome. Approved unpaid outcomes for v1 are strictly limited to: partial pay, debt accumulation, and payroll strikes. Morale mutation is explicitly out of scope (YAGNI).
2. **Given** repeated unpaid cycles, **When** thresholds are hit, **Then** escalations follow the published ladder (still no unexplained card deletion without warning).

---

### User Story 4 - Contracts that matter (Priority: P2)

Contracts have length; renewals cost coins; expiry affects playability or presence after a grace period, so renewals aren’t optional fluff.

**Why this priority**: `renew_contract` and `contract_expires_at` exist but expiry has no teeth.

**Independent Test**: Past grace period → player cannot be assigned to the Starting XI (`squad_assignments`) until renewed or replaced. **No auto-release in v1.** Renew restores usability.

**Acceptance Scenarios**:

1. **Given** a card nearing expiry, **When** the manager renews via profile, **Then** coins debit and expiry extends by the configured term.
2. **Given** age ≥35 (existing retirement gate), **When** renew is attempted, **Then** renew stays blocked.
3. **Given** contract expired beyond grace, **When** the manager tries to assign them to Starting XI or play a match with them in XI, **Then** the action is blocked until renewed or replaced. **No auto-release in v1.**

---

### User Story 5 - Migration of existing clubs (Priority: P2)

Existing clubs receive sensible default wages/contracts without bankrupting them on day one of enablement.

**Why this priority**: Production rosters are large; a hard payroll flip would be catastrophic.

**Independent Test**: After backfill, every senior card has contract/wage fields populated; first payroll can be deferred or soft-capped by config.

**Acceptance Scenarios**:

1. **Given** legacy cards with only `contract_expires_at`, **When** migration runs, **Then** wages/defaults are assigned without deleting cards.
2. **Given** first enablement week, **When** payroll runs, **Then** optional grace/soft billing config prevents mass insolvency (documented).

---

### Edge Cases

- Mid-week transfers changing next bill vs current bill.
- Academy / listed / injured cards — wage scope is Starting XI only (bench/academy unpaid).
- Bot/AI clubs — exempt from payroll.
- Double payroll if job retries — idempotent `payroll_runs`.
- Interaction with P2P purchases inflating wage bill next week.
- Division/intensity scaling of wages (optional — out of v1).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST compute weekly wages from a documented formula (OVR/rarity/age/potential factors as approved in plan) with package + SQL/config parity.
- **FR-002**: System MUST show wage forecast on `/profile` Finances (extend existing, no new slash command).
- **FR-003**: When enabled, System MUST process payroll on a scheduled cadence via atomic economy RPC(s).
- **FR-004**: Payroll MUST use the club economy ledger pipe — never silent `players.coins` updates.
- **FR-005**: System MUST define insufficient-funds behavior (tiers) visible to the manager — v1: partial pay, debt, strikes only (no morale mutation).
- **FR-006**: Contract renewals MUST remain coin-costing and extend `contract_expires_at` (or successor field).
- **FR-007**: Past grace period → player cannot be assigned to the Starting XI (`squad_assignments`) until renewed or replaced. **No auto-release in v1.**
- **FR-008**: Age ≥35 renew block MUST remain.
- **FR-009**: Enablement MUST be feature-flagged; default off until migration + verify.
- **FR-010**: Senior roster capacity (`senior_roster_cap`) MAY interact as a soft pressure tool but MUST NOT be replaced by wages alone.
- **FR-011**: Wage scope MUST be Starting XI (`squad_assignments`) only in v1.
- **FR-012**: Strike market/scout penalties MUST be enforced in RPCs (`create_transfer_listing`, `purchase_scouting_player`, `dispatch_youth_scout`, `sign_youth_scout_prospect`) when `payroll_strikes >=` configured market block — not Discord-client-only.

### Key Entities

- **Player Wage Obligation**: Per-card weekly coin amount (derived at bill time — not a stored wage column).
- **Club Payroll Run**: Timestamped bill + paid/debt outcome.
- **Player Contract**: Expiry, term length, renewal cost snapshot.
- **Payroll Consequence State**: Debt + strike count for unpaid cycles (no morale tier).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With flag on, 100% of weekly payroll QA runs produce a ledger row (or explicit skip reason for exempt clubs).
- **SC-002**: Managers can find wage bill + next payment hint in under 30 seconds from `/profile`.
- **SC-003**: Freeze `wages_payroll_bill_scale` default to **1.0** in `game_config`. Ops may set to **0.5** for soft launch / lower-pressure weeks if needed. No code KPI required beyond soft-scale config.
- **SC-004**: Expiry grace behavior matches copy in ≥95% of scripted QA cases.
- **SC-005**: Flag off: finances remain forecast-only (today’s promise); no surprise deductions.

## Assumptions

- Reuse existing wage formula as baseline; rarity/age/POT multipliers config-tunable (age/POT off by default) — plan D1–D3.
- Scheduler aligns to Monday UTC jobs already used for aging/academy (**00:05 UTC** payroll).
- Default **flag off**; wage scope **Starting XI only**.
- Non-payment v1: debt + strikes + match/market gates — **not** morale mutation, **not** automatic fire-sale.
- Renewal UI stays on `/player-profile` (+ Finances alerts).

## Out of Scope

- Real-world multi-year agent negotiations
- Token-based wage payments
- New `/wages` slash command
- Full FM negotiation UI
- Instant club liquidation without warnings
- Morale mutation on unpaid wages
- Auto-release / free-agency of expired contracts (v1)
