# Feature Specification: Recovery QoL Balance

**Feature Branch**: `011-recovery-qol-balance`

**Created**: 2026-07-12

**Status**: Implemented

**Input**: User description: "Players say injury healing takes too much real time and fatigued players take too many matches/days to recover. Research EA FC 26, Football Manager, Top Eleven recovery cadence; then compress injury heal days and buff fatigue recovery (passive, bench, slight drain nerf) for Discord real-time cadence. Proposed numbers: injury bases 1/4/7 days; passive base +25/day with TG scaling so TG L3 ≈ +40/day; bench +25; base match drain 18."

## Background & Motivation

ElevenBoss runs on **real-world days** as the play cadence. Industry peers either compress injury clocks (Top Eleven: ~3–6 real days max), measure healing in **in-game** days that advance with matches (EA FC Career), or assume large squads plus daily play (Football Manager). On Discord, a 20-real-day Major injury or multi-day wait to refill fitness feels like a quit incentive, not a strategic pause.

This feature is a **balance / QoL patch**: same systems (injury tiers, Hospital, fatigue drain/bench/passive, Training Ground passive scaling, Recovery Session), retuned numbers so injuries are temporary hurdles and daily XI play stays sustainable.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Injuries Heal on a Discord-Friendly Clock (Priority: P1)

As a manager, when a player is injured, expected recovery is short enough that I rotate a backup for days—not weeks—and Hospital upgrades still meaningfully shorten that wait.

**Why this priority**: Long real-time injury clocks are the strongest quit risk called out in feedback.

**Independent Test**: Trigger or inspect each injury tier’s expected recovery window (untreated and with high Hospital); confirm new base day counts and that Hospital still reduces time vs untreated.

**Acceptance Scenarios**:

1. **Given** a **Minor** injury with no Hospital benefit, **When** recovery is computed, **Then** the base expected duration is **1 day** (not 3).
2. **Given** a **Moderate** injury with no Hospital benefit, **When** recovery is computed, **Then** the base expected duration is **4 days** (not 8).
3. **Given** a **Major** injury with no Hospital benefit, **When** recovery is computed, **Then** the base expected duration is **7 days** (not 20).
4. **Given** a Major injury at a high Hospital level, **When** recovery is computed, **Then** expected return is clearly shorter than untreated (on the order of ~half at top Hospital under the existing facility curve), and never longer than the new untreated base.
5. **Given** a player already mid-injury under old longer windows, **When** this patch ships, **Then** [Assumption: newly computed admits/upgrades use new bases; already-scheduled expected dates are not retroactively lengthened—see Assumptions].

---

### User Story 2 - Fitness Recovers Fast Enough for Daily Play (Priority: P1)

As a manager, my squad’s fitness climbs quickly enough via daily passive (and Training Ground) that I am not forced to shelve stars for multiple real days after a heavy stretch.

**Why this priority**: Equal to injuries for daily-loop frustration; enables the “play main XI often” fantasy.

**Independent Test**: Compare fatigue after one daily recovery tick at TG L1 vs TG L3 (and L5 if available); confirm amounts match the new published table.

**Acceptance Scenarios**:

1. **Given** a non-hospital card below full fatigue, **When** daily passive recovery runs with Training Ground at the club’s level, **Then** fatigue increases by **25 + (TG level × 5)** (capped at 100).
2. **Given** TG level 3, **When** daily passive runs, **Then** the bump is **+40** (25 + 15).
3. **Given** TG level 1, **When** daily passive runs, **Then** the bump is **+30** (25 + 5).
4. **Given** a card in Hospital, **When** daily fatigue recovery runs, **Then** the existing hospital daily fatigue path remains in force (this patch does not retune hospital fatigue separately unless already tied to the same passive keys).

---

### User Story 3 - Bench Rest Is a Strong Soft Lever (Priority: P2)

As a manager, parking a tired player on the bench for a competitive match restores a meaningful chunk of fitness (+25), so rotation between matches feels rewarding.

**Why this priority**: Complements passive buffs; smaller surface than injury/passive retunes.

**Independent Test**: Bench an unused squad member for a full competitive match; fatigue rises by 25 (cap 100).

**Acceptance Scenarios**:

1. **Given** a player sits unused on the bench for a full competitive match, **When** the match ends, **Then** they gain **+25** fatigue (not +15), capped at 100.
2. **Given** friendlies remain sandbox for fatigue writes, **When** a friendly completes, **Then** bench rest rules for competitive matches are unchanged in scope (no new friendly fatigue writes).

---

### User Story 4 - Daily Starters Accrue Fatigue Slowly (Priority: P2)

As a manager, playing my best XI once per day does not instantly dump them into deep fatigue; base match drain is lighter so passive recovery can keep pace with a single daily match.

**Why this priority**: Makes the recovery buffs feel coherent; without a drain nerf, buffs alone still feel like “always catching up.”

