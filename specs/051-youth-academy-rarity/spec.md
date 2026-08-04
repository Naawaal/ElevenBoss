# Feature Specification: Youth Academy Rarity-Cap Redesign

**Feature Branch**: `051-youth-academy-rarity`

**Created**: 2026-08-04

**Status**: Draft

**Input**: User description: "Youth Academy Rarity-Cap Redesign — redesign academy intake, scouting uncertainty, capacity, development, promotion limits, and facility progression so every academy-generated player obeys global rarity potential ceilings (Common 75 / Rare 85 / Epic 92 / Legendary 99); strengthen existing Youth Academy workflow without new slash commands or a second player table."

**Parent / related**: Extends Feature 015 Youth Academy ([`015-youth-academy`](../015-youth-academy/spec.md)) and rarity integrity ([`049-rarity-potential-integrity`](../049-rarity-potential-integrity/spec.md)). Academy upgrades remain under `/store` → Club Facilities. No new top-level slash command.

**Type**: Gameplay redesign / integrity-aligned academy V2.

---

## Problem Statement

The Youth Academy already exists as a managed holding phase (intake, growth, scout, promote/release, facility levels). It still conflicts with the game’s absolute rarity ceilings and creates too much long-run card supply.

Managers experience three problems today:

1. **Illegal or misleading potential.** Common academy prospects can appear or be generated with potential above 75. Exact potential and star displays can leak true ceiling quality before managers have earned that knowledge.
2. **Too generous retention.** Large academy capacity plus weekly free intake plus paid scouting can stockpile many prospects and later flood the senior club and market.
3. **Unclear long-term loop.** Facility upgrades should improve odds and development speed, not guarantee elite players or rewrite existing prospects.

Comparable football games keep youth exciting by combining a fixed intake moment, facility-driven probabilities, progressive scouting confidence, and a limited promote-to-first-team pathway. ElevenBoss should keep Discord-simple controls while adopting those product principles.

**Required product invariant for every academy-generated player:**

> overall ≤ potential ≤ rarity ceiling  
> Common 75 · Rare 85 · Epic 92 · Legendary 99

Academy upgrades may improve the chance of higher rarities. They must never raise a player above that rarity’s ceiling, and they must never reroll existing prospects’ rarity or potential.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Trust every academy player’s rarity ceiling (Priority: P1)

As a manager and as the competitive field, every youth prospect I receive or sign obeys the published rarity potential ceiling, and no academy action can create or grow illegal headroom.

**Why this priority**: Without a hard ceiling, academy becomes a free high-potential factory and undermines rarity integrity across the game.

**Independent Test**: Generate or sign academy prospects at every academy level and rarity; confirm each prospect’s potential never exceeds its rarity ceiling and overall never exceeds potential.

**Acceptance Scenarios**:

1. **Given** a Common academy prospect, **When** they are created or grown, **Then** potential never exceeds 75 and overall never exceeds potential.
2. **Given** Rare / Epic / Legendary academy prospects, **When** created or grown, **Then** potential never exceeds 85 / 92 / 99 respectively.
3. **Given** free Monday intake and paid scout signing, **When** either route produces a prospect, **Then** both routes apply the same rarity ceilings and validation rules.
4. **Given** a Youth Academy facility upgrade, **When** the upgrade completes, **Then** existing academy prospects keep their current rarity and potential (no reroll).

---

### User Story 2 - Receive a limited weekly youth intake (Priority: P1)

As a manager, every Monday I receive a small free intake that fills only available academy seats, so youth feels like a weekly event without overflowing my academy or senior club.

**Why this priority**: Intake is the heartbeat of the academy loop; capacity and count control must land before scouting polish.

**Independent Test**: With known free seats and academy level, run one Monday intake; confirm seated count equals min(configured intake count, free seats), no senior-roster dumping, and a second run the same week does not duplicate intake.

**Acceptance Scenarios**:

