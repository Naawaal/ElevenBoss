# Feature Specification: Profile Finance & Hospital Hub

**Feature Branch**: `003-profile-finance-hospital`

**Created**: 2026-07-11

**Status**: Draft

**Input**: User description: "Unify Club Finance overview and Hospital facility into a single rich Discord embed under the existing `/profile` slash command, with actionable buttons for hospital management, finances, and club stats."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One-Stop Club Dashboard on `/profile` (Priority: P1)

As a manager, I run `/profile` and see my club’s wallet and medical status in one polished dashboard—alongside the existing club identity, energy, division, and record information—so I do not need to bounce between multiple commands to understand club health.

**Why this priority**: Delivers the core value of the feature without requiring new management flows. Extends the existing `/profile` surface managers already know.

**Independent Test**: Run `/profile` with a registered club that has coins, optional gems, and either no hospital or a leveled hospital with/without patients; confirm finance + hospital sections render correctly and existing profile fields still appear.

**Acceptance Scenarios**:

1. **Given** a registered manager with a club, **When** they run `/profile`, **Then** they see a single club dashboard embed that includes at least: club identity, coin balance, gems (when the club has a gems balance field), action energy, and a Hospital section.
2. **Given** the club has Hospital level ≥ 1, **When** they view `/profile`, **Then** the Hospital section shows facility level, bed usage (occupied/capacity), recovery speed multiplier for that level, and either a short list of injured patients with expected recovery dates or a clear “No injuries” message.
3. **Given** the club has Hospital level 0 (not built), **When** they view `/profile`, **Then** the Hospital section shows a clear empty state such as “No Hospital – build one in the Store!” and does not invent fake bed counts.
4. **Given** the club has no active hospital patients, **When** they view `/profile` with Hospital built, **Then** bed usage shows `0/N` (or equivalent) and the patient list area shows “No injuries” (or equivalent clear empty copy).
5. **Given** `/profile` already showed division, LP, match record, and trophy cabinet, **When** this feature ships, **Then** those existing sections remain available (extended, not removed).

---

### User Story 2 - Action Buttons Under the Profile Embed (Priority: P1)

As a manager, below the profile dashboard I get clear action buttons so I can manage the hospital, open finances detail, or jump to club/squad stats without memorizing other slash commands.

**Why this priority**: A read-only dashboard without actions fails the “one-stop” goal; buttons are what make `/profile` a hub.

**Independent Test**: Open `/profile`, press each button, confirm the correct sub-panel or hub opens, and confirm returning/refreshing updates the profile dashboard when hospital or finance-relevant state changes.

**Acceptance Scenarios**:

1. **Given** the profile dashboard is open, **When** the manager presses **Manage Hospital**, **Then** they enter a hospital management sub-panel where they can upgrade (when eligible), admit/discharge as already supported by Club Facilities hospital management, and see detailed patient info consistent with the existing hospital panel.
2. **Given** Hospital is not built (level 0), **When** the manager presses **Manage Hospital**, **Then** they still reach a useful path to build/upgrade (or a clear prompt directing them to Club Facilities / Store upgrade), not a dead end.
3. **Given** the profile dashboard is open, **When** the manager presses **Finances**, **Then** they see a finance detail panel with wallet summary and the wage/facility overview currently offered by the club finances command (transaction log is out of scope for v1).
4. **Given** the profile dashboard is open, **When** the manager presses **View Club Stats**, **Then** they are taken to the existing squad hub (or an equivalent club roster/stats surface already in product).
5. **Given** the manager upgrades the hospital or discharges a patient from a profile-opened hospital panel, **When** they return to or refresh the profile dashboard, **Then** level, bed usage, patient list, and coin balance reflect the new state.
6. **Given** button rows time out or the bot restarts, **When** the manager interacts with a stale message, **Then** they get a clear recovery path (e.g. re-run `/profile`) rather than a cryptic failure.

---

### User Story 3 - Graceful Empty, Missing-Club, and DM Contexts (Priority: P2)

As a manager (or would-be manager), `/profile` behaves predictably when I have no club, run the command in DMs, or when hospital data is temporarily unavailable—always with clear copy, never a raw error dump.

**Why this priority**: Edge handling protects trust; secondary to the happy-path dashboard.

**Independent Test**: Invoke `/profile` with no club, in DM with a club, and with hospital data missing/unavailable; confirm friendly messaging and no crash.

**Acceptance Scenarios**:

