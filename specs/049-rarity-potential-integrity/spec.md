# Feature Specification: Rarity Potential Cap Integrity

**Feature Branch**: `049-rarity-potential-integrity`

**Created**: 2026-07-31

**Status**: Draft

**Input**: User description: "Player Potential Cap Integrity Plan — make rarity absolute POT ceilings an invariant (Common 75 / Rare 85 / Epic 92 / Legendary 99); stop recurrence; audit, dry-run reimbursements with confidence levels, repair corrupted cards, refund only removed paid progression; notify managers; no new gameplay features."

**Parent / related**: Extends **US-42** game integrity ([`029-game-integrity`](../029-game-integrity/spec.md)), especially US-42.2 (player state), US-42.7 (economy), US-42.9 (DB invariants). Touches progression/economy pipes from US-23 / US-25 without inventing parallel XP or coin pipes. Does **not** redesign academy rarity generation, marketplace price damages, or add new slash commands / hubs.

**Type**: Stability / game-integrity correction — **no new gameplay features**.

---

## Problem (why this exists)

Rarity is intended to set the absolute maximum potential (POT) a card may ever reach:

| Rarity    | Absolute maximum POT |
| --------- | -------------------: |
| Common    |                   75 |
| Rare      |                   85 |
| Epic      |                   92 |
| Legendary |                   99 |

That mapping already exists as a design rule, but it is **not currently an invariant**. Creation, growth, and progression paths can produce or consume illegally high POT. An illegal POT becomes extra progression headroom (skill points, drills, evolutions, academy growth), which unbalances rarities, devalues Legendary scarcity, and can leave managers with stats and spend that should never have been allowed.

**Required invariant (all cards, at all times):**

> `overall ≤ potential ≤ rarity_cap`  
> and `base_potential ≤ rarity_cap` (when base potential is set)

Age, performance, academy quality, and similar systems may influence how close a player gets to the ceiling. **Nothing may raise the ceiling itself.**

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Illegal potential cannot grow further (Priority: P1)

As a manager (and as the competitive field), once containment is live, no card can gain potential above its rarity maximum, and no progression action can spend headroom that sits above that maximum — even if a historical card still shows a bad stored potential during the repair window.

**Why this priority**: Stopping additional corruption and unfair progression is more urgent than historical cleanup. Every day the leak remains open widens the fairness gap.

**Independent Test**: Attempt dynamic potential growth, regen/youth creation, pack/registration intake, skill allocation, drills, evolution claims, and academy growth at or above the rarity ceiling; all reject or clamp so final state never exceeds the rarity cap, and progression never uses illegal headroom.

**Acceptance Scenarios**:

1. **Given** an Epic card at potential 92, **When** any dynamic potential boost would apply, **Then** potential remains ≤ 92.
2. **Given** a Rare card whose stored potential is illegally above 85, **When** the manager attempts skill allocation, a drill, an evolution reward, or academy growth that would use headroom above 85, **Then** the action is blocked or limited to the legal ceiling (effective potential = min(stored, rarity cap)).
3. **Given** a request to create or ingest a card with overall or potential above its rarity cap (or overall > potential), **When** creation/ingress runs, **Then** the request is rejected — the system must **not** raise potential to “fix” an illegal overall.
4. **Given** regen or youth/academy generation, **When** a card is produced, **Then** potential and base potential obey the rarity cap for that card’s rarity (including academy gems).

---

### User Story 2 — Ops can inventory damage without mutating production (Priority: P1)

As an operator, I can run a read-only inventory of every card that violates the invariant, with enough before-state detail to plan repair and reimbursement — without changing live player data.

**Why this priority**: Repair without a complete, reviewed inventory risks unfair or irreversible mutations. The dry-run reimbursement report is **non-negotiable** before any production mutation.

**Independent Test**: On a copy of production-like data (or production read-only), produce a per-card report listing old/new proposed overall/potential/base potential, attributes that would change, proposed refunds, and an evidence confidence label; confirm zero writes to player cards or balances.

**Acceptance Scenarios**:

1. **Given** cards with illegal potential, illegal base potential, overall > potential, and/or overall > rarity cap, **When** the inventory runs, **Then** every such card appears grouped by rarity with counts and a full export row.
2. **Given** the dry-run reimbursement report, **When** reviewed, **Then** each card is labeled **EXACT**, **RECONSTRUCTED**, or **MANUAL_REVIEW** for refund confidence — never presented as falsely precise when evidence is aggregate or missing.
3. **Given** cards with only illegal potential but legal overall (no stats to remove), **When** classified, **Then** proposed automatic resource refund is none, with clear rationale.
4. **Given** ambiguous ownership/payer history or fusion/item consumption without reconstructable evidence, **When** classified, **Then** the card is **MANUAL_REVIEW** (or policy-resolved) before production repair — scripts must not silently guess material compensation.

---

### User Story 3 — Corrupted cards are repaired fairly; paid removed progression is refunded (Priority: P2)

As a manager whose card exceeded rarity caps, after the approved repair window my card obeys the invariant, true overall matches the corrected attributes, and I receive resources only for progression that was actually removed and that I (or the attributable payer) paid for — not for system-generated illegal baseline stats alone, and not for marketplace “overpayment” theory.

**Why this priority**: Fairness after the leak is closed; depends on a reviewed dry-run (Story 2).

**Independent Test**: On a clone with representative Category A/B/C cards, run repair twice; second run applies no extra stat/balance changes; anomaly count is zero; refund ledger entries are idempotent.

**Acceptance Scenarios**:

1. **Given** Category A (illegal POT, legal OVR), **When** repaired, **Then** potential/base potential are capped; overall and attributes unchanged; no automatic refund.
2. **Given** Category B (illegal OVR and POT), **When** repaired, **Then** potential/base potential and underlying attributes are corrected so recalculated overall ≤ legal potential ≤ rarity cap; attributable removed paid progression is refunded.
3. **Given** Category C (illegally generated at creation), **When** repaired, **Then** attributes/overall/potential are normalized to the rarity ceiling; no refund for the illegal generated baseline; subsequent paid progression that was removed is still reimbursable when evidence allows.
4. **Given** a card sold after upgrades by Manager A to Manager B, **When** refunds are applied, **Then** card correction applies to the current card, and resource reimbursement goes to the manager who paid when that can be established; otherwise **MANUAL_REVIEW**.
5. **Given** an evolution reward that must be reversed, **When** refunded, **Then** the evolution is not reopened for a second claim.
6. **Given** Mentor Transfusion history, **When** repair runs, **Then** mentor transfers are not automatically reversed (they grant XP, not potential/stats); participating cards must still pass integrity checks going forward.
7. **Given** repair and refunds committed, **When** notification runs, **Then** the manager receives one grouped message reflecting **actual** committed refunds (or an explicit “none required” for POT-only fixes); DM failure does not roll back the repair.

---

### User Story 4 — Recurrence is structurally impossible and monitored (Priority: P3)

As product/ops, after cleanup the impossible state cannot persist, and any new anomaly is treated as a critical integrity incident — not silently auto-fixed.

**Why this priority**: Prevention and monitoring close the incident; comes after containment and fair repair.

**Independent Test**: Attempt invalid persisted states after constraints are validated; all fail closed. Lifecycle checkpoints (youth/regen/academy/aging/match processing) report anomaly count = 0.

**Acceptance Scenarios**:

1. **Given** all historical violators repaired, **When** durable integrity rules are validated, **Then** new writes that would violate overall ≤ potential ≤ rarity cap (and base potential ≤ rarity cap) are rejected.
2. **Given** deploy verification, bot startup, or post-lifecycle checkpoints, **When** the anomaly count is checked, **Then** it is exactly zero; non-zero triggers a critical integrity alert with card identifiers — no automatic silent repair of new anomalies.
3. **Given** a temporary rollout switch used during shadow/enforcement phases, **When** constraints are validated and the incident is closed, **Then** there is no lasting switch that can re-enable Epic potential above 92 (or equivalent for other rarities).

---

### Edge Cases