1. **Given** free academy seats and a successful Monday intake, **When** intake completes, **Then** I receive up to **2** new prospects seated in the academy (not the starting XI).
2. **Given** the academy is full, **When** Monday intake runs, **Then** no new prospects are seated and I am told capacity blocked intake (no backlog claim pile).
3. **Given** only one free seat, **When** intake would generate two, **Then** only one prospect is seated and the rest are skipped.
4. **Given** intake already succeeded this UTC week, **When** the weekly job retries, **Then** I do not receive a second free intake.

---

### User Story 3 - Evaluate uncertain potential through scouting (Priority: P1)

As a manager, I first see an approximate potential range for each prospect, then spend coins and time on scouting to narrow that range — without changing who the player truly is.

**Why this priority**: Uncertainty and discovery are the emotional core of youth; exact POT spoilers remove the hunt.

**Independent Test**: Open an unscouted prospect, run each scout tier in order, and confirm the visible range only narrows, still contains the true potential, and never reprints exact potential as the default Deep result.

**Acceptance Scenarios**:

1. **Given** a newly seated prospect, **When** I view the academy list, **Then** I see name, age, position, current OVR, rarity, an approximate potential range, development progress, and a readiness estimate — not exact potential by default.
2. **Given** an unscouted or lightly scouted prospect, **When** I buy a higher scout tier, **Then** the potential range narrows and never widens or rerolls the underlying potential.
3. **Given** Quick / Standard / Deep scout options, **When** I complete Deep, **Then** I receive a tight range (about 2–4 points) and development outlook, not a guaranteed exact POT reveal as the normal outcome.
4. **Given** star or quality indicators in the list, **When** displayed, **Then** they are based on the currently known scouting interval, not the hidden exact potential.
5. **Given** an active scout report on a prospect, **When** I try to start another conflicting report for the same prospect, **Then** the second start is rejected without double-charging.

---

### User Story 4 - Develop, promote, or release within limits (Priority: P2)

As a manager, prospects grow over time in the academy; I can promote ready or early graduates into the senior club (with weekly limits and optional fee) or release them to free a seat.

**Why this priority**: Promotion is the payoff of the loop; limits prevent stockpile dumps without removing agency.

**Independent Test**: Grow a prospect below readiness, promote early, promote a second prospect the same week, attempt a third promotion, and attempt promotion with a full senior roster; verify growth caps, graduation messaging, and clean failures.

**Acceptance Scenarios**:

1. **Given** a seated prospect below their potential, **When** daily academy growth runs, **Then** overall may rise but never past stored potential or the rarity ceiling.
2. **Given** a prospect below the recommended ready OVR for my academy level, **When** I choose Promote, **Then** early promotion is still allowed (readiness remains advisory, not a hard lock).
3. **Given** I have already promoted **2** academy players this UTC week, **When** I attempt another promotion, **Then** the action is blocked with clear copy until next week.
4. **Given** my senior roster is at soft cap, **When** I attempt promotion, **Then** promotion fails cleanly and the prospect remains in the academy.
5. **Given** a successful promotion, **When** the result is shown, **Then** I see a graduation milestone summary (name, OVR, rarity, age, time developed) and the player joins senior roster rules without duplicating the card.
6. **Given** I release a prospect, **When** release succeeds, **Then** the seat frees, no coin refund is granted, and that card cannot be promoted later.

---

### User Story 5 - Improve the academy through facilities, not rerolls (Priority: P2)

As a manager, upgrading Youth Academy improves capacity, rarity odds, initial scouting accuracy, and development speed — previewed before I pay — without mutating prospects I already hold.

**Why this priority**: Facility spend must feel meaningful and fair; rerolling existing youth would feel like a pay cheat or a rug-pull.

**Independent Test**: View next-level preview at Store → Club Facilities, upgrade one level, confirm capacity/odds/range-width/growth effects change for future intake only, and existing prospects remain unchanged.

**Acceptance Scenarios**:

1. **Given** Youth Academy level 1–4, **When** I open the next upgrade preview, **Then** I see concrete before→after effects for capacity, rarity chances, scout-range width, and development speed.
2. **Given** I complete an upgrade, **When** I check existing academy prospects, **Then** their rarity and potential are unchanged.
3. **Given** academy levels 1–5, **When** comparing capacity, **Then** capacity follows **3 / 3 / 4 / 4 / 5** (not the old 4–10 curve).
4. **Given** academy level below 5, **When** free intake generates prospects, **Then** Legendary is unavailable; at level 5 Legendary remains extremely rare (~0.1%) and can be disabled by configuration without a new feature release.