1. **Given** the user has no registered club, **When** they run `/profile`, **Then** they see a clear “create/register a club first” style message and no broken finance/hospital sections.
2. **Given** the user has a club and runs `/profile` in a DM, **When** the command succeeds, **Then** their own club dashboard is shown (same data as in a guild), unless product policy already forbids DMs—in which case a clear “use this in a server” message appears.
3. **Given** hospital patient data cannot be loaded, **When** `/profile` still has wallet/club identity, **Then** finance and core profile sections still render and the Hospital section shows a safe fallback (“Hospital status unavailable”) instead of failing the whole command.
4. **Given** many injured patients exceed a readable embed length, **When** the dashboard renders, **Then** the list is truncated with a clear “and N more — open Manage Hospital” style cue rather than overflowing Discord limits.

---

### User Story 4 - Soft Transition from Standalone Finance Command (Priority: P3)

As a manager who already uses `/club-finances`, I am guided toward the unified `/profile` hub without a hard break of my muscle memory in v1.

**Why this priority**: Reduces command sprawl over time without forcing a breaking removal in the first ship.

**Independent Test**: Run `/club-finances` after the feature ships; confirm it still works and points managers to `/profile` for the unified dashboard.

**Acceptance Scenarios**:

1. **Given** `/club-finances` exists today, **When** this feature ships, **Then** the command remains functional (no hard delete in v1).
2. **Given** a manager opens `/club-finances`, **When** the response is shown, **Then** it includes a short pointer that the unified club dashboard (finance + hospital) lives on `/profile`.
3. **Given** there is no standalone `/hospital` command today, **When** this feature ships, **Then** no new `/hospital` slash command is introduced; hospital management stays reachable from `/profile` and from Store → Club Facilities.

---

### Edge Cases

- Manager double-taps **Manage Hospital** or **Finances** — second press must not corrupt state; either refresh the same panel or ignore safely.
- Hospital upgrade succeeds but profile message is stale — returning via Back / Refresh must re-fetch coins, level, and patients.
- Club has Hospital level ≥ 1 but zero beds occupied and untreated injuries elsewhere — dashboard still shows bed usage and directs management via **Manage Hospital** (untreated injuries may appear in hospital panel admit flow, not necessarily on the summary list).
- Gems/tokens balance is zero — gems still display as `0` (or omit only if product already omits zero gems elsewhere; prefer consistent wallet display with coins).
- Bot-controlled clubs — no human `/profile` user; no special profile UI required.
- Matchday lock / season transition — profile remains read-oriented; management actions reuse existing facility/hospital rules and error copy.
- Persistent view after bot restart — stale buttons fail gracefully with “run `/profile` again”.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `/profile` MUST present a unified club dashboard that includes Club Finance and Hospital sections in addition to existing club profile content (identity, energy, division/record/trophies as already shown).
- **FR-002**: The Club Finance section MUST show current coin balance and gems (tokens) in a clear, scannable layout. A lightweight visual cue (e.g. text bar or compact summary line) MAY be used for balance emphasis; a full transaction ledger is NOT required in v1.
- **FR-003**: The Hospital section MUST show: hospital level; bed usage (`occupied/capacity`) when level ≥ 1; recovery speed multiplier for the current level; and a patient summary list with expected recovery dates, or an explicit empty-injuries message.
- **FR-004**: When Hospital level is 0, the Hospital section MUST show a not-built empty state that directs the manager to build via Store / Club Facilities (wording may match product tone, e.g. “No Hospital – build one in the Store!”).
- **FR-005**: The dashboard MUST include action controls beneath the embed: **Manage Hospital**, **Finances**, and **View Club Stats**.
- **FR-006**: **Manage Hospital** MUST open hospital management that reuses the existing Club Facilities hospital capabilities (upgrade, admit, discharge, patient detail)—reachable from profile without requiring the manager to start at `/store` first (Store path remains valid).
- **FR-007**: **Finances** MUST open a finance detail panel covering at least wallet + wage forecast / facility level summary equivalent to today’s `/club-finances` content. Transaction history is OUT OF SCOPE for v1.
- **FR-008**: **View Club Stats** MUST route to the existing squad hub (roster/formation surface).
- **FR-009**: After hospital upgrade, admit, or discharge performed from a profile-originated panel, returning to the profile dashboard MUST show updated coins, hospital level, beds, and patients.
- **FR-010**: `/profile` MUST handle no-club, DM-with-club, and hospital-data-unavailable cases with clear user-facing messages without failing the entire command when partial data is available.
- **FR-011**: Patient lists on the summary embed MUST respect Discord message size limits via truncation + “see Manage Hospital” cue when needed.
- **FR-012**: v1 MUST NOT add a new `/hospital` slash command.
- **FR-013**: v1 MUST keep `/club-finances` working and MUST add a short pointer to `/profile` as the unified dashboard.
- **FR-014**: Store → Club Facilities → Hospital Panel MUST remain a supported path (profile is an additional entry point, not a replacement that orphans Store).
- **FR-015**: Dashboard presentation MUST feel consistent with ElevenBoss hub polish (club-relevant emphasis, clear section labels, emoji affordances on buttons/sections) and MUST adapt empty states without placeholder junk data.

