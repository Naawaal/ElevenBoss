# Feature Specification: Youth Academy Integration & Functional Workflow

**Feature Branch**: `015-youth-academy`

**Created**: 2026-07-12

**Status**: Draft

**Input**: User description: "Youth Academy Integration & Functional Workflow Design — facility exists in UI but lacks proper gameplay integration; design end-to-end scouting/intake, academy development, promotion, release, economy/calendar/roster hooks, balancing, and UX informed by EA FC Career Mode, Football Manager, and Top Eleven, from the manager's perspective."

## Problem Statement

Managers can upgrade the Youth Academy in Club Facilities and receive weekly intake prospects, but the academy does **not** feel like a managed system. Prospects land on the senior roster with little academy identity, there is no clear develop → promote → integrate loop, and upgrading the facility mainly changes intake numbers rather than giving managers a place to *run* an academy.

Comparable football management games solve this differently:

| Title | Strength | Flaw for Discord |
|-------|----------|------------------|
| EA FC Career Mode | Hire scouts → timed region reports → promote when ready | Development feels disconnected from minutes |
| Football Manager | Annual intake day + U18/U21 pathway | Too much micromanagement for a bot |
| Top Eleven | Facility-tied youth with simple promote/release | Less identity / less “wonderkid hunt” |

**ElevenBoss v1 approach (manager-facing):** Keep Discord-simple controls. Use a clear **academy holding phase** (slots, growth, promote/release), keep **seasonal/weekly intake** as the free heartbeat for F2P login cadence, add **paid scouting** as a coin sink for active managers, and scale quality and capacity with academy level. Primary UI lives under **`/profile` → Manage Academy** (no new slash command). Pre-feature intake cards already on the senior roster stay senior (grandfathered); only new intake/scout signings use academy mechanics. No hidden U18 league in v1 — first-team match minutes remain the path to senior progression after promotion.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Open the Academy and Understand Status (Priority: P1)

As a manager, I open **Manage Academy** from `/profile` and immediately see academy level, how many youth slots I am using, which prospects I hold, whether any are recommended for promotion, and when the next free intake arrives — so the facility feels like a place I manage, not only an upgrade button.

**Why this priority**: Without a readable academy home, every other mechanic is invisible. This is the gap managers feel today.

**Independent Test**: With at least one academy prospect and a known academy level, open Manage Academy from /profile and verify level, slot usage, prospect list, and next-intake timing are all visible without asking support.

**Acceptance Scenarios**:

1. **Given** I am a registered manager, **When** I open `/profile` → Manage Academy, **Then** I see academy level (1–5), used/max youth slots, and a list (or empty state) of academy prospects with position, age, current rating, and growth-ceiling indication (star band or POT summary).
2. **Given** a prospect meets the promotion-ready guideline, **When** I view the academy list, **Then** that prospect is visually marked as ready (badge/icon/copy) without requiring me to open external docs.
3. **Given** I have never used the academy beyond upgrading the facility, **When** I open Manage Academy, **Then** short help copy explains intake → grow → promote/release in one screenful.
4. **Given** I am on `/profile`, **When** I look for academy gameplay, **Then** a **Manage Academy** control is present (YA upgrades remain under `/store` → Club Facilities; no separate `/academy` slash command).

---

### User Story 2 - Receive and Seat Intake Prospects (Priority: P1)

As a manager, when weekly youth intake arrives, new prospects enter my **academy**, not my first-team XI, so I can choose who to develop and who to release without automatically bloating the senior roster.

**Why this priority**: Fixes the core “missing integration” — intake today joins the roster with no academy phase.

**Independent Test**: Trigger (or simulate) one weekly intake for a club with free academy slots; confirm prospects appear in the academy list and are not auto-assigned to the starting XI.

**Acceptance Scenarios**:

1. **Given** free academy slots and a successful weekly intake, **When** intake completes, **Then** new prospects appear in the academy with ages in the youth band, ratings within the current academy-level quality band, and a growth ceiling scaled by academy level (including a small chance of a “gem” at higher levels).
2. **Given** intake completes, **When** I check my starting XI, **Then** no new prospect was auto-inserted into the XI.
3. **Given** I miss the intake DM, **When** I open the Academy surface later that week, **Then** I can still see this week’s seated prospects (intake is not DM-only).
4. **Given** academy slots are full (or partially full) at intake time, **When** intake would add prospects, **Then** the system partial-seats any available slots and skips the remaining prospects; a notification clearly states how many were skipped due to a full academy; the manager is not prompted to choose whom to replace.

---

### User Story 3 - Watch Academy Prospects Grow (Priority: P1)

As a manager, academy prospects improve over calendar time while seated in the academy, faster and toward higher ceilings when my academy level is higher, without forcing me to run a second drill UI every day.

**Why this priority**: Development is what makes “keeping” a youth feel rewarding between Mondays.

**Independent Test**: Note a prospect’s rating/progress on day 0; after one daily growth tick (or equivalent test advance), progress has increased within the published model and never exceeds that prospect’s growth ceiling.

**Acceptance Scenarios**:

1. **Given** a seated academy prospect below their growth ceiling, **When** a daily academy growth tick runs, **Then** their development progress increases by an amount that scales with academy level and their ceiling.
2. **Given** a prospect at their growth ceiling, **When** growth ticks run, **Then** their current rating does not rise further (no soft overflow past potential).
3. **Given** two clubs at different academy levels with similar prospects, **When** the same number of growth ticks elapse, **Then** the higher-level academy shows meaningfully faster progress and/or higher attainable ceilings consistent with published tier bands.
4. **Given** I open the academy list, **When** multiple prospects are shown, **Then** I can compare relative progress (e.g. progress toward ready / toward ceiling) without opening each card individually.

---

### User Story 4 - Promote a Prospect into the Senior Club (Priority: P1)

As a manager, I promote a ready (or early) academy prospect into the senior club when I have roster space, after which they use normal senior progression (matches, drills, skill points) and appear in the same player profile UI as other cards.

**Why this priority**: Promotion is the payoff that connects academy to matches and squad management.

**Independent Test**: Promote one prospect with free senior roster capacity; confirm they leave academy slots, appear on the senior roster (unassigned to XI unless I assign them), and can be opened in the normal player profile.

**Acceptance Scenarios**:

1. **Given** an academy prospect and free senior roster capacity, **When** I confirm promote, **Then** they leave the academy, consume a senior roster slot, and are available to assign in squad management.
2. **Given** the senior roster is at capacity, **When** I attempt promote, **Then** promotion is blocked with a clear message telling me to free a senior player first (sell/release/retire path already available in the game).
3. **Given** a prospect below the “ready” guideline, **When** I still choose promote, **Then** I may promote early (no hard rating lock), with copy that early promotion is allowed but growth in the academy would have continued.
4. **Given** a promoted player, **When** I open their profile, **Then** I see the same profile surfaces as other senior players (stats, potential, age lifecycle), not a dead-end “youth-only” view.

---

### User Story 5 - Release Underperforming Academy Prospects (Priority: P2)

As a manager, I can release academy prospects to free slots when I want a better intake or scouted talent, knowing what happens to the released player.

**Why this priority**: Slot pressure is required for meaningful choices; without release, a full academy stalls the feature.

**Independent Test**: Release one non-promoted prospect; slot count decreases by one and the player is no longer listed in the academy.

**Acceptance Scenarios**:

1. **Given** at least one academy prospect, **When** I confirm release, **Then** they leave the academy immediately and the slot frees.
2. **Given** I release a prospect, **When** the action completes, **Then** clear copy states the outcome: they are gone from my club (v1 default: not retained as a sellable senior asset; see Assumptions for free-agent handling).
3. **Given** I cancel the confirm step, **When** I return to the list, **Then** the prospect is unchanged.

---

### User Story 6 - Paid Scouting Assignment (Priority: P2)

As a manager, I can spend coins on a timed scouting assignment that returns a shortlist of extra prospects I may sign into free academy slots, as a supplement to (not a replacement for) Monday free intake.

