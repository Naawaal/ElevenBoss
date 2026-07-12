# Feature Specification: Active Fatigue Recovery

**Feature Branch**: `009-fatigue-recovery`

**Created**: 2026-07-12

**Status**: Draft

**Input**: User description: "Improve player fatigue recovery after research into EA Sports FC 26 Career Mode and Football Manager. Managers find bench-only recovery unsatisfying. Recommended path: (A) Active Recovery Sessions in the Development hub that restore fatigue without XP, plus (B) Training Ground level multiplies daily passive fatigue recovery. Physio consumables deferred."

## Background & Motivation

Managers report that the only meaningful recovery lever — benched starters for a modest per-match fatigue bump — feels like punishment rather than management. Passive recovery alone takes multiple real-world days for a drained player. Industry analogues (EA FC Career Mode Recovery training sessions; Football Manager Rest + sports-science facilities) give managers **agency** (choose recovery vs development) and **facility value** (better grounds recover faster). ElevenBoss already has Development drills and a Training Ground facility; this feature extends those surfaces rather than inventing new player-facing commands.

This feature **extends** `002-injury-fatigue-hospital` / US-39. Match drain, bench rest, injury Hospital, and fatigue match penalties remain in force unless explicitly changed below.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Schedule a Recovery Session (Priority: P1)

As a manager, I can send a tired (but available) player to a Recovery Session from the Development hub. The session completes immediately like a normal skill drill, restores a large chunk of fatigue, and grants no skill XP — so I am deliberately choosing fitness over development.

**Why this priority**: This is the core agency fix. Without an active recovery action, managers remain stuck with bench-or-wait. A Recovery Session alone is a shippable MVP that makes fatigue management feel intentional.

**Independent Test**: Start a Recovery Session on a fatigued starter from Development; wait until completion; confirm fatigue increased by the Recovery Session amount, XP unchanged, and the player was never required to sit a match to get that bump.

**Acceptance Scenarios**:

1. **Given** a non-injured player with fatigue below 100 and the manager has available Development drill capacity, **When** they start a Recovery Session on that player, **Then** the session completes immediately like other Development drills and is clearly labeled as Recovery (not a skill drill).
2. **Given** a Recovery Session completes successfully, **When** the manager views the result, **Then** the player's fatigue has increased by the Recovery Session amount (capped at 100), XP and level are unchanged, and no skill-stat bump occurred.
3. **Given** a player at fatigue 100, **When** the manager tries to start a Recovery Session, **Then** the action is rejected with a clear message that the player is already fully rested.
4. **Given** an injured player, **When** the manager tries to start a Recovery Session, **Then** the action is rejected and they are directed toward Hospital / injury recovery instead.
5. **Given** daily Development drill capacity is exhausted for the club or card, **When** the manager tries to start a Recovery Session, **Then** the action is rejected with the same class of capacity messaging used for skill drills.

---

### User Story 2 - Choose Recovery vs Skill Development (Priority: P1)

As a manager, when opening Development for a tired high-OVR starter, I can see both Skill Drill and Recovery Session options and understand the trade-off: skill progress vs fitness restore. Choosing Recovery does not feel like "wasting" a slot without explanation.

**Why this priority**: The strategic depth of the feature is the choice itself. If Recovery is hidden or unlabeled, managers will miss it and keep complaining about forced benching.

**Independent Test**: Open Development for a fatigued eligible player; confirm Skill and Recovery options are both visible with distinct outcomes described before committing.

**Acceptance Scenarios**:

1. **Given** a fatigued eligible player, **When** the manager opens Development drill choices for them, **Then** Recovery Session appears alongside skill drill options with copy that states fatigue restore, no XP, and duration/cost in the same terms other drills use.
2. **Given** the manager starts a Recovery Session, **When** the session is in progress, **Then** the player cannot simultaneously be in a skill drill (one active Development job per card, same as today).
3. **Given** a Recovery Session is in progress, **When** the manager views squad/fatigue UI, **Then** they can tell the player is recovering via session (not merely "on bench").

---

### User Story 3 - Training Ground Speeds Passive Recovery (Priority: P2)

As a manager with an upgraded Training Ground, my squad recovers more fatigue each daily recovery tick than a club with a lower (or no) Training Ground. Upgrading Training Ground feels valuable for senior-squad fitness, not only youth/drill XP.