- Epic (or any rarity) with overall already above rarity cap: reject on create/ingress; on repair, reduce attributes then recalculate overall — never only overwrite the stored overall number.
- Dynamic potential still useful inside rarity (e.g. base + limited boost) but never past rarity cap.
- Unknown / unsupported rarity: fail closed loudly — do not silently treat as Common.
- Drill XP and legitimate match/mentor XP generally retained; only resources tied to **removed** illegal stat progression are refunded.
- Unspent skill points after OVR is capped may remain (spendable when legal headroom exists later).
- Ambiguous SP attribution: never double-refund the same removed stat point as both drill and skill allocation; escalate material ambiguity to **MANUAL_REVIEW**.
- Marketplace listing/sale “extra value” from displayed illegal POT: correct the card; no algorithmic transfer-market damages in this fix; optional export of transferred affected cards for admin review.
- DMs disabled: repair and refunds stay committed; notification failure logged for admin follow-up.
- Repair script run twice: second run is a no-op for stats and refunds (idempotent).
- Temporary containment must ship before reimbursement tooling is complete so the leak does not widen.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: For every player card at all times, overall MUST be ≤ potential, potential MUST be ≤ the absolute rarity maximum (Common 75, Rare 85, Epic 92, Legendary 99), and base potential (when present) MUST be ≤ that same maximum.
- **FR-002**: Age and performance systems MUST NOT change rarity absolute maxima; they may only affect rolls, eligibility, growth speed, or aging within the cap.
- **FR-003**: Illegal overall MUST NEVER raise potential above the rarity maximum; create/ingress paths MUST reject impossible overall/potential combinations.
- **FR-004**: Dynamic potential growth MUST respect the rarity maximum (boosts may still apply inside the cap and any existing within-rarity boost ceiling).
- **FR-005**: All card producers (including factory, regen, youth/academy, gems, gacha/special creation, and maintenance writers) MUST emit only invariant-valid cards; no producer may overwrite a valid card with an unchecked potential.
- **FR-006**: Card models / validation at creation boundaries MUST reject potential or base potential above rarity cap and overall > potential.
- **FR-007**: Pack claim, registration, youth intake, and scout signing ingress MUST reject malformed cards before persistence.
- **FR-008**: Progression consumers (skill allocation, drills, evolution rewards, academy growth, fusion/training paths that gate on potential, and mentor paths operating on cards) MUST use effective potential = min(stored potential, rarity cap) during and after rollout so illegal stored headroom cannot be spent.
- **FR-009**: Mentor Transfusion MUST NOT be treated as a potential-corruption source or automatically reversed; cards involved MUST still satisfy integrity before further progression.
- **FR-010**: Ops MUST be able to run a read-only anomaly inventory and export full before-state for every affected card before any production mutation.
- **FR-011**: A dry-run reimbursement report MUST exist before production repair, classifying each card’s refund confidence as **EXACT**, **RECONSTRUCTED**, or **MANUAL_REVIEW**, and surfacing evidence strength explicitly (e.g. drill charges with card-level economy metadata vs aggregate skill-points-spent without per-allocation history).
- **FR-012**: Production repair MUST NOT proceed while unclassified affected cards remain, or while material **MANUAL_REVIEW** cases lack an explicit compensation policy.
- **FR-013**: Repair MUST adjust underlying attributes when overall exceeds the corrected ceiling, then recalculate true overall so stored overall matches calculated overall — never overall-only patches.
- **FR-014**: Refunds MUST apply only to resources attached to progression that is actually removed; POT-only corrections without removed stats MUST NOT auto-refund; illegal generated baseline stats MUST NOT manufacture refunds.
- **FR-015**: Coin and action-energy refunds MUST use the existing authoritative economy pipe with idempotent keys; skill-point corrections MUST keep available and spent counters consistent.
- **FR-016**: Refund payer SHOULD be the manager who paid when reconstructable; otherwise flag **MANUAL_REVIEW** — do not blindly credit the current owner for all historical spend.
- **FR-017**: Marketplace overvaluation damages MUST NOT be algorithmically compensated in this feature.
- **FR-018**: Manager notifications MUST reflect committed repair/refund outcomes only (including explicit “none required” when appropriate), sent after repair and refunds succeed; notification failure MUST NOT undo integrity repairs.
- **FR-019**: After cleanup, durable persistence rules MUST reject new invariant violations; new anomalies MUST alert as critical and MUST NOT be silently auto-repaired.
- **FR-020**: Monitoring MUST re-check anomaly count = 0 at deploy verification, startup, and after key lifecycle boundaries (youth intake, regen, academy growth, season aging, match processing) without building a new player-facing dashboard or gameplay surface.
- **FR-021**: No new slash command, hub button, or gameplay table beyond what integrity audit/repair requires; academy rarity redesign is out of scope.
- **FR-022**: Containment (stop new illegal POT and stop spending illegal headroom) MUST be deployable before historical reimbursement is complete.
- **FR-023**: Repair and refund execution MUST be idempotent (safe to re-run without double effects).
- **FR-024**: Rollout may use a temporary config flag for shadow vs enforce behavior only; after durable rules are validated, no operational switch may re-open rarity ceilings.