**Why this priority**: Hybrid talent model — Monday intake retains F2P weekly login value; paid scouting is the active-manager coin sink. Secondary only to seating/grow/promote (P1) so the academy loop ships even if scouting lands in the same release behind P1.

**Independent Test**: Pay for one scout assignment, wait until it completes, review the shortlist, and sign one prospect into a free slot (or be blocked if full).

**Acceptance Scenarios**:

1. **Given** enough coins and no scout already in progress, **When** I start a scouting assignment at a chosen depth/cost tier, **Then** coins are taken only if the assignment successfully starts, and I see a finish time.
2. **Given** a finished assignment, **When** I open the report (DM and/or Academy inbox), **Then** I see a small shortlist (e.g. 3) with star-band / ceiling indication and may sign up to the allowed number into free slots.
3. **Given** academy slots are full, **When** I try to sign from a report, **Then** signing is blocked until I release or promote someone; the report remains claimable until it expires.
4. **Given** insufficient coins, **When** I try to start scouting, **Then** the action fails with a clear balance message and no timer is started.

---

### User Story 7 - Facility Level as Meaningful Academy Power (Priority: P2)

As a manager, each Youth Academy level clearly improves capacity and/or intake quality and growth so upgrading remains a long-term investment alongside Training Ground and Hospital — without making youth so strong that buying/signing seniors becomes pointless.

**Why this priority**: Preserves the existing facility ladder’s value while curing “upgrade does nothing I feel.”

**Independent Test**: Compare published L1 vs L5 benefits on the Academy/Facilities UI; verify slot and quality bands match the tier table in Requirements.

**Acceptance Scenarios**:

1. **Given** academy level N, **When** I view facilities or academy help, **Then** I see the current max slots, intake quality band, and growth benefit for that level.
2. **Given** I upgrade the academy under existing facility rules (cost, match gate, weekly upgrade slot), **When** the upgrade completes, **Then** new benefits apply to subsequent intake/growth (in-flight scout reports keep the rules stated in Edge Cases).
3. **Given** economy balance goals, **When** a manager only uses academy paths, **Then** acquiring competitive seniors via packs/market remains a viable parallel path (academy is strong for long-term POT, not an instant first-team wipe).

---

### Edge Cases