**Why this priority**: Solves the multi-day wait for drained squads and rewards facility investment. Valuable alone, but secondary to the active Recovery Session because managers still want something they can do *now*.

**Independent Test**: Compare two clubs at different Training Ground levels after one daily recovery pass on equally fatigued cards; the higher TG club gains more fatigue (until the 100 cap).

**Acceptance Scenarios**:

1. **Given** a club with Training Ground level N, **When** daily passive fatigue recovery runs for a non-hospital card, **Then** fatigue increases by the published TG-scaled daily amount (capped at 100).
2. **Given** Training Ground level 0, **When** daily passive recovery runs, **Then** the base daily amount applies (no TG bonus).
3. **Given** a club upgrades Training Ground, **When** the next daily recovery runs, **Then** the new higher amount applies without requiring a separate facility "recovery unlock."
4. **Given** a player is in Hospital for injury, **When** daily recovery runs, **Then** injury Hospital fatigue rules from the existing hospital feature continue to apply; TG passive scaling does not replace Hospital care.

---

### User Story 4 - Bench Rest Remains a Soft Lever (Priority: P3)

As a manager, I can still gain a modest fatigue bump by leaving a player on the bench for a competitive match. Bench rest is no longer the *only* recovery strategy, but it remains useful for light rotation between Recovery Sessions and matches.

**Why this priority**: Preserves existing squad-rotation feel from US-39 without forcing managers to use Recovery Sessions for every point of fitness. Lower priority because P1–P2 already solve the primary complaint.

**Independent Test**: Bench a fatigued player for a full competitive match; confirm the existing bench-rest bump still applies alongside the new Recovery / TG paths.

**Acceptance Scenarios**:

1. **Given** a player sits unused on the bench for a full competitive match, **When** the match ends, **Then** they still receive the existing bench-rest fatigue bump (unchanged amount unless a later balance pass revises it).
2. **Given** a player completed a Recovery Session earlier the same day, **When** they also sit a match on the bench, **Then** both recovery sources may apply (subject to the 100 fatigue cap); neither cancels the other.

---

### Edge Cases

- Player fatigue is near 100 (e.g. 90): Recovery Session still completes and restores only up to 100 (no overshoot / waste messaging optional but clear cap).
- Player becomes injured while a Recovery Session is queued or in progress: session fails or cancels cleanly; injury Hospital path takes precedence; no phantom fatigue credit.
- Club action energy / drill capacity is insufficient: Recovery Session cannot start; message matches existing Development affordability patterns.
- Double-tap / concurrent start of two Recovery Sessions on the same card: only one active Development job; second attempt rejected.
- Bot-controlled clubs: passive TG-scaled recovery still applies on the daily tick; bots do not need interactive Recovery Session UI for correctness of league simulation.
- Season reset / Monday jobs: daily fatigue recovery continues to coexist with aging and other daily jobs without skipping either.
- Friendlies: remain sandbox for fatigue drain (per US-39); Recovery Sessions may still be run outside matches as Development actions.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST offer a Recovery Session action on the existing Development hub surface (no new slash command).
- **FR-002**: Recovery Session MUST be schedulable only on non-injured player cards owned by the manager's club with fatigue strictly below 100.
- **FR-003**: On successful Recovery Session completion, system MUST increase that card's fatigue by a fixed Recovery amount (default **+40**), clamped to 100, and MUST NOT grant XP, skill points, or direct stat increases.
- **FR-004**: Recovery Session MUST complete **immediately** in the same interaction pattern as skill drills (one confirm → result). There is no multi-hour wait or queued training job.
- **FR-005**: Recovery Session MUST cost **0 coins**. Resource costs beyond coins (e.g. club action energy) MUST follow the same affordability pattern as a Basic skill drill unless a later balance pass documents a different published cost.
- **FR-006**: Recovery Session MUST consume Development drill capacity (per-card and per-club daily limits) the same way skill drills do, so Recovery cannot bypass pacing caps.
- **FR-007**: System MUST present Recovery Session as a distinct choice from skill drills before the manager commits, including outcome summary (fatigue gain, no XP, duration, costs).
- **FR-008**: Daily passive fatigue recovery for non-hospital cards MUST scale with Training Ground level using: **base 15 + (Training Ground level × 5)** per day, clamped to 100. (Replaces the flat +20/day passive for non-hospital cards.)
- **FR-009**: Training Ground level 0 MUST yield exactly the base daily amount (15); higher levels MUST increase the daily amount linearly per FR-008.
- **FR-010**: Competitive-match bench-rest fatigue recovery MUST remain available at its current amount (+15 per unused bench match) and MUST NOT be removed by this feature.
- **FR-011**: Hospital injury recovery behavior and hospital daily fatigue rules MUST remain unchanged; TG passive scaling applies to the non-hospital passive path only.
- **FR-012**: Fatigue match drain, performance penalty tiers, and action-energy gates MUST remain unchanged; Recovery Sessions MUST NOT refill or bypass club action energy for matches.
- **FR-013**: Physio / sports-drink style instant full-fatigue consumables in the Store are **out of scope** for this feature.
- **FR-014**: Managers MUST receive clear success and failure feedback for Recovery Session start and completion (including capacity, injury, and already-rested cases).