---

### User Story 6 - Feel aging pressure without silent deletion (Priority: P3)

As a manager, older unpromoted prospects warn me, may slowly lose unused potential ceiling, and eventually force a promote-or-release decision after a grace period — without vanishing without notice.

**Why this priority**: Creates urgency and frees seats, but is less critical than ceiling integrity and weekly loop basics.

**Independent Test**: Advance an academy prospect through warning age, first possible decay season, age-out pending, and grace expiry; confirm warnings, bounded decay, and auto-release (not silent delete, not forced senior inflation).

**Acceptance Scenarios**:

1. **Given** an academy prospect reaches the warning age (recommended 20), **When** I view academy status, **Then** I see a clear aging warning before any decay can apply.
2. **Given** an unpromoted academy prospect aged 20+ at a season aging event, **When** decay resolves, **Then** potential may fall by at most 1, never below current OVR, and never above the rarity ceiling.
3. **Given** a prospect hits the age-out boundary (recommended 21), **When** grace begins, **Then** the prospect is marked pending age-out and I have a configured grace window to promote or release.
4. **Given** grace expires without promotion, **When** cleanup runs, **Then** the prospect is auto-released rather than silently deleted or auto-forced onto the senior roster.

---

### User Story 7 - Reach the academy from existing hubs (Priority: P2)

As a manager, I open the same Youth Academy experience from Development (primary) and optionally Squad, while Store still handles facility upgrades and Profile remains a temporary compatibility entry.

**Why this priority**: Discovery and habit matter, but the loop can exist before entry points are fully migrated.

**Independent Test**: Open Youth from `/development`, `/squad` (if present), and legacy Profile Manage Academy; confirm one shared academy experience and compact academy status on Squad/Profile.

**Acceptance Scenarios**:

1. **Given** I am on `/development`, **When** I choose Youth Academy, **Then** I open the academy hub showing level, capacity, next intake, weekly promotions used, scout status, and prospects.
2. **Given** `/squad` exposes Youth, **When** I open it, **Then** I reach the same academy experience (not a second conflicting UI).
3. **Given** legacy `/profile` → Manage Academy still exists during transition, **When** I open it, **Then** it opens the same academy experience.
4. **Given** Squad or Profile summary embeds, **When** shown, **Then** a compact academy line appears (occupied/capacity and next intake).
5. **Given** this feature ships, **When** I look for commands, **Then** there is still **no** `/academy` slash command.

---

### User Story 8 - Existing illegal or over-capacity academies are handled fairly (Priority: P1)

As a manager who already holds academy prospects, the redesign corrects illegal potentials without deleting my current OVR progress, and if I am over the new capacity I keep my current prospects but cannot add more until I free seats.

**Why this priority**: Live clubs must survive the cutover without feeling robbed or soft-locked into deletion.

**Independent Test**: Audit sample illegal Common/Rare/Epic/Legendary academy cards and an over-capacity club; after cutover, potentials are legal, OVR is not reduced, over-capacity shows clearly, and new intake/signing is blocked until under capacity.

**Acceptance Scenarios**:

1. **Given** an academy card with illegal potential above its rarity ceiling but legal overall, **When** correction runs, **Then** potential is lowered to the legal ceiling (or overall if higher than the illegal potential floor rule requires) and current overall is not reduced.
2. **Given** a card whose overall already exceeds its rarity ceiling, **When** academy cutover runs, **Then** it is escalated for separate global rarity handling rather than silently “fixed” by inventing a higher rarity.
3. **Given** I hold more prospects than the new capacity, **When** the new rules go live, **Then** all existing prospects remain, the UI shows over-capacity (e.g. 5/3), and new free intake / paid signing is blocked until I promote or release down to capacity.
4. **Given** cutover initializes scouting bounds, **When** I open existing prospects, **Then** I see ranges that contain the true potential rather than an immediate exact POT dump.

---

### Edge Cases