### Key Entities

- **Rarity potential cap**: Absolute maximum potential allowed for a rarity (Common 75 / Rare 85 / Epic 92 / Legendary 99).
- **Effective potential**: min(stored potential, rarity cap) — used by progression while historical data may still be dirty.
- **Violating card**: Any card failing overall ≤ potential ≤ rarity cap or base potential ≤ rarity cap.
- **Repair category**:
  - **A** — illegal potential, legal overall (cap POT; no auto refund)
  - **B** — illegal overall and potential (normalize stats + POT; refund removed paid progression)
  - **C** — illegally generated at creation (normalize; refund only subsequent paid removed progression)
- **Repair audit record**: Immutable before/after snapshot per card/batch, refund amounts, confidence, repair/notification status (incident evidence, not gameplay).
- **Refund confidence**: EXACT | RECONSTRUCTED | MANUAL_REVIEW.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After containment, zero new cards are created or updated with potential (or base potential) above their rarity maximum, and overall never exceeds potential via “raise potential to match.”
- **SC-002**: At rarity boundaries, progression actions cannot increase attributes using headroom above the rarity maximum (Common 75 / Rare 85 / Epic 92 / Legendary 99).
- **SC-003**: A complete dry-run reimbursement report exists with every affected card classified and confidence labeled before any production card or balance mutation.
- **SC-004**: After production repair, the live anomaly count for potential integrity is exactly **0**, and recalculated overall equals stored overall for every repaired card.
- **SC-005**: Re-running repair/refund on already-processed cards produces **0** additional attribute changes and **0** additional coin / energy / SP refunds.
- **SC-006**: Every material ambiguous compensation case is either policy-resolved before production or left as **MANUAL_REVIEW** — none silently guessed into precise refunds.
- **SC-007**: Affected managers who can receive messages get one accurate post-commit notification; POT-only cases clearly state no resources returned.
- **SC-008**: Post-deploy lifecycle checkpoints (match processing, drills/evolutions, academy growth, youth/regen, season aging) keep anomaly count at **0**.
- **SC-009**: Competitive fairness outcome: Epic/Rare/Common cards cannot approach higher-tier ceilings than their rarity allows; Legendary scarcity is not undermined by illegal Epic ceilings.

## Assumptions

- Rarity caps in the problem statement are the frozen product law for this incident; no age-specific absolute POT caps are added here.
- Dual Python and database enforcement of the same mapping is acceptable if they remain the only two mapping sources and stay parity-tested (detail deferred to plan).
- Prefer fail-closed CHECK-style persistence rejection over silent trigger “fixes” that hide bugs.
- Two-phase rollout (guards + repair tooling, then validate durable constraints) is preferred over one irreversible mega-change.
- Drill economy metadata is a strong EXACT refund source where present; skill allocation often has only aggregate spent counters → RECONSTRUCTED or MANUAL_REVIEW as appropriate.
- XP/levels from matches, drills, and mentor generally stay; unspent SP may remain after caps.
- Fusion/item consumption without reconstructable history → MANUAL_REVIEW, not invented exact refunds.
- Temporary `potential_rarity_caps_enabled`-style config is rollout-only and must not survive as a way to disable the invariant.
- Deployed database function definitions are the authority for “what production does today”; repo migrations may be superseded — plan must verify live definitions before rewriting writers.
- User-facing copy for DMs follows the tone in the input plan (before/after OVR/POT, rarity law, resources returned or none required, apology).

## Out of Scope

- Redesigning youth academy rarity generation or gem rarity rules
- Algorithmic marketplace / transfer-market overpayment damages
- New monitoring dashboards or admin Discord economy commands
- New slash commands or hub buttons for players
- Automatically reversing Mentor Transfusion XP grants
- Removing legitimate drill/match/mentor XP solely because POT was illegal
- Age-based absolute potential ceilings beyond rarity
- Reopening evolutions after refunding their rewards
