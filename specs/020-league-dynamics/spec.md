# Feature Specification: League Dynamics Overhaul

**Feature Branch**: `020-league-dynamics`

**Created**: 2026-07-15

**Status**: Implemented (T001–T042; flag default off)

**Input**: User description: "Pre-integration assessment and design for League Dynamics: Daily Tick (24h hard close at 00:00 UTC), 14-day seasons, automatic division splitting with promotion/relegation, and Manager of the Matchday awards — validated against current guild league system and FM / Top Eleven / EA FC research, Ponytail-compliant (modify existing surfaces only)."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Daily Matchday Tick (Priority: P1)

A manager knows every league matchday is a calendar day that ends at midnight UTC. They can play any time before that deadline. If they forget, the club is auto-simulated shortly after midnight with the rest of the league’s unplayed fixtures in one shared “tick,” and the Journal / standings update as a league-wide moment.

**Why this priority**: Today’s rolling ~48-hour windows (derived from season length ÷ matchday count, starting at admin start time) leave early finishers waiting and never create a shared server ritual. Research from Top Eleven / FM-style ticks and async Discord play both favor a predictable daily cadence over long soft windows.

**Independent Test**: In an active season on the new rules, all current-matchday fixtures share a hard close at 00:00 UTC; unplayed fixtures resolve in the post-midnight tick; hub copy and reminders describe “before midnight UTC,” not a rolling 48h countdown from season start.

**Acceptance Scenarios**:

1. **Given** a season started under League Dynamics rules, **When** a matchday opens, **Then** its play window is at most one UTC calendar day and hard-closes at 00:00 UTC (not a soft rolling expiry aligned only to admin start time).
2. **Given** unplayed fixtures after the hard close, **When** the daily tick runs (~00:05 UTC), **Then** those fixtures are auto-simulated in one batch and the current matchday advances when all fixtures for that matchday are resolved.
3. **Given** a manager still within the open window, **When** they play manually, **Then** the match counts normally and is not later re-simulated by the tick.
4. **Given** the daily tick has already simulated a fixture, **When** a manager later opens the hub or tries to play that fixture, **Then** they see it as already played with no double resolution.

---

### User Story 2 - Two-Week Seasons (Priority: P1)

Admins and managers run compact seasons (~14 real days) so promotion fights, title races, and prize payouts arrive often enough that mid-table and early-losing clubs still feel momentum toward the next campaign.

**Why this priority**: Default 28-day seasons and the older 4–6 week design guideline make delayed season prizes the only big pay day; short seasons plus the daily tick tighten the loop without adding new commands.

**Independent Test**: New seasons default to 14 days; with the standard 8-club double round-robin (14 matchdays), each matchday maps cleanly to one daily tick. Registration / start messaging states the 14-day length.

**Acceptance Scenarios**:

1. **Given** an admin opens registration under League Dynamics defaults, **When** they accept defaults, **Then** season length is 14 days (overridable only if existing admin config still allows custom days — custom days must still produce coherent daily windows or be constrained).
2. **Given** an 8-club division under double round-robin, **When** the season runs, **Then** there are 14 matchdays over ~14 days with one hard close per matchday.
3. **Given** a season completes, **When** prizes distribute, **Then** existing top-3 pool and participation rewards still apply (award values remain tunable; pacing change alone does not invent a new slash command).

---

### User Story 3 - Guild Division Pyramid (Priority: P2)

When a guild has too many managers for one competitive table, the seasonal league automatically runs multiple division tiers (e.g. Division 1, Division 2). At season end, the bottom two of a higher division swap places with the top two of the division below for the next season, so strong clubs climb and struggling clubs get a fairer table.

**Why this priority**: A single flat table (current model, sizes up to 16) does not scale; repeat title loops without relegation feel static. Football Manager–style fixed up/down spots create long-term goals without changing the weekly Division Rank ladder (bot-match based).

**Independent Test**: With 9+ registered humans, start-of-season assignment places the first 8 into Division 1 (bot-filled to 8 if needed only when humans < 8 in a tier) and overflows into Division 2+; each tier table is exactly 8 clubs via bot fill; end-of-season stands produce exactly two promotions and two relegations between adjacent tiers (when both tiers exist and have enough clubs). Hub / standings identify the manager’s division.

**Acceptance Scenarios**:

1. **Given** 9 or more registered humans at season start, **When** the season starts, **Then** humans are assigned across division tiers with **at most 8 humans per tier**, each tier table completed to **exactly 8 clubs** with bot fill, using double round-robin (14 matchdays).
2. **Given** 8 or fewer registered humans, **When** the season starts, **Then** a single Division 1 table of exactly 8 clubs (bot fill as needed) is created — no Division 2.
3. **Given** Division 1 and Division 2 both completed a season, **When** prizes and transitions resolve, **Then** the bottom 2 of Division 1 are marked for relegation and the top 2 of Division 2 for promotion into the next season’s tier assignments.
4. **Given** only one division exists, **When** the season ends, **Then** no phantom promotion/relegation occurs.
5. **Given** a manager views standings or hub, **When** multi-division mode is active, **Then** they see their own division’s table first (not a confusing merged leaderboard of all tiers).

---

### User Story 4 - Manager of the Matchday (Priority: P2)

After each matchday tick settles, the manager with the most impressive win that matchday receives a small coin bonus and a short Journal shout-out, so clubs outside the title race still chase a daily micro-goal.

**Why this priority**: End-of-season prizes alone demotivate early losers; EA FC / FM-style mid-cycle awards fit Discord Journal cadence without new slash commands. Distinct from existing in-match **player** Man of the Match on cards.

**Independent Test**: After a fully resolved matchday with at least one human-managed **manual** win, exactly one Manager of the Matchday is chosen by the published rule, coins credit once (idempotent per season+matchday), and the Journal posts a clear award line. If every fixture that matchday was auto-simmed (or there are only draws / AI-only results), no MoMD is awarded.

**Acceptance Scenarios**:

1. **Given** all fixtures for matchday N are resolved (manual and/or tick), **When** post-matchday settlement runs, **Then** the system selects one Manager of the Matchday among eligible wins — or awards none if no eligible wins exist.
2. **Given** selection by largest winning margin (goal difference of the winning scoreline), with goals-for as tie-break, **When** a unique eligible winner exists, **Then** that club receives a **2,000-coin** bonus (tunable) via the normal club economy pipe.
3. **Given** the Journal for that season, **When** the award fires, **Then** a short public notice names the manager/club, scoreline, and bonus — without spamming MatchDay commentary threads with duplicate noise beyond one Journal announcement.
4. **Given** the award already paid for season S matchday N, **When** settlement retries, **Then** coins are not granted again.
5. **Given** a matchday where all human fixtures were auto-simmed, or only draws / AI-vs-AI results exist, **When** settlement runs, **Then** no Manager of the Matchday is awarded and no MoMD coins are granted.
6. **Given** a human club that won via auto-sim, **When** MoMD is selected, **Then** that club is **ineligible** — only wins from human-managed **manual** play qualify.

---

### User Story 5 - Safe Rollout for Living Seasons (Priority: P1)

Servers with an active 28-day / rolling-window season are not mid-season rewritten into 24h ticks and division pyramids. Admins can enable or verify the new pacing on the next registration/start cycle (or behind a clear feature flag), with a documented path to test without destroying ongoing competitions.

**Why this priority**: Changing `window_end` mid-flight would invalidate reminders, half-played matchdays, and player expectations.

**Independent Test**: With the flag off (or legacy season marker), existing active seasons keep current window math and 10-minute auto-sim polling behavior for those seasons; a newly started season under the flag uses daily tick rules.

**Acceptance Scenarios**:

1. **Given** an already-active legacy season, **When** League Dynamics ships, **Then** its fixtures continue under existing window semantics until that season completes or an admin ends it.
2. **Given** the feature is enabled for a guild (or globally) and no active legacy season blocks it, **When** admin starts a new season, **Then** daily-tick windows, 14-day default, and (if applicable) division assignment apply.
3. **Given** a test guild, **When** operators run a short season under the flag, **Then** they can validate tick, awards, and standings without mutating unrelated guilds’ active seasons.

---

### Edge Cases