- Manager registers after the Monday job: no retroactive free intake by default for that week.
- Partial seat availability during intake: seat only what fits; no senior-roster overflow.
- Double-tap promote/scout/release: one successful mutation; no duplicate cards or double charges.
- Scout completion after prospect was released/promoted: completion fails safely; no coin double-charge on retry.
- Legendary kill-switch enabled: Legendary academy weight behaves as zero without removing other rarities.
- Configuration weights that do not total 100% or bands that exceed rarity ceilings: rejected/validated before use.
- Paid scouting and free intake competing for the same last seat: both respect shared capacity and weekly signing limits.
- Promotion fee configured as free for the first weekly promotion: still counts toward the weekly promotion cap.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST enforce overall ≤ potential ≤ rarity ceiling for every academy-generated or academy-signed player (Common 75, Rare 85, Epic 92, Legendary 99).
- **FR-002**: System MUST resolve rarity before finalizing potential during academy generation, then clamp potential into that rarity’s legal generation band and hard ceiling.
- **FR-003**: Free Monday intake MUST remain the only free academy heartbeat and MUST be idempotent per manager per UTC week.
- **FR-004**: Default free intake MUST generate at most **2** prospects and seat only into free academy capacity (no backlog, no automatic senior placement).
- **FR-005**: Academy capacity by level MUST be **3 / 3 / 4 / 4 / 5**.
- **FR-006**: Academy level MUST influence only rarity distribution, initial scout-range width, capacity, and development speed — not direct post-generation potential grants and not rerolls of existing prospects.
- **FR-007**: Legendary academy generation MUST be unavailable below level 5, remain extremely rare at level 5 by default (~0.1%), have no pity guarantee, and be independently disableable by configuration.
- **FR-008**: Managers MUST see potential as a range by default; list quality indicators MUST derive from the known scouting interval, not hidden exact potential.
- **FR-009**: Scouting MUST narrow visible bounds around the already-created potential, MUST NOT reroll potential/rarity/attributes, MUST NOT widen ranges, and MUST prevent conflicting duplicate reports without double-charging.
- **FR-010**: Deep/complete assessment MUST NOT normally reveal exact stored potential as the default presentation; it MAY leave a 0–2 point range only if configured as a late/complete assessment benefit.
- **FR-011**: Daily academy growth MUST never raise overall above stored potential or the rarity ceiling.
- **FR-012**: Promotion readiness OVR by academy level MUST remain advisory; early promotion MUST stay allowed.
- **FR-013**: System MUST allow at most **2** academy promotions per manager per UTC week by default.
- **FR-014**: Promotion MUST be atomic with roster-cap checks, optional/configured coin fee, graduation messaging, and no card duplication.
- **FR-015**: Release MUST free capacity, grant no refund, and prevent later promotion of that released academy card.
- **FR-016**: Free intake and paid scout signing MUST share academy capacity and a weekly signing/promotion ledger so paid scouting cannot bypass retention limits.
- **FR-017**: Aging MUST warn before decay, apply at most 0–1 potential loss per configured season aging event for unpromoted prospects at/above decay age, never below overall, and age-out MUST use grace then auto-release rather than silent delete or forced senior inflation.
- **FR-018**: Primary entry MUST be `/development` → Youth Academy; `/squad` → Youth MAY open the same experience; `/profile` Manage Academy MAY remain temporarily as compatibility; Store → Club Facilities remains the upgrade surface; no `/academy` command.
- **FR-019**: Facility upgrade preview MUST show concrete next-level effects for capacity, rarity chances, scout-range width, and development speed.
- **FR-020**: Cutover MUST audit illegal academy potentials, correct them without reducing current overall when overall is legal, grandfather over-capacity academies, initialize scouting ranges, and roll out behind a feature flag.
- **FR-021**: All academy balance values in this redesign MUST be configuration-driven and validated on load (weights sum, non-negative costs/durations, non-decreasing capacity, bands within caps, Legendary weight zero when disabled).
- **FR-022**: Client/bot-submitted rarity, potential, or final attributes MUST NOT be trusted as source of truth for academy generation or signing.
- **FR-023**: Academy players MUST remain in the same player-card lifecycle as the rest of the club; the feature MUST NOT introduce a second canonical academy-player inventory.
- **FR-024**: System MUST expose monitoring signals for generation volume, rarity mix by academy level, promote/release rates, Legendary counts, capacity blocks, and academy-origin market activity, plus an independent Legendary kill switch.