- **Academy full at weekly intake:** Partial-seat free slots only; skip the rest with a clear skipped count; never delete or prompt to replace existing academy players.
- **Academy full when signing a scouted star:** Signing blocked until a slot is freed; report stays available until expiry.
- **Promote with senior roster full:** Blocked with actionable copy (free a senior first).
- **Prospect ages out of academy band:** If a prospect reaches the maximum academy age without promotion, the club is notified; default outcome is forced promotion attempt, else release to free-agent / removal with clear DM (no infinite academy parking).
- **Insufficient coins for scouting or facility upgrade:** Action refused; no partial timer/upgrade.
- **Upgrade during active scouting:** Scouting may continue; growth/intake benefits of the new level apply from the stated rule (default: growth uses current level each tick; already-generated scout shortlists are not retroactively rerolled).
- **Double-tap promote/release/scout:** Second action is idempotent or clearly rejected; no duplicate seniors or double coin charge.
- **DMs disabled:** Intake and scout-report content remain reachable from the Academy surface (hub is source of truth).
- **Bot-controlled clubs:** AI clubs may skip interactive academy UI but must not break shared intake/aging jobs for human clubs.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Managers MUST reach a dedicated Youth Academy surface via `/profile` → Manage Academy (no new slash command) that shows level, slot usage, prospect list with progress, promotion-ready markers, next free intake timing, and entry points for promote / release / scout.
- **FR-002**: Weekly free youth intake MUST continue on the existing Monday UTC cadence as the baseline talent faucet, with quality still scaled by Youth Academy level (existing tier bands remain the quality source of truth unless rebalanced in planning).
- **FR-003**: New intake prospects MUST be seated in the **academy** (holding phase) rather than auto-joining the starting XI; they MUST NOT be match-eligible for senior competitive matches until promoted.
- **FR-004**: Academy capacity MUST be finite and scale with academy level (default ladder below). Managers MUST NOT exceed max academy slots.
- **FR-005**: While seated, prospects MUST receive passive calendar growth toward their individual growth ceiling; growth rate MUST improve with higher academy level. Managers MUST NOT be required to run a separate daily youth-drill loop for v1.
- **FR-006**: Managers MUST be able to promote an academy prospect into the senior club when under the senior roster soft cap (default 48 non-academy non-retired cards); promoted players MUST use the same senior progression and profile UX as other club players.
- **FR-007**: The system MUST recommend promotion when a prospect reaches a published ready guideline (default: current rating ≥ 65), without hard-blocking earlier promotion.
- **FR-008**: Managers MUST be able to release academy prospects to free slots, with explicit confirmation and clear outcome copy.
- **FR-009**: Youth Academy facility upgrades MUST remain on the existing Club Facilities investment rules (costs, match gates, shared weekly upgrade cadence with Training Ground) and MUST update published academy benefits (slots, intake quality, growth).
- **FR-010**: All academy coin charges (scouting and facility upgrades; promote fee only if economy planning enables it) MUST go through the club economy pipe and MUST validate balances before committing side effects.
- **FR-011**: Intake and scout-report outcomes MUST remain visible in Manage Academy even if Discord DMs are disabled or missed.
- **FR-012**: Prospects who age out of the academy band without promotion MUST be resolved automatically (attempt promote, else release/remove) with manager notification — no indefinite parking.
- **FR-013**: v1 MUST NOT require a separate simulated reserve/U18 league for academy growth; senior match XP applies only after promotion.
- **FR-014**: Scouted and intake prospects MUST expose enough signal for decisions (position, age, current rating, star-band or ceiling summary). Exact stats MAY be partially fogged on quicker/cheaper paid scout tiers.
- **FR-015**: v1 MUST use a **hybrid** talent model: keep weekly free Monday intake as the baseline faucet **and** ship paid timed scouting (US6 / P2) as a coin sink. Paid scouting MUST NOT replace or disable weekly intake.
- **FR-016**: The primary Academy surface MUST live under `/profile` → Manage Academy. The product MUST NOT add a new `/academy` (or equivalent) slash command for v1.
- **FR-017**: Pre-feature youth intake cards already on the senior roster MUST be **grandfathered** — they remain standard senior players with no forced move into the academy. Only prospects created after this feature ships (new weekly intake seating and scout signings) MUST use academy holding-phase mechanics.

### Default Academy Level Ladder (published for managers)

| Academy Level | Max Academy Slots | Intake / Prospect Quality (existing bands) | Growth |
|---------------|-------------------|--------------------------------------------|--------|
| 1 | 4 | OVR ~50–65 · POT cap ~82 · no gem | Baseline daily growth |
| 2 | 5 | Slightly higher OVR · POT ~85 · ~5% gem | Faster than L1 |
| 3 | 6 | Mid band · POT ~88 · ~10% gem | Faster |
| 4 | 8 | Higher band · POT ~91 · ~15% gem | Faster |
| 5 | 10 | Top band · POT ~94 · ~20% gem | Fastest |

Exact numeric growth formula is a planning deliverable; the spec requires monotonic improvement by level and a hard cap at each prospect’s ceiling.

### Default Paid Scouting Tiers (in scope — P2)

| Tier | Manager-facing wait | Relative cost | Shortlist |
|------|---------------------|---------------|-----------|
| Quick | Short (hours) | Low | 3 prospects, more fogged |
| Standard | Medium | Mid | 3 prospects |
| Deep | Long (~1 day) | High | 3 prospects, clearer star signal |

Costs MUST be tuned so packs/market seniors remain competitive (planning owns exact coin amounts).

### Key Entities