- Matchday with mixed human-played and unplayed fixtures at 00:00 UTC — only unplayed sims; already-played results stand.
- Bot fill clubs and AI vs AI on a matchday — standings update; AI results never win MoMD; auto-sim human wins never win MoMD.
- Season paused mid-matchday — tick must not advance or auto-sim paused seasons.
- Equal largest margins among two humans — goals-for tie-break, then deterministic secondary tie-break (e.g. lower club id / earlier finish) so exactly one winner.
- Division with fewer than four clubs — promotion/relegation of “top/bottom 2” must not orphan empty tiers; skip or shrink swap set when N < 4.
- Registration between min humans and overflow — bot fill still allowed per existing admin config; multi-division assignment must not charge entry fees twice.
- Reminder DMs currently “6h before window_end” — under daily tick, reminders must still fire once per matchday without duplicate spam when window_end is midnight UTC.
- Naming collision: weekly **Division Rank** (`players.division`) vs seasonal **division tier** — product copy must not use identical labels in the hub without disambiguation.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST offer a League Dynamics mode where each matchday has a hard close at **00:00 UTC** and unplayed fixtures are auto-resolved in a scheduled **daily tick** shortly after (~00:05 UTC).
- **FR-002**: System MUST default new League Dynamics seasons to **14 days**, with pacing that produces one matchday close per UTC day for the standard 8-club double round-robin layout.
- **FR-003**: System MUST preserve the existing dual-thread UX (League Journal for standings/results/awards; MatchDay for match spectacle) and MUST NOT add new slash commands for these behaviors.
- **FR-004**: System MUST keep guild seasonal standings derived from seasonal fixtures, and MUST NOT write seasonal fixture results into the weekly Division Rank fields (`league_points` / weekly ladder) — the two ladders remain decoupled.
- **FR-005**: System MUST support automatic multi-tier seasonal divisions when humans exceed one table, persist each participant’s seasonal **division tier**, and at season end apply **top 2 promotion / bottom 2 relegation** between adjacent tiers for the next season.
- **FR-006**: Each division table MUST be **exactly 8 clubs** (double round-robin → 14 matchdays). When registered humans are **≤ 8**, run a single Division 1 with bot fill to 8. When humans are **> 8**, assign at most 8 humans per tier (overflow seeds Division 2, then 3, …) and bot-fill each incomplete tier to 8.
- **FR-007**: System MUST award **Manager of the Matchday** after each fully settled matchday when an eligible win exists: select the best eligible win, grant **2,000 coins** (config-tunable) once per season+matchday, and announce in the League Journal.
- **FR-008**: MoMD eligibility MUST be **human-managed manual wins only**. Auto-simmed results (even for human clubs), draws, and AI-vs-AI scorelines are ineligible. If no eligible win exists that matchday, the system MUST award nothing (no coins, no Journal MoMD line).
- **FR-009**: System MUST keep coin grants for MoMD and season prizes on the single club economy pipe with idempotent keys (no direct balance edits).
- **FR-010**: System MUST leave in-progress legacy seasons on current rolling-window / interval auto-sim behavior until they complete; new rules apply to newly started seasons when the feature is enabled.
- **FR-011**: System MUST update hub, reminder, and announcement copy so managers understand the midnight UTC deadline and (when relevant) their division tier.
- **FR-012**: System MUST remain operable via existing `/league hub` and admin season lifecycle surfaces only (no new player-facing slash commands).

### Key Entities

- **Guild Seasonal Season**: Timed competition for one Discord guild; length, status, current matchday, thread IDs; under League Dynamics, matchdays align to UTC day boundaries.
- **Matchday Window**: Play eligibility interval for a set of fixtures; Dynamics mode hard-closes at 00:00 UTC; legacy mode retains rolling `window_end`.
- **Daily Tick**: Post-midnight batch that auto-simulates expired unplayed fixtures and triggers matchday settlement (advance, standings posts, MoMD).
- **Seasonal Division Tier**: Ordinal tier (1 = top) on a participant for a season/guild pyramid; distinct from weekly Division Rank name on the club profile.
- **League Participant**: Club enrolled in a season; gains/retains division tier across seasons via promotion/relegation outcomes.
- **Manager of the Matchday Award**: Per season+matchday honor with coin payout and Journal notice; separate from player-card Man of the Match.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In Dynamics seasons, ≥95% of matchdays fully resolve (all fixtures played or auto-simmed) within 15 minutes after 00:00 UTC on tick days.
- **SC-002**: Managers can state the play deadline correctly from hub copy alone (“by 00:00 UTC”) in usability checks without reading a wiki.
- **SC-003**: Standard 8-club Dynamics seasons complete in **14±1** calendar days from start to prize distribution under normal tick operation.
- **SC-004**: When two adjacent divisions finish a season with ≥4 clubs each, exactly two clubs move up and two move down for the next season’s assignments (unless skipped by the empty-tier rule).
- **SC-005**: On matchdays with at least one eligible MoMD win, exactly one MoMD payout and one Journal announcement occur; zero duplicate coin grants on retries.
- **SC-006**: Enabling Dynamics does not change fixtures, standings, or window ends of seasons already `active` under legacy rules.
- **SC-007**: Player-facing friction stays low: no new slash commands; existing hubs/journals remain the only surfaces for play, standings, and awards.