**Independent Test**: Fully rested starter (100) completes one competitive match with neutral typical conditions; fatigue loss is based on new base drain **18** (still modified by PHY / tactics / intensity as today).

**Acceptance Scenarios**:

1. **Given** the published drain formula still applies, **When** base drain is used, **Then** the base component is **18** (not 22).
2. **Given** PHY, tactic stance, and intensity modifiers, **When** drain is computed, **Then** those modifiers still apply on top of the new base (no removal of strategic modifiers).
3. **Given** a manager plays roughly one competitive match per day and applies daily passive, **When** comparing before/after this patch, **Then** sustaining a high-fatigue XI is easier (qualitative success: less forced multi-day benches solely for fitness).

---

### Edge Cases

- Fatigue near 100 with +25 bench or +40 passive — clamp at 100; no overshoot.
- Major injury + max Hospital — still shorter than untreated 7 days; never zero unless existing rules allow.
- Bot clubs — same formulas on daily recovery and match drain/bench.
- Recovery Session (+40 fatigue, energy cost) — **unchanged** by this patch unless explicitly retuned later.
- Cards already injured with long `expected_recovery_date` — see Assumptions (no silent extension; optional shorten is a product choice).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Injury base recovery durations MUST be **Minor = 1 day**, **Moderate = 4 days**, **Major = 7 days** (replacing 3 / 8 / 20).
- **FR-002**: Hospital MUST continue to shorten injury recovery via the existing facility multiplier curve; outcomes with high Hospital MUST remain strictly better than untreated for the same tier.
- **FR-003**: Non-hospital daily passive fatigue recovery MUST use **base 25 + (Training Ground level × 5)** per day, capped at 100 (replacing base 15 + TG×5).
- **FR-004**: Competitive match **bench rest** MUST grant **+25** fatigue (replacing +15), capped at 100.
- **FR-005**: Match fatigue **base drain** MUST be **18** (replacing 22); PHY / tactic / intensity modifiers remain.
- **FR-006**: Fatigue penalty tiers, injury chance soft-caps, Hospital beds/admit UI, Recovery Session mechanics, and action-energy rules MUST remain unchanged except where FR-001–FR-005 apply.
- **FR-007**: Tunables MUST be updated in the same places managers/ops already expect (runtime config and/or pure formula defaults) so Discord UI and match/daily jobs stay consistent.
- **FR-008**: No new slash commands, hubs, or consumable “instant heal” Store items in this feature.

### Key Entities

- **Injury recovery window**: Per-tier base days before Hospital shortening.
- **Daily passive fatigue**: TG-scaled daily bump for non-hospital cards.
- **Bench rest**: Post-match fitness gain for unused competitive squad members.
- **Match drain base**: Starting point of the post-match starter fatigue formula.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Untreated Major injury expected duration is **≤ 7 real days** (down from 20).
- **SC-002**: Untreated Minor injury expected duration is **≤ 1 real day**.
- **SC-003**: A card at 0 fatigue reaches 100 via passive alone in **≤ 4** daily ticks at TG ≥ 3 (+40/day), and in **≤ 4** ticks even at TG 1 (+30/day → 4 days to 120 capped at 100).
- **SC-004**: Bench rest after one competitive match restores **25** fatigue points (pre-cap).
- **SC-005**: Published base match drain constant used in calculation is **18**.
- **SC-006**: After rollout, manager feedback about “injury lasts forever” / “can’t recover fitness without multi-day benches” declines (qualitative); Hospital upgrades still cited as valuable for cutting Major waits roughly in half at top level.

## Assumptions

- Research takeaways (Top Eleven short real clocks; EA FC in-game-day healing; FM large-squad tolerance) justify **compression**, not cloning monetized instant-heal consumables in this patch.
- Passive formula remains `25 + (TG × 5)`; user’s “No TG = +25” is the **base** before TG bonus. Schema TG minimum remains 1 → effective floor **+30/day** at TG1; TG3 = **+40**; TG5 = **+50**.
- Hospital multiplier math is **not** redesigned—only injury **bases** change so L5 still roughly halves calendar time vs untreated.
- **Already-injured cards**: Prefer **not** lengthening existing expected dates. Optional one-time shorten of open hospital stays to new bases is allowed if cheap; default is **forward-only** (new injuries / new admits use new bases).
- Recovery Session (+40 / energy cost), injury probability, and fatigue **performance penalty** bands are out of retune scope here.
- Friendlies remain sandbox for competitive fatigue drain/bench writes.
- Discord cadence assumption: one meaningful “play day” ≈ one real day.

## Out of Scope

- Instant injury/fatigue Store consumables (Top Eleven–style “Rests”).
- New Rest toggles or FM-style medical staff entities.
- Changing Hospital upgrade costs, bed counts, or Profile Hospital UI layout.
- Changing Recovery Session fatigue grant or energy cost.
- Reworking match simulation injury chance or live sub UX.
- New slash commands or hubs.
