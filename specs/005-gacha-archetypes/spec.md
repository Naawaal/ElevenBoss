# Feature Specification: Gacha Card Archetypes & Factory Reliability

**Feature Branch**: `005-gacha-archetypes`

**Created**: 2026-07-11

**Status**: Draft — analyze remediations applied 2026-07-11 (FR-006 / SC-004 locked)

**Input**: User description: "Elevate the gacha procedural pipeline with three Ponytail-compliant improvements: (1) Player Archetypes before stat distribution so same-position cards feel distinct (e.g. Poacher vs Speedster vs Complete Forward); (2) Deterministic OVR balancing that replaces fragile iterative while-loop adjustment with a single-pass delta so printed True OVR always matches the target; (3) Strict typed card contracts from the factory plus pack rarity/weight configs extracted so new pack types can be added by configuration without touching generation logic."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Distinct Card Identities from Packs (Priority: P1)

As a manager opening packs, I receive players of the same position and rarity who nonetheless feel different—one striker might be a clinical poacher, another a blistering speedster—so building a squad is about fitting styles together, not collecting interchangeable OVR numbers.

**Why this priority**: Homogenized cards are the main “flat gacha” complaint; without identity, rarity and OVR alone cannot create long-term squad-building depth.

**Independent Test**: Generate a batch of FWD cards at the same rarity/OVR band; confirm at least two different archetypes appear and that their primary stat emphases match the archetype’s intended profile (e.g. Poacher favors shooting/physical; Speedster favors pace/dribbling).

**Acceptance Scenarios**:

1. **Given** a new card is generated for a position, **When** creation runs, **Then** an archetype is chosen for that position *before* stats are rolled, and that archetype drives how attributes are emphasized.
2. **Given** two Epic FWDs are generated independently, **When** a manager compares them, **Then** they can differ in archetype (e.g. Poacher vs Speedster vs Complete Forward) and their attribute shapes reflect those identities—not identical “generic striker” spreads.
3. **Given** cards for DEF, MID, and GK are generated, **When** creation runs, **Then** each position group has its own archetype set (not FWD-only), including a balanced/complete option where appropriate.
4. **Given** a newly created card is saved and later viewed in squad or pack results, **When** the manager sees the card, **Then** the archetype identity is visible via the existing role/label surface managers already see on cards (no orphaned invisible identity).

---

### User Story 2 - Trustworthy Overall Ratings (Priority: P1)

As a manager, when a pack advertises a card at a given overall, that overall is accurate—the True OVR calculation matches the target band used at creation—so I never feel cheated by a “75” that secretly plays like a 72.

**Why this priority**: Rating trust underpins every rarity band and marketplace valuation; fragile balancing that can stop short leaves silent incorrect OVRs.

**Independent Test**: Generate hundreds of cards across rarities with fixed seeds where useful; assert every card’s computed True OVR equals the creation target (within the rules of the True OVR formula and legal attribute bounds).

**Acceptance Scenarios**:

1. **Given** a target overall is chosen for a new card, **When** base stats are produced and balanced, **Then** the final True OVR equals that target via a deterministic terminating correction (bulk estimate + finite greedy ±1)—no “gave up after N attempts” leftover mismatch.
2. **Given** the target is higher than the provisional True OVR, **When** balancing applies, **Then** points are added preferentially into the card’s primary (highest-weight) attributes for its archetype/position.
3. **Given** the target is lower than the provisional True OVR, **When** balancing applies, **Then** points are removed preferentially from secondary (lowest-weight) attributes, without breaking legal attribute bounds.
4. **Given** attribute floors/ceilings would block a perfect match in an extreme edge case, **When** balancing completes, **Then** the outcome is deterministic and documented (prefer exact match; if physically impossible under bounds, land on the closest achievable True OVR and never hang or retry indefinitely).

---

### User Story 3 - Configurable Pack Rules Without Rewriting Generation (Priority: P2)

As a product owner, I can define or adjust pack rarity mixes (and later add pack variants such as a Defender-focused pack) by changing pack configuration data—without rewriting the core player-creation pipeline—so new pack products ship safely and quickly.