- **Youth Academy**: Per-club facility with level 1–5, slot capacity, and growth/intake modifiers.
- **Academy Prospect**: Young player held in the academy; has position, age, current rating, growth ceiling, progress toward ready; not senior-match-eligible until promoted.
- **Weekly Intake Event**: Free Monday UTC batch of prospects generated for human managers, quality scaled by academy level, seated into free academy slots.
- **Scouting Assignment**: Timed, paid search that produces an expiring shortlist the manager may sign into free academy slots (hybrid model; does not replace weekly intake).
- **Promotion**: One-way move from academy → senior club roster (not XI), subject to senior capacity.
- **Release**: Removal of an academy prospect to free a slot.
- **Senior Roster Capacity (New)**: A newly introduced soft cap (default 48) on non-academy, non-retired `player_cards` to prevent infinite hoarding and validate academy promotions; promotion consumes one unit of that capacity.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new manager can open Manage Academy from /profile and explain intake → grow → promote/release in under 2 minutes using only in-bot copy (no external wiki).
- **SC-002**: After one weekly intake with free slots, 100% of successfully seated prospects appear in the academy list and 0% are auto-inserted into the starting XI.
- **SC-003**: After at least 7 daily growth ticks, a below-ceiling academy prospect shows measurable progress toward ready/ceiling on the academy list.
- **SC-004**: In usability checks, ≥80% of managers correctly identify at least one “ready” prospect when one exists, and correctly state why promotion failed when the senior roster is full.
- **SC-005**: Managers with a full academy can free a slot via release or promote and seat a new prospect in a single session without support intervention.
- **SC-006**: Upgrading Youth Academy still feels worthwhile: L5 clubs show higher slot capacity and better intake quality than L1 clubs in side-by-side comparison.
- **SC-007**: Buying/signing seniors via existing store/market paths remains a rational alternative — academy graduates are not the only viable first-team path within the first two weeks of play for a new club.
- **SC-008**: Managers with DMs disabled can still complete intake review and promotion from Manage Academy alone.

## Assumptions

- Weekly Monday UTC intake (US-32) remains the free baseline; this feature **extends** it into an academy holding phase rather than deleting the cadence (**Q1: Hybrid** with paid scouting as P2).
- Primary UX entry is `/profile` → Manage Academy; YA upgrades stay under Club Facilities; no `/academy` slash (**Q2** revised).
- Pre-feature senior-roster intake cards stay senior with zero migration (**Q3: Grandfather**); only post-ship intake/scout prospects enter the academy.
- Passive growth is preferred over active youth drills in v1 (Discord attention budget; Training Ground already owns drill UX).
- No U18/reserve match simulation in v1 (ponytail / YAGNI); revisit only if retention data shows academy feels idle.
- Promotion-ready guideline defaults to current rating ≥ 65; early promote allowed.
- Released academy prospects are removed from the club in v1 (simple); optional free-agent listing can be a follow-up if market needs supply.
- Existing Youth Academy upgrade costs, match gates, and shared weekly facility upgrade slot stay as-is unless planning proves a rebalance is required.
- Existing intake quality tiers in Club Facilities remain the quality source of truth (OVR/POT/gem); slot ladder above is additive.
- Bot/AI clubs are out of scope for interactive academy UX; shared jobs must remain safe for human clubs.
- Star-band display is a UX translation of growth ceiling (e.g. higher POT → more stars), not a separate hidden stat managers must learn.
- Optional promote signing fee is off by default in v1 unless economy planning enables a small fee.
- Scout signal fog scales inversely with tier cost: Quick scouts return results with the highest fog (hidden stats/potential), while Deep scouts return results with the least fog; weekly free intake may show full band signals consistent with today’s intake embeds.

## Out of Scope (v1)

- Full Football Manager-style coaching staff, individual training schedules, and hidden U18 league simulation.
- Region-by-region scout map with dozens of countries (simple depth tiers only; no region map).
- Changing daily gacha pack odds via academy level (facility copy already states packs are unaffected).
- New website surfaces (Discord-only).
- Reworking Hospital or Training Ground beyond shared facility-upgrade cadence interactions.