### Key Entities

- **Club Profile Dashboard**: The manager-facing `/profile` view combining identity, progression/league snapshot, finance summary, and hospital summary.
- **Club Wallet**: Coins and gems (tokens) belonging to the manager’s club.
- **Hospital Facility**: Club facility with level (0–max), bed capacity derived from level, and recovery speed multiplier.
- **Hospital Patient**: An injured player card currently occupying a hospital bed, with expected recovery date and injury severity context.
- **Profile Action Hub**: Button row on the dashboard that opens Hospital management, Finances detail, or Squad stats.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A registered manager can open `/profile` and understand coin balance, hospital level (or not-built state), and whether anyone is injured within one glance (under ~10 seconds of reading).
- **SC-002**: From `/profile`, a manager can reach hospital management and complete an upgrade or discharge path without first opening `/store`, in a single continuous interaction flow.
- **SC-003**: 100% of no-club and hospital-unavailable edge cases show a clear human message (no raw error text) in acceptance testing.
- **SC-004**: Existing `/profile` league/record/trophy information remains present after the redesign (no regression of those sections).
- **SC-005**: Managers who still use `/club-finances` continue to succeed and see an explicit pointer to `/profile` for the unified view.
- **SC-006**: After a hospital state change from a profile-opened panel, the refreshed profile dashboard matches the new hospital level/beds/patients and coin balance on the next view.

## Assumptions

- Hospital facility rules, bed counts, recovery multipliers, upgrade costs, and admit/discharge behavior already defined in `002-injury-fatigue-hospital` remain the source of truth; this feature is a **presentation and navigation hub**, not a rebalance of hospital math.
- Gems in the UI map to the existing club tokens balance; no new currency is introduced.
- “Recent income/expenses” on the finance summary is **nice-to-have**; v1 may show wallet only on the main embed and richer wage/facility detail behind **Finances**, without a ledger.
- **View Club Stats** defaults to the Squad hub (not `/development`); development remains reachable via its own command.
- `/profile` remains ephemeral (or matches current visibility); buttons follow existing hub timeout patterns.
- DM support: show the invoking user’s club when they have one (same as other personal club commands), unless a global bot policy already blocks DMs—in that case, clear refusal copy is enough.
- Soft-deprecation of `/club-finances` (keep + pointer) is preferred over hard removal in v1; hard removal can be a later cleanup task.
- No new slash commands, tables, or hospital RPCs are required for v1 of this hub beyond what hospital/economy already provide.

## Out of Scope (v1)

- Full economy transaction log / ledger browser.
- New `/hospital` or `/finances` slash commands.
- Redesigning Store faucet flows (daily login / energy refill).
- Changing hospital upgrade pricing, bed formulas, or recovery math.
- Admin-only discharge powers beyond what managers already have for their own club.
- Removing Store → Club Facilities hospital entry.

## UX Layout Mockup (manager-facing)

Text wireframe of the unified `/profile` embed + button row (illustrative copy):

```text
┌──────────────────────────────────────────────┐
│  Club Profile: {Club Name}                   │
│  Manager · @{user}                           │
├──────────────────────────────────────────────┤
│  💰 Club Finance                             │
│  Coins: 12,450     Gems: 3                   │
│  ▓▓▓▓▓▓▓▓░░  (optional balance emphasis)     │
├──────────────────────────────────────────────┤
│  🏥 Hospital                                 │
│  Level 2 · Beds 2/4 · Recovery ×1.25         │
│  • Alex Rivera — back Jul 14                 │
│  • Sam Ortiz — back Jul 16                   │
│  (or) No injuries                            │
│  (if L0) No Hospital – build one in Store!   │
├──────────────────────────────────────────────┤
│  ⚡ Energy · 🏆 Division / LP · Record …     │
│  (existing profile sections retained)        │
└──────────────────────────────────────────────┘
 [🏥 Manage Hospital] [💰 Finances] [📊 Club Stats]
```

**Navigation sketch:**

- **Manage Hospital** → hospital panel (upgrade / admit / discharge) → **Back to Profile** refreshes dashboard.
- **Finances** → finance detail (wallet + wages + facility levels) → **Back to Profile**.
- **View Club Stats** → Squad hub (existing).
- Store → Club Facilities → Hospital Panel remains available; Back there continues to return to Store/Facilities as today.