**Why this priority**: Config separation unlocks future pack products; secondary to archetypes and OVR trust because today’s Standard pack already works, it just embeds magic numbers.

**Independent Test**: Change only the pack configuration for rarity weights (e.g. temporarily make Legendaries more common in a test config); confirm generation respects the new weights without edits to the core factory logic. Confirm factory output is a validated card contract (all required fields present) before any persistence path consumes it.

**Acceptance Scenarios**:

1. **Given** the Standard daily pack rarity mix (Common 60% / Rare 30% / Epic 8% / Legendary 2%), **When** packs are generated, **Then** those weights come from named pack configuration—not scattered literals inside generation control flow.
2. **Given** a new pack configuration entry is added (e.g. Defender Pack with position bias), **When** generation is invoked with that pack id, **Then** cards follow that config’s rules without requiring changes to the shared archetype + OVR factory steps.
3. **Given** the factory finishes creating a card, **When** the result is handed to gacha/intake/persistence adapters, **Then** the result is a fully validated typed card contract (required identity, position, rarity, OVR, six attributes, potential, age/DOB, archetype/role)—never an incomplete ad-hoc map that can silently omit keys.
4. **Given** v1 of this feature ships, **When** managers claim the existing Standard pack from `/store`, **Then** behavior remains the familiar 5-card pack with the same published rarity mix—only card *identity quality* and rating reliability improve (no surprise economy change).

---

### Edge Cases

- Attribute clamps (10–99 or project-standard bounds) prevent adding/removing more points—balancing must remain finite and deterministic.
- GK archetypes must not produce nonsensical outfield-heavy spreads that break True OVR expectations for keepers.
- Existing cards already in the database keep their current stats/role; this feature does not rewrite historical cards.
- Youth academy intake, starter-squad generation, and regen/bot creation paths that share the factory MUST receive the same archetype + deterministic balancing benefits (no half-wired callers).
- Pack config missing or unknown pack id — fail clearly in generation (typed error / explicit message), never silently fall back to unbalanced weights.
- Extreme target OVR at rarity band edges still produces legal cards within rarity rating ranges.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Player creation MUST select a position-appropriate **archetype** after position is known and before attribute distribution.
- **FR-002**: Each position group (FWD, MID, DEF, GK) MUST define at least three archetypes, including one balanced/complete option and two specialized options with clearly different primary-attribute emphases.
- **FR-003**: FWD archetypes MUST include at least: Poacher (heavy shooting/physical, weaker passing/pace relative to peers), Speedster (heavy pace/dribbling, weaker defending/physical), and Complete Forward (balanced within FWD weights).
- **FR-004**: Archetype selection MUST be stochastic with configurable weights per position (not a fixed rotation that makes packs predictable).
- **FR-005**: Attribute distribution MUST use the selected archetype’s weight profile (replacing a single static per-position weight table as the sole driver).
- **FR-006**: After provisional stats are rolled, creation MUST apply a **deterministic, terminating** overall correction so final True OVR matches the creation target whenever attribute bounds allow. This utilizes a bulk estimate followed by a finite greedy ±1 loop, abandoning the legacy `attempts < 10` random loop.
- **FR-007**: When raising OVR, correction MUST prefer the archetype’s top primary attributes; when lowering OVR, correction MUST prefer the weakest secondary attributes.
- **FR-008**: Creation MUST NOT rely on unbounded or capped retry loops that can exit with a mismatched True OVR under normal inputs.
- **FR-009**: Factory output MUST be a validated typed card contract including name, position, rarity, overall/base rating, six attributes, potential, age, date of birth, and archetype/role label.
- **FR-010**: Pack rarity (and related pack rule) weights MUST live in named pack configuration entries; the Standard pack MUST preserve today’s published mix (60/30/8/2) unless product explicitly changes it.
- **FR-011**: All current callers of unified player creation (daily packs, starter squad, youth intake, and any other factory consumers in scope) MUST consume the typed contract and archetype-aware pipeline—no leftover dict-only path that skips archetypes or deterministic balancing.
- **FR-012**: Archetype identity MUST populate the existing card **role** field (or equivalent already shown in squad UI) so managers see the identity without a new player-facing command surface.
- **FR-013**: v1 MUST NOT add a new slash command, hub button, or pack-claim economy change beyond making existing pack/intake quality better.
- **FR-014**: Match simulation formulas and PlayStyle synergy rules remain unchanged in v1; richer archetypes improve *input card shape* only (PlayStyle catalog expansion is out of scope unless already implied by role text).