### Key Entities

- **Player Card Fatigue**: Existing 0–100 fitness value per card; drained by competitive starts; restored by bench rest, passive daily recovery, and Recovery Sessions.
- **Recovery Session**: A Development action that restores fatigue, grants no XP, shares drill capacity/wait semantics with skill drills, and is mutually exclusive with an active skill drill on the same card.
- **Training Ground Level**: Existing club facility level that already affects drill XP; additionally multiplies/scales daily passive fatigue recovery per FR-008.
- **Bench Rest**: Existing post-match recovery for unused squad members; retained as a soft lever.
- **Hospital Care**: Existing injury recovery path; not replaced by Recovery Sessions.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A manager can restore at least **40 fatigue** on one tired starter within one Recovery Session cycle without fielding a weaker bench player in a match for that purpose.
- **SC-002**: A fully drained player (fatigue 0) at Training Ground level 5 reaches full fatigue (100) in **at most 3 daily recovery ticks** via passive recovery alone (40/day), vs **5+ days** under the prior flat +20/day rule.
- **SC-003**: In usability checks, managers can identify and start a Recovery Session from Development on the first attempt without asking support how to rest a starter outside of matches.
- **SC-004**: At least **90%** of Recovery Session completion attempts that were valid at start result in the expected fatigue credit (no silent no-ops).
- **SC-005**: Clubs with Training Ground level ≥ 3 show a clearly higher daily passive recovery amount than TG 0 clubs when both are measured on equally fatigued cards.
- **SC-006**: Support / feedback volume about “only way to recover is benching starters” drops after rollout (qualitative target: managers cite Recovery Session or faster TG recovery as the alternative).

## Assumptions

- Research takeaways from EA FC 26 Career Mode (Recovery training vs skill training; facility-gated recovery) and Football Manager (Rest / sports science as passive boost) are adopted as design inspiration only; ElevenBoss maps them onto Development + Training Ground rather than cloning those UIs.
- Recommended scope is **Solution A + B only**. Store physio consumables (Solution C) are deferred and require a separate feature if pursued.
- Recovery Session amount **+40**, **0 coins**, **0 XP**, Basic-drill energy cost are the v1 published numbers; balance may later move to config without changing the user stories. Sessions are instant (research R1: Development drills have no async job infra).
- Recovery Session consumes the same daily Development drill capacity as skill drills (agency = opportunity cost).
- Recovery Session energy cost mirrors Basic skill drill affordability so free infinite recovery is impossible.
- Bench rest **+15** remains; it is complementary, not removed.
- Passive formula change from flat **+20/day** to **15 + (TG × 5)** is intentional: TG 1 matches the old baseline; higher TG is an upgrade reward; TG 0 is slightly slower to incentivize facility investment.
- Hospital patients keep existing hospital daily fatigue behavior; they are not the primary audience for Recovery Sessions.
- No new slash commands, hubs, or tables beyond what Development drills and Training Ground already imply for the player-facing surface.
- Friendlies stay sandbox for match fatigue drain per existing US-39 policy.
- Bot clubs benefit from TG-scaled passive recovery automatically; interactive Recovery Sessions are a human-manager affordance.

## Out of Scope

- Instant full-fatigue Store consumables (physio kits / sports drinks).
- Changing match fatigue drain formulas or penalty tiers.
- Changing Hospital injury tiers, beds, or admit UI.
- Removing bench rest.
- New slash commands or a dedicated “Physio” hub.
- FM-style per-player “Rest from training” toggle separate from Recovery Sessions (Recovery Session covers the agency need in v1).