### Key Entities

- **Academy Prospect**: A youth player held in academy capacity with rarity, overall, true potential, visible potential range, development progress, assessment level, origin (weekly intake / paid scout / migration / admin), and lifecycle timestamps (seated, graduated, age-out pending).
- **Youth Academy Facility**: Club facility level (1–5) that sets capacity, rarity odds, initial range width, and growth speed for future prospects.
- **Weekly Intake Event**: Monday UTC free generation attempt, limited by configured count and free seats, recorded once per manager per week.
- **Scout Assessment**: Paid/time-gated narrowing of a prospect’s visible potential range and readiness information without changing underlying identity.
- **Academy Weekly Actions**: Per-manager weekly counters for promotions and paid signings.
- **Graduation**: Successful transition from academy holding to senior club membership, with milestone summary for the manager.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of newly generated or newly signed academy prospects obey rarity potential ceilings in acceptance testing across all academy levels.
- **SC-002**: After cutover repair, 100% of previously illegal-but-repairable academy potentials are within rarity ceilings without reducing legal current overall.
- **SC-003**: In a full academy, Monday intake seats 0 new prospects and communicates the capacity block in the academy surface.
- **SC-004**: Managers can identify approximate potential and improve confidence through scouting without being shown exact potential as the default Deep outcome.
- **SC-005**: At least 95% of promote/scout/release retries in test harnesses produce no duplicate cards and no duplicate coin charges.
- **SC-006**: No manager can complete more than 2 academy promotions in a single UTC week under default configuration.
- **SC-007**: Youth Academy L5 Legendary share remains below 0.2% of generated L5 prospects over a monitored sample large enough to observe rarity mix (order of thousands of generations), or 0% when the Legendary kill switch is on.
- **SC-008**: Managers can open the full academy loop from `/development` in one hub flow with no new top-level command.
- **SC-009**: Over-capacity grandfathered clubs retain all existing prospects and are blocked from new acquisitions until at or below capacity.
- **SC-010**: Facility upgrade previews state concrete numeric before→after effects, and upgrades do not change existing prospects’ rarity/potential in spot checks.

---

## Assumptions

- Global rarity ceilings from rarity-integrity work remain the source of truth; this feature aligns academy generation and presentation to them rather than inventing different caps.
- Existing Monday intake scheduling, daily academy growth, promote/release actions, scout tiers, and Store facility upgrades are retained and rebalanced rather than replaced with a second academy product.
- Readiness OVR stays advisory (early promote allowed) to avoid soft-locking weak clubs.
- Default promotion fee is 500 coins and may be configured; first promotion in a week may be free if configuration says so, but still counts toward the weekly cap.
- Seven-day post-promotion trade lock is deferred unless live market data later shows academy dumping; not required for first release.
- Auto-release after age-out grace is preferred over auto-promotion into a full or inflated senior roster.
- Profile → Manage Academy remains available for at least one release as compatibility, then may be removed based on usage.
- No academy-specific currency, coaches, youth matches, loans, morale systems, pity Legendary, or pre-promotion trading in this release.

---

## Out of Scope

- New `/academy` slash command or a second top-level hub command family.
- A second canonical academy-player table or duplicated card lifecycle.
- Academy-only currency, staff hiring, coach inventories, youth leagues/matches, prospect morale, training-plan trees, position conversion, loans, negotiable youth contracts, regional scouting maps.
- Guaranteed rarity pity or paid rerolls of existing prospects.
- Prospect trading before promotion.
- Automatic rarity upgrades during cutover merely to preserve illegal potential.

---

## Dependencies

- Existing Youth Academy manager experience (Feature 015) and its intake/growth/scout/promote/release surfaces.
- Global rarity potential integrity rules (Feature 049).
- Existing Store → Club Facilities upgrade flow and Youth Academy level progression.
- Existing senior-roster soft-cap and economy ledger behavior for fees/refunds policy.
