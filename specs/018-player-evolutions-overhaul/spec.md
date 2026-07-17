# Feature Specification: Player Evolutions Overhaul

**Feature Branch**: `018-player-evolutions-overhaul`

**Created**: 2026-07-14

**Status**: Draft

**Input**: User description: "Pre-integration assessment and design for Player Evolutions: audit existing tracks/slots/UI, study FUT/FM-style objective evolutions, design 3-slot objective tracks with permanent rewards (stats and/or PlayStyles), clear progress, pot-safe caps, feature-flagged rollout that does not break XP/drill/transfer balance."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Start a compelling evolution with clear goals (Priority: P1)

A manager opens Evolutions, picks an eligible player and track, sees the objective and reward preview, and starts — excited by a narrative upgrade, not confused by conflicting caps or costs.

**Why this priority**: Without a clear start loop, evolutions don’t retain; current hub has drift (costs, slots, PlayStyle copy that lies).

**Independent Test**: From `/development` → Evolutions, start one track on an eligible card; hub shows slot count, objective, cost, and cooldown consistently with server rules.

**Acceptance Scenarios**:

1. **Given** a free evolution slot and an eligible card, **When** the manager starts a track, **Then** they pay the configured energy+coin cost, the card enters an active evolution, and remaining slots update (max **3** active).
2. **Given** 3 already active, **When** they try a 4th, **Then** start is rejected with a clear ephemeral reason.
3. **Given** start eligibility fails (level, injury, locked for transfer/drill/XI if gated, track already completed if non-repeatable), **When** they attempt start, **Then** no coins/energy are deducted.

---

### User Story 2 - Progress and complete with visible payoff (Priority: P1)

The manager plays matches (or completes track objectives), sees progress on the hub, claims the reward, and receives a permanent, pot-safe upgrade that matches the track preview.

**Why this priority**: Completion is the dopamine; hidden or inflated rewards break trust and economy.

**Independent Test**: With an active track at goal progress, claim applies advertised reward within POT/caps; progress bar/copy goes to completed.

**Acceptance Scenarios**:

1. **Given** an active matches-based track, **When** the evolved card appears in competitive match results, **Then** progress increments toward the goal (no silent skips).
2. **Given** progress ≥ goal and rewards unclaimed, **When** the manager claims, **Then** permanent reward is applied once (idempotent), OVR recomputed, and the slot frees (or track moves to completed history).
3. **Given** claiming would exceed potential or configured reward cap, **When** claim runs, **Then** reward is clamped safely — never ignores POT.

---

### User Story 3 - Balance slots with other activities (Priority: P2)

A manager can cancel or finish evolutions without stranding the card forever offline from drills/transfers, and cold-start cooldown is understandable.

**Why this priority**: 3 slots + card locks compete with drills, fusion, marketplace; frustration comes from unclear locks and cooldown.

**Independent Test**: Active evo card is blocked from conflicting actions with a Delist/finish-style message; cancel frees the slot with documented fee/cooldown rules.

**Acceptance Scenarios**:

1. **Given** a card in active evolution, **When** the manager tries drill/fusion/agent sale/P2P list/recovery that should conflict, **Then** action is blocked with an evolution-specific reason.
2. **Given** an active evolution, **When** they cancel, **Then** fee (if any) is charged once, status becomes cancelled, and cold-start cooldown behavior matches the published rule (replacement vs cold).

---

### User Story 4 - Truthful PlayStyle / reward catalog (Priority: P2)

Rewards match hub copy: if PlayStyles are offered, they actually grant; if only stats, copy must not promise PlayStyles.

**Why this priority**: Current hub claims PlayStyle evolution while claims only bump PAC/SHO/DEF — trust debt.

**Independent Test**: For each published track reward type, completing once leaves the expected permanent effect on the card.

**Acceptance Scenarios**:

1. **Given** a track that awards a PlayStyle (if in scope for this overhaul), **When** claimed, **Then** the PlayStyle is stored and usable in match/profile surfaces.
2. **Given** a track that awards only stats, **When** shown in the hub, **Then** copy never implies PlayStyle upgrades.

---

### User Story 5 - Safe rollout over existing clubs (Priority: P3)