### Key Entities

- **Player Archetype**: A named playing identity for a position (e.g. Poacher, Speedster) that defines relative attribute emphases used at creation.
- **Creation Target OVR**: The overall rating the factory aims to hit, typically drawn from the card’s rarity band.
- **True OVR**: The project’s authoritative overall computed from position, attributes, playstyles, and potential; creation must land on the target True OVR.
- **Typed Card Contract**: The validated card payload produced by the factory for all intake sources.
- **Pack Configuration**: Named rules for a pack product (rarity weights, optional position bias, card count) consumed by pack generation without embedding literals in control flow.
- **Card Role**: Existing manager-visible label on a card; in this feature it carries the archetype name.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a sample of 100 generated FWD cards at a fixed rarity, at least two distinct archetypes appear, and cards of different archetypes show measurably different mean primary-stat profiles (not interchangeable within noise).
- **SC-002**: In a sample of 500 generated cards across positions and rarities, 100% achieve True OVR equal to the creation target when bounds allow; zero cards exit creation with a silent mismatch caused by abandoned iterative balancing.
- **SC-003**: Managers viewing a newly obtained card in squad (or pack reveal if role is shown there) can name the card’s archetype/role without inspecting raw attribute math.
- **SC-004**: Standard pack rarity distribution remains within sampling tolerance of 60/30/8/2 over a simulated claim batch of **N ≥ 2000**: each rarity tier must fall within **±3 percentage points** of its target weight (e.g. Common between 57% and 63%). No accidental economy rebalance.
- **SC-005**: Adding a second pack configuration entry for a hypothetical Defender Pack requires no change to archetype selection or OVR-balancing steps—only pack config + a thin call-site selector.
- **SC-006**: All factory consumers used in registration, daily packs, and youth intake produce archetype-labeled, target-accurate cards in acceptance checks (no caller left on the old homogenizing path).

## Assumptions

- The existing `player_cards.role` column (default `Balanced`, already shown in squad embeds) is the persistence/display home for archetype names—no new table or slash command is required for v1.
- Historical cards keep their current role/stats; only newly generated cards receive archetypes from this pipeline.
- Position groups each get ≥3 archetypes; exact MID/DEF/GK names follow football conventions analogous to the FWD examples (plan phase locks the catalog).
- Archetype roll weights default to roughly even among options per position unless plan/tuning says otherwise; “Complete/Balanced” may be slightly more common if needed for economy feel.
- True OVR formula, rarity rating ranges, and pack size (5) stay as today.
- `GachaPlayer` / pack models already exist in the gacha package; factory-level typed output should align with or feed those contracts rather than inventing a parallel competing schema.
- Shipping a live “Defender Pack” or “Gold Pack” product to managers is **out of scope for v1**—config infrastructure must make them *easy*, not necessarily live.
- PlayStyle matching depth in the match engine is a downstream benefit of better stat shapes; expanding PlayStyle keys or synergy tables is not part of this feature.
- Constitution Principle III (typed models at package boundaries) is a governance constraint this feature explicitly restores for card creation.

## Out of Scope (v1)

- New manager-facing pack products (Defender Pack, Gold Pack, etc.) beyond config readiness.
- Rewriting or rebalancing True OVR / PlayStyle synergy formulas.
- Backfilling archetype labels onto existing cards.
- New slash commands, hubs, or pack-claim pricing changes.
- Marketplace listing UX redesign (aside from cards naturally showing richer roles where role is already displayed).
- Changing youth academy level curves or seasonal intake counts.