## Assumptions

### Research validation (FM / Top Eleven / EA FC → Discord bot)

- **Daily tick**: Correctly interpreted — synchronized resolution beats long async soft windows for “league night” energy. For Discord, a **fixed UTC midnight** close is clearer than Top Eleven’s player-local prime-time, because guilds are multi-timezone and the bot already schedules in UTC.
- **24h vs 48h UX**: Shorter deadlines raise mild deadline pressure (healthy routine for daily Discord habits) and reduce “I already played, now I wait two days” dead time. Risk: managers who only play weekends may auto-sim more — mitigated by short seasons, MoMD on other days, and clear midnight messaging + existing ~6h reminders retargeted to midnight.
- **14-day seasons**: Aligns with keeping engagement loops short; slightly more aggressive than the older 4–6 week design doc, but compatible with 8-club double RR (14 matchdays). Acceptable deliberate pacing change.
- **Division pyramid**: FM-style fixed top/bottom 2 is fairer and easier to explain than the weekly ladder’s percentage cut. Assumed **seasonal-only**; weekly Division Rank remains a separate bot-match ladder (existing product rule).
- **Manager of the Matchday**: Mid-cycle coin + Journal shout-out is appropriate density for Discord (one embed/line per day per guild season). Avoid MatchDay spam and avoid conflating with player MOTM. 2,000 coins assumed as a small faucet relative to season prizes — must stay tunable so economy calibration can nerf if inflation appears.
- **Ponytail surface area**: Changes piggyback `/league hub`, admin season start/end, Journal posts, and scheduler jobs — no new player slash commands; minimize new abstractions.

### Resolved product decisions

- Legacy seasons are grandfathered; Dynamics applies at next season start when enabled.
- **Division size**: Target/exact **8 clubs per division** (bot fill); double RR only — no single/double RR mix.
- **Split threshold**: Open the next tier when **humans > 8** (9th human seeds Division 2).
- **MoMD eligibility**: Human-managed **manual** wins only; all-auto-sim matchdays yield no award (incentivizes daily login).
- MoMD primary metric = winning goal margin; tie-break = goals scored by the winner; then deterministic club order.
- Seasonal division labels in UI use wording like “Division 1 / 2” and must not overwrite weekly rank names without a qualifier (“Weekly Rank”).
- Bot fill remains required so every tier is a valid 8-club table.

### Out of scope (v1 of this feature)

- Merging weekly Division Rank with seasonal tiers into one ladder.
- Winners Cup / cross-guild competitions.
- Changing per-match league XP/coin formulas beyond MoMD’s explicit bonus.
- New slash commands or a separate “awards” hub.
- Mandatory simultaneous live attendance.

## Dependencies

- Existing guild league lifecycle (registration → start → fixtures → Journal/MatchDay threads → prizes).
- Existing auto-sim and matchday reminder behaviors (retargeted, not replaced with a parallel player UI).
- Single coin economy pipe and season prize distribution flow.
- APScheduler UTC jobs already used for other midnight/Monday tasks.

## Rollout Strategy *(product)*

1. **Ship behind a feature flag** (global and/or per-guild) defaulting to off.
2. **Grandfather** all `active` / `paused` seasons as legacy window mode until completed.
3. **Pilot** on one internal/test guild: 8-club, 14-day, observe tick reliability, reminder quality, MoMD noise, and auto-sim rate.
4. **Enable** for production guilds at next registration window; publish one Journal/changelog note explaining midnight UTC + shorter seasons + divisions/MoMD when those subfeatures are on.
5. **Economy watch**: MoMD 2,000 × matchdays × guilds — confirm against season prize pool so the daily award stays a spice, not a primary income.