Existing active/completed evolutions keep working; operators can enable overhaul behavior without wiping progress.

**Why this priority**: Production already has `active_evolutions` rows and three legacy tracks.

**Independent Test**: With flag off, legacy start/claim paths behave as today; with flag on, new tracks/rules apply without deleting history.

**Acceptance Scenarios**:

1. **Given** existing active evolutions, **When** the overhaul ships, **Then** they remain claimable/progressable under documented migration rules.
2. **Given** the feature flag / config toggles, **When** disabled, **Then** managers are not soft-locked out of `/development` Evolutions for legacy tracks (or graceful freeze is documented).

---

### Edge Cases

- Match ticks for cards not in XI / subbed — define whether only XI counts.
- Double-claim race on reward.
- Card retired/injured mid-evolution.
- Transfer market listing / sale of active evo card (must stay blocked).
- Config keys diverge from Python/hub constants (must single-source).
- Repeatable tracks vs one-shot (FUT-like) — v1 default remains non-repeatable per track per card unless specified.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST keep a hard cap of **3** simultaneous `active` evolutions per club (configurable only if hub, Python, and RPC all read the same `game_config` key).
- **FR-002**: System MUST expose Evolutions under `/development` (no new slash command).
- **FR-003**: Starting an evolution MUST deduct energy and coins atomically via the club economy pipe; shortfalls abort with no partial debit.
- **FR-004**: Progress MUST advance from defined objectives (at minimum match appearances for current tracks; optional goals/rating metrics if catalog expands).
- **FR-005**: Claim MUST apply permanent rewards exactly once, clamped by potential and per-track caps.
- **FR-006**: Hub MUST show slots used, costs, cooldown, progress, and reward preview that match server behavior.
- **FR-007**: Active evolutions MUST block conflicting card actions (drills, fusion, agent sale, P2P list, and other existing guards) with clear messaging.
- **FR-008**: Reward catalog and UI copy MUST agree (PlayStyles only if granted; else stat-only language).
- **FR-009**: Cold-start cooldown and cancel→replacement rules MUST be documented and enforced identically in RPC + UI.
- **FR-010**: Overhaul MUST NOT grant XP outside `apply_card_xp` or bypass POT caps.
- **FR-011**: Track definitions SHOULD move toward a data-driven catalog (table or shared package+SQL seed) to end Python/SQL drift.
- **FR-012**: Rollout MUST preserve existing `active_evolutions` history and offer a migration/flag strategy.

### Key Entities

- **Evolution Track**: Named objective path (metric, goal, min level, reward type/magnitude, repeatability).
- **Active Evolution**: Club-card assignment with progress and status (active/completed/cancelled).
- **Evolution Reward**: Permanent stat delta and/or PlayStyle grant applied on claim.
- **Club Evolution State**: Slot usage + cold-start cooldown timestamp.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: ≥50% of active managers who open Evolutions in a pilot week successfully start at least one track.
- **SC-002**: ≥80% of started evolutions in the pilot reach claim without support tickets about “missing PlayStyle” or wrong cost.
- **SC-003**: Zero claimed rewards exceed POT or undocumented caps in a post-claim audit sample.
- **SC-004**: Hub-displayed slot/cost/cooldown matches RPC rejection reasons in 100% of QA scripted cases.
- **SC-005**: No regression: drills/fusion/match XP paths still use their RPCs; evo claim never writes XP outside `apply_card_xp`.

## Assumptions

- Keep hub entry at `/development` Evolutions + profile shortcuts.
- Default max active = **3** (resolve `game_config` seed of 4 to match).
- v1 objectives remain primarily **matches played**; richer metrics (goals, rating) are catalog extensions.
- PlayStyle grants are **in-scope for design** but may be phased P2 after stat-path truthfulness is fixed.
- Cancel fee and start fee remain economy sinks via `apply_club_economy`.
- Feature flagging may be config-key based rather than a separate slash surface.

## Out of Scope

- Paid real-money evolution paths
- Making evolved cards untradeable globally (FUT pattern) — ElevenBoss already soft-locks while active only
- Infinite evo chaining meta of weekly premium EVOs
- New slash command `/evolutions`
