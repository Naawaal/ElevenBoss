# Feature Specification: League Rulebook and Autonomous Lifecycle Engine V1

**Feature Branch**: `026-league-lifecycle-rulebook`

**Created**: 2026-07-21

**Status**: Draft (clarifications resolved — ready for `/speckit.plan`)

**Input**: User description: Research-backed ElevenBoss league identity (Hattrick 8-club / 14-matchday, Top Eleven compact cadence, OSM fixed deadlines, FM Live assistant-manager absences, Soccer Manager offseason, Goalunited promo presentation) → freeze a complete autonomous league rulebook before any engine/scheduler implementation. Order of work: research → identity → rulebook → lifecycle state machines → persistence/recovery → automation engine → Discord UI + match simulation. Automation must execute the rulebook; it must never invent competitive decisions.

**Supersedes (for new seasons after approval)**: Competitive pacing and lifecycle rules in `020-league-dynamics` and `021-league-automation-and-config`, and the seasonal half of `.specify/specs/v1.0.0/league-mode-design.md`. Weekly Division Rank (bot-match ladder) remains a separate system and is out of scope.

---

## Product Identity

ElevenBoss Guild Seasonal League is:

> A persistent, autonomous guild football pyramid where managers prepare their clubs asynchronously, fixtures resolve at fixed daily deadlines, and the league continuously handles registration, scheduling, matches, standings, rewards, promotion, relegation, and the next season.

It is **not** a live-attendance competition. Managers never need to coordinate availability with an opponent. Every fixture has a deadline; absence is handled by the assistant manager, not by punishing the present club with a forfeit (unless no legal team can be fielded).

### Design influences (adopted)

| Requirement | Inspiration |
|-------------|-------------|
| Eight-club divisions | Hattrick |
| Fourteen-matchday double round-robin | Hattrick |
| Compact season cadence | Top Eleven |
| Fixed daily resolution deadline | Online Soccer Manager |
| Assistant manager for absent users | Football Manager Live |
| Explicit preparation / offseason between seasons | Soccer Manager |
| Bot population management | Hattrick, Goalunited |
| Promotion presentation and bonuses | Hattrick, Goalunited |

### Explicitly rejected for V1

- 14-club Top Eleven tables (too large for typical Discord servers)
- Promoting a majority of a division (weak promotion drama)
- Hattrick-length ~16-week seasons
- Qualification / promotion playoffs
- Deep multi-continent division trees
- Mandatory live match attendance
- Flexible multi-day rolling windows as the primary pacing model (legacy grandfather only)

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Predictable autonomous season cycle (Priority: P1)

A manager in a guild with league automation enabled experiences a repeating **21-day cycle** without needing an admin to babysit: registration opens, they join, preparation seats the table and publishes fixtures, fourteen daily matchdays resolve whether or not they click Play, settlement awards prizes and moves clubs, then a short offseason leads into the next registration.

**Why this priority**: The product promise is a living league. Without a frozen calendar and autonomous transitions, Discord leagues stall on admin availability.

**Independent Test**: Run (or simulate) one full cycle on a pilot guild; verify each phase duration and that no admin Start is required for the happy path.

**Acceptance Scenarios**:

1. **Given** a guild eligible for a new cycle and no open season, **When** the next registration time is reached, **Then** registration opens for **48 hours** and managers can join via the existing `/league` hub.
2. **Given** registration closes with at least the minimum eligible humans, **When** preparation runs, **Then** deposits are charged, divisions of exactly **8 clubs** are formed (bots fill empty seats), and a double round-robin of **14 matchdays** is published before the first matchday opens.
3. **Given** an active season, **When** each calendar matchday’s resolution deadline is reached, **Then** every unfinished fixture for that matchday reaches a terminal result the same day — managers do not need to be online.
4. **Given** all 14 matchdays are terminal, **When** settlement runs (**24 hours** phase), **Then** final standings freeze, prizes pay once, promotion/relegation apply once, and trophy history records the season.
5. **Given** settlement completes, **When** offseason begins (**72 hours**), **Then** managers have a preparation window before the next registration opens; the system does not jump straight into matchday 1 of the next season.
6. **Given** registration closes with fewer than the minimum humans, **When** evaluation runs, **Then** the attempt is **cancelled** (not marked completed), deposits are refunded if charged, and the next registration is scheduled — not endlessly retried the same day.

---

### User Story 2 - Asynchronous matchday with assistant manager (Priority: P1)

A manager prepares a league lineup (or relies on a saved league XI). They may present the match early for immersion, but competitive fairness does not reward who clicks first. If they miss the deadline, the assistant manager fields a legal team from their saved plan and the match still resolves. Only a club that cannot field any legal XI forfeits.

**Why this priority**: Discord managers are casual and multi-timezone. Forfeiting for absence would destroy retention; FM Live–style assistant control is the core async contract.

**Independent Test**: Leave a fixture unplayed until after the deadline with a valid saved XI → automatic simulation with that plan; remove all legal players from a club → forfeit path only.

**Acceptance Scenarios**:

1. **Given** a fixture is open before the deadline, **When** a manager has a valid submitted matchday lineup or valid saved league lineup, **Then** that plan is used for resolution (manual early presentation or automatic).
2. **Given** the deadline is reached and a manager’s lineup is incomplete or has injured/suspended players, **When** the assistant manager runs, **Then** it repairs using eligible replacements and the club’s preferred formation/tactics — it does not invent a random tactical identity.
3. **Given** one club cannot field a legal team after assistant repair and the opponent can, **When** the fixture settles, **Then** the illegal club receives a **3–0 forfeit loss**.
4. **Given** both clubs cannot field legal teams, **When** the fixture settles, **Then** both receive a 0–0 double forfeit (MP +1, L +1, 0 points, result type `double_forfeit`) that does not count as a draw, clean sheet, unbeaten, appearance, or promotion-eligibility match.
5. **Given** Discord is unavailable at deadline, **When** resolution runs, **Then** the sporting result still settles internally; presentation may retry later without changing the result.
6. **Given** the match simulator is temporarily unavailable, **When** resolution is attempted, **Then** the fixture stays retryable — infrastructure failure MUST NOT produce a sporting forfeit.

---

### User Story 3 - Fair eight-club pyramid with human-first promotion (Priority: P1)

When more than eight humans register, the guild runs multiple eight-club divisions. At season end, positions 1–2 promote (position 1 is also champion), 7–8 relegate, and bots never consume human promotion slots or prize identity. Standings and announcements clearly mark bot clubs and celebrate promotion/relegation.

**Why this priority**: Hattrick’s 8/14 format is the right Discord table size; Goalunited-style presentation makes movement feel earned.

**Independent Test**: Start with 6, then 9, then 16 humans; verify seating, bot fill, and end-of-season movement sets never overlap and never promote bots into human slots.

**Acceptance Scenarios**:

1. **Given** eight or fewer eligible humans at preparation, **When** the season forms, **Then** there is a single top division of exactly eight clubs (bot-filled as needed).
2. **Given** more than eight eligible humans, **When** the season forms, **Then** humans are seated across divisions with **at most eight humans per division**, each division completed to eight clubs with bots, using deterministic seating rules (prior division level, then stable tie-breaks — not uncontrolled randomness).
3. **Given** an eight-club division completes, **When** settlement applies movement, **Then** positions **1** (champion + promoted) and **2** promote; **7–8** relegate; **3–6** remain — with no promotion above the top division and no relegation below the bottom.
4. **Given** bots occupy table positions that would otherwise claim promotion, **When** promotion slots are assigned, **Then** eligible humans fill those slots; bots move down or are replaced rather than blocking humans.
5. **Given** too few active humans for full two-up/two-down without collapsing the pyramid, **When** settlement runs, **Then** the system reduces movement rather than promoting and relegating nearly everyone.
6. **Given** settlement completes, **When** managers view standings/history, **Then** promoted, relegated, and bot clubs are visually distinct and promotion includes reward/presentation — not a silent database change only.

---

### User Story 4 - Rulebook-driven automation, not job-scattered rules (Priority: P1)

Server owners and managers experience one coherent league that advances when deadlines are due. Admins who pause, resume, force-end, or manually trigger a transition use the **same** lifecycle rules as automation. Re-running the lifecycle after downtime never double-pays prizes, double-settles fixtures, or invents different competitive outcomes.

**Why this priority**: Scattered schedulers with embedded business rules are how leagues become unpredictable. The rulebook must be the only source of competitive truth.

**Independent Test**: Pause mid-matchday; resume after two days and confirm unresolved windows shift forward by the pause duration; kill the bot for six hours past a deadline and confirm catch-up settles each overdue transition once; admin “Start Season” produces the same preparation rules as automatic start.

**Acceptance Scenarios**:

1. **Given** any due lifecycle deadline (registration close, matchday lock, season settle, next registration), **When** the lifecycle runs, **Then** it applies the frozen rulebook transitions — the wake-up schedule does not contain competitive rules of its own.
2. **Given** the bot was offline across one or more deadlines, **When** it recovers, **Then** it processes overdue transitions in order and reaches the same terminal state as if it had been online (catch-up).
3. **Given** prizes, promotions, fixture settlements, or registration closes already committed, **When** the lifecycle runs again, **Then** those operations do not apply a second time.
4. **Given** an operator recovery or scheduler wake requests a transition, **When** the action is accepted, **Then** it uses the same engine transitions automation would use — not a parallel one-off path. *(Discord admin Start/Close/Settle removed by `027-league-autonomous-admin`.)*
5. **Given** a season is paused via operator/infrastructure path, **When** time passes, **Then** unresolved deadlines do not expire during the pause; on resume, unresolved windows are rebased forward by the paused duration.
6. **Given** an operator force-ends a season before natural completion, **When** cancellation settlement runs, **Then** the season is marked cancelled (not naturally completed); full prizes and promotion are disabled unless a published completion threshold was already met.

---

### User Story 5 - Managers prepare via existing league surfaces (Priority: P2)

Managers continue to use `/league` for registration, standings, fixtures, scout, and early match presentation. They configure league preparation (saved lineup / tactics) before deadlines. They do not receive new player slash commands for lifecycle. Announcements and journal presentation show deadlines in each user’s local time (Discord timestamps) based on the season’s frozen resolution schedule.

**Why this priority**: Ponytail — extend the existing hub; do not invent a second command surface.

**Independent Test**: Inventory player commands after delivery — still `/league` (+ existing `/leaderboard` season tab); hub shows next deadline as a localized timestamp; saved lineup is used when the manager is absent.

**Acceptance Scenarios**:

1. **Given** registration is open, **When** a manager uses `/league` Register, **Then** they appear on the seasonal registration roster if eligible.
2. **Given** an open matchday, **When** a manager views fixtures, **Then** they see the resolution deadline as a localized Discord timestamp derived from the season’s frozen schedule.
3. **Given** product surfaces are inventoried, **When** this feature ships, **Then** no new player-facing slash command exists solely for lifecycle control.
4. **Given** a manager updates their saved league lineup before the deadline, **When** automatic resolution runs, **Then** that lineup (after assistant repair if needed) is the plan used.

---

### Edge Cases

- Bot offline at deadline → fixture remains due; on restart, resolve using original deadline and the season’s immutable ruleset snapshot.
- Invalid or empty manager lineup → assistant repairs; forfeit only if no legal team can be built.
- Season paused for N days → unresolved windows move forward by N days; they do not instantly expire on resume.
- Manager leaves Discord mid-season → club remains assistant-controlled until season end; inactivity handled in offseason (replace or mark inactive) without breaking the table mid-season.
- Extra humans register after preparation → they wait for the next cycle; never restructure an active division.
- Discord thread or announce channel deleted → competitive state continues; presentation recreates or redirects without blocking progression.
- Multiple workers wake the lifecycle → only one successful commit per operation (idempotent keys / lease); no double settlement.
- Match presentation started early by one manager → sporting rules identical to deadline resolution; early click is cosmetic/immersive, not a competitive advantage.
- Incomplete XI / hospital / suspensions → assistant replacement priority; still forfeit if zero legal players.
- Weekly Division Rank ladder → unchanged; seasonal fixtures MUST NOT write weekly ladder points.

---

## Requirements *(mandatory)*

### Functional Requirements

#### League identity and calendar

- **FR-001**: System MUST run Guild Seasonal League as a **21-day autonomous cycle** with phases: Registration **48h** → Preparation **24h** → Regular season **14 days** (one matchday per day) → Settlement **24h** → Offseason **72h**, then next registration.
- **FR-002**: Each competitive division MUST contain exactly **8 clubs**, **14 matchdays**, **4 fixtures per matchday**, and a double round-robin yielding **7 home and 7 away** matches per club.
- **FR-003**: System MUST support multiple divisions in a guild pyramid when more than eight humans register, without placing more than eight humans in one division.
- **FR-004**: Minimum humans required to proceed from locked registration into preparation MUST be configurable; V1 default is **four** eligible humans until simulations justify a change.
- **FR-005**: Every season MUST store an **immutable ruleset snapshot** at creation/activation so mid-season rule changes cannot rewrite living competitions.
- **FR-006**: Resolution schedule for a season MUST be guild-configurable (**IANA timezone** + **local daily resolution hour**), chosen before the season becomes active and **frozen for that season**. At preparation the system MUST store the IANA timezone and local hour, precompute every matchday’s `window_start` / `window_end` as UTC timestamps, and never recalculate an active season’s deadlines when guild settings later change. DST MUST be handled via the timezone database when generating the schedule; ambiguous or nonexistent local times MUST resolve with one documented deterministic rule (see Assumptions).
- **FR-007**: Weekly Division Rank (bot-match ladder) MUST remain decoupled; seasonal league matches MUST NOT award weekly ladder points or goal difference used by that ladder.

#### Lifecycle states

- **FR-008**: A league season MUST use distinct statuses that separate success from failure: at minimum `dormant`, `registration_open`, `registration_locked`, `preparing`, `active`, `paused`, `settling`, `completed`, `cancelled`, `failed`. Failed or cancelled registration MUST NOT be labeled `completed`.
- **FR-009**: Only one non-terminal open season (registration / preparing / active / paused / settling) MAY exist per guild league at a time.
- **FR-010**: Matchdays MUST progress through scheduled → open → (optional closing-soon reminder) → locked → resolving → completed, with a retryable failed-resolution state that does not invent forfeits.
- **FR-011**: Every fixture MUST eventually reach a terminal sporting state among: `settled`, `forfeit`, `void`. Non-terminal states (`scheduled`, `available`, `running`, `settling`, `failed_retryable`) MUST NOT be left permanently unresolved because a manager was inactive.
- **FR-012**: Admin pause/resume, force-end, and manual lifecycle triggers via Discord are **removed** (amended by `027-league-autonomous-admin`). Lifecycle transitions are engine/scheduler/operator-only and MUST use the same transitions as automation.

#### Registration and preparation

- **FR-013**: Registration MUST enforce eligibility rules (account age / match experience thresholds as configured), prevent duplicates, support withdrawal while open, and honor bans.
- **FR-014**: On successful preparation start, system MUST charge the configured entry deposit once per eligible human, seat divisions deterministically, fill remaining seats with bots, generate the double round-robin, assign matchday windows from the frozen schedule, and publish fixtures before matchday 1 opens.
- **FR-015**: If minimum humans are not met at registration lock, system MUST cancel the attempt, refund any charged deposits, and schedule the next registration — not mark the attempt as a completed season.
- **FR-016**: Preparation failure that is infrastructure-related MUST be retryable (`failed` / re-enter preparing) without cancelling eligible humans unfairly; sporting cancellation is reserved for under-min or explicit admin cancel.

#### Match resolution and assistant manager

- **FR-017**: Before deadline, managers MUST be able to prepare: saved league formation, starting XI, bench, tactics, and related match plan fields already supported by the product (captain / set pieces / approach as available). A submitted matchday plan overrides the saved league plan for that fixture.
- **FR-018**: At lock time, lineup selection priority MUST be: (1) valid submitted matchday lineup, (2) valid saved league lineup, (3) assistant-repaired lineup, (4) emergency legal lineup, (5) forfeit if no legal team exists.
- **FR-019**: Assistant manager MAY replace injured/suspended players, fill empty slots, use preferred formation, and pick best eligible bench replacements while preserving the manager’s tactical identity whenever possible. It MUST NOT randomly rewrite tactics.
- **FR-020**: One-sided illegal team → **3–0 forfeit** against the illegal club. Both illegal → **0–0 double forfeit with zero points for both clubs**. Standings MUST apply: MP +1, L +1 for both, GF +0, GA +0, GD unchanged, Points +0, result type `double_forfeit`. A double forfeit MUST NOT count as a draw, clean sheet, unbeaten result, player appearance, or valid completed match for promotion eligibility.
- **FR-021**: Early manual match presentation MUST NOT change sporting rules relative to deadline resolution (no first-click advantage to standings).
- **FR-022**: Match simulation randomness MUST be reproducible from a stored seed derived from season identity, fixture identity, and match-engine version; recovery MUST resume or reproduce the same match, not generate a conflicting result.
- **FR-023**: Discord outages MUST NOT block fixture settlement. Match-engine outages MUST leave fixtures retryable rather than forfeited.

#### Standings, prizes, promotion

- **FR-024**: Standings MUST rank by points (W=3, D=1, L=0), then goal difference, then goals scored, then head-to-head, then a published final stable tie-break. Form is display-only unless already published as a tie-break (V1: form is display-only).
- **FR-025**: Final standings after settlement MUST be immutable for that season.
- **FR-026**: End-of-season prizes MUST pay once per ruleset (champion / podium / participation as configured), and entry deposits MUST refund or convert per published economy rules without double payment.
- **FR-027**: Promotion/relegation for an eight-club division MUST be: positions **1** champion+promoted, **2** promoted, **3–6** remain, **7–8** relegated, with boundary clamps at top/bottom divisions.
- **FR-028**: Bots MUST NOT receive human promotion rewards, MUST NOT consume promotion slots intended for humans, MUST NOT receive economy rewards, and MUST be clearly marked in standings.
- **FR-029**: A club SHOULD complete a minimum number of eligible fixtures to receive promotion; when counts are too low, reduce movement rather than force full two-up/two-down.
- **FR-030**: Promotion and relegation sets for a division MUST never overlap. V1 MUST NOT include promotion playoffs.

#### Bots

- **FR-031**: Bots exist only to keep schedules complete. They fill seats after humans are seated, use division-appropriate strength snapshotted at season start (not recalculated every match), always maintain a valid automatic lineup, move down or get replaced when more humans join next cycle, and never prevent a human from joining the next season.
- **FR-032**: Bot strength target MUST be based on a division human median rating times a configured modifier, snapshotted for the season.

#### Autonomy, recovery, notifications

- **FR-033**: A single authoritative lifecycle process MUST evaluate durable league state and execute every transition that is due. Wake-up frequency is an implementation concern; competitive rules MUST live in the rulebook/lifecycle — not as separate one-off “registration close job”, “prize job”, etc. with divergent logic.
- **FR-034**: Every major competitive operation MUST be exactly-once under retry (registration close, prepare, activate, fixture resolve/settle, matchday complete, season settle, promotion, rewards, next registration).
- **FR-035**: Every automatic competitive decision MUST be auditable after the fact (why season started, why someone was excluded, why a forfeit happened, why a club was promoted, whether rewards already ran, which ruleset version applied).
- **FR-036**: Notification / journal presentation MUST announce registration, fixtures, matchday open, deadline reminders, results, standings, promotion, relegation, and champions — and MUST NEVER be the source of competitive state.
- **FR-037**: Recovery MUST cover stuck preparation, stuck match runs, expired locks, partial settlement, missed wake-ups, bot restart, and Discord publication retries.
- **FR-038**: Living seasons under prior rulebooks (020/021 legacy or Dynamics) MUST be grandfathered until natural/admin completion. Rollout MUST be a **feature-flagged exclusive cutover per guild**: after a guild migrates, every future season for that guild uses Lifecycle Rulebook V1 exclusively. The product MUST NOT permanently support two selectable league modes. After successful rollout, 021 automation becomes only a thin scheduler/wake-up over the unified lifecycle. Every season MUST store `ruleset_version` and `engine_version`. Rollback MUST disable new-season creation for V1 — never convert an active V1 season back to Dynamics.

#### Player and admin surfaces

- **FR-039**: System MUST NOT add new player-facing slash commands for lifecycle. `/league` remains the manager surface. Discord `/admin` league configuration is **League Time only** under Server Settings (amended by `027-league-autonomous-admin`); pause/resume/force-end are not Discord-exposed.
- **FR-040**: When automation owns the happy path, Discord MUST NOT offer Open Registration / Start Season forks. Operator recovery (if any) MUST request the shared engine transitions.

### Key Entities

- **Guild League**: Persistent competition container for one Discord guild.
- **League Membership**: Long-lived manager membership (current division level, auto-register preference, inactivity counters) separate from a single season’s registration.
- **Season Registration**: Per-season signup record (eligibility snapshot, deposit status, withdrawal/ban state).
- **Season**: One cycle instance with immutable ruleset snapshot, frozen resolution schedule, and lifecycle status.
- **Division**: Exactly eight clubs for one season tier within a guild pyramid.
- **Participant**: Human or bot club seated in a division for a season.
- **Matchday**: One of fourteen daily rounds with its own window and resolution state.
- **Fixture**: One home/away pairing with lineup plans, resolution path, terminal result, and reproducibility metadata (seed / ruleset / snapshots).
- **Match Plan**: Submitted or saved lineup + tactics used by assistant manager priority rules.
- **Final Standing**: Immutable end-of-season table row (position, points, movement, participant type).
- **Transition Record**: Audit entry for an automatic or admin-triggered lifecycle decision.
- **Lifecycle Operation**: Idempotent unit of work keyed so retries are safe.
- **Presentation Event**: Outbound announce/journal message that must not mutate competitive state.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a pilot guild with automation enabled, managers can complete a full registration → season → settlement → offseason → next registration cycle **without any admin Start action**.
- **SC-002**: **100%** of fixtures in a completed season reach a terminal sporting state (`settled`, `forfeit`, or `void`) without requiring both managers to be online at the same time.
- **SC-003**: Re-running lifecycle processing **100 times** against an unchanged “now” timestamp does not create duplicate seasons, duplicate fixture results, duplicate prize payments, or duplicate promotion applications.
- **SC-004**: After a simulated **≥6 hour** outage past a matchday deadline, the next recovery pass settles all overdue fixtures and advances the matchday without changing already-settled results.
- **SC-005**: In divisions with mixed humans and bots, **zero** bot clubs occupy a human promotion reward slot when an eligible human exists for that slot.
- **SC-006**: Managers can identify their next fixture deadline in their own local time from the hub/announce surfaces without converting UTC manually.
- **SC-007**: A paused season resumed after **≥48 hours** does not instantly expire previously open fixtures; remaining play time matches the rebased windows.
- **SC-008**: Product inventory after delivery shows **no new player slash commands** added solely for this lifecycle rulebook.

---

## Assumptions

- V1 default minimum humans to start preparation is **4**, remaining configurable for balance sims.
- Double round-robin for eight clubs is always **14 matchdays / 14 calendar days** of regular season inside the 21-day cycle.
- Form strings remain display-only; published competitive tie-breaks are points → GD → GF → H2H → stable identifier.
- Early match presentation is allowed for immersion but uses the same sporting settlement rules as deadline resolution.
- Existing `/league` hub and `/admin` league management are extended; no parallel player command family.
- Economy prize pool percentages and deposit amounts remain tunable configuration; this rulebook freezes **when** they apply and **once-only** payment, not every coin number.
- Weekly Division Rank and Global LP systems are unchanged and out of scope except for the decoupling invariant.
- Prior 020/021 seasons are grandfathered; this spec does not rewrite mid-flight tables.
- **Q1 resolved**: Guild-configurable IANA timezone + daily resolution hour in V1; freeze per season; precompute all matchday UTC windows at preparation; guild setting changes never rewrite active deadlines.
- **DST ambiguous/nonexistent local times**: When the chosen local resolution time falls in a DST gap (spring forward), use the first valid local time after the gap. When it falls in an overlap (fall back), use the **earlier** (DST) offset occurrence. Document this rule in the season ruleset snapshot.
- **Q2 resolved**: Double forfeit = 0–0, zero points, MP+1/L+1 both sides; not a draw/clean sheet/unbeaten/appearance/promo-eligibility match.
- **Q3 resolved**: Feature-flagged exclusive per-guild cutover; one final rule path; 021 becomes thin wake-up; rollback = stop creating new V1 seasons, never rewrite active V1 → Dynamics.

---

## Out of Scope (V1)

- Promotion/relegation playoffs or qualification rounds
- Mid-season division restructuring when new humans arrive
- Live mandatory co-attendance matches
- Deep continent-scale division trees
- Separate fragile schedulers per lifecycle event with divergent business rules
- Replacing the football match simulator itself (orchestration only)
- Changing Weekly Division Rank Monday reset rules
- New player slash commands

---

## Rulebook Invariants (normative)

1. Only one open season may exist per guild league.
2. Every season stores an immutable ruleset snapshot.
3. Every fixture reaches a terminal state.
4. A fixture result may be settled only once.
5. Both participating clubs are locked during settlement.
6. Discord failures cannot block league progression.
7. Rewards may be paid only once.
8. Promotion and relegation may be applied only once.
9. Bots never block human progression.
10. Pausing a season pauses its deadlines.
11. Resuming a season recalculates unresolved windows.
12. Failed infrastructure never causes a sporting forfeit.
13. Match randomness is reproducible.
14. Final standings are immutable.
15. Recovery can resume every lifecycle phase.
16. Operator / automation recovery actions use the same engine transitions as normal wakes (Discord admins do not trigger lifecycle — see `027`).

---

## Recommended Development Sequence (after approval)

This specification freezes the rulebook. Implementation MUST follow:

1. Approve and resolve remaining clarifications in this document  
2. Technical plan for persistence + recovery models  
3. Lifecycle state machines against the frozen statuses  
4. Autonomous lifecycle engine that only executes this rulebook  
5. Discord UI + match simulation wiring  

Do **not** invent competitive rules inside the scheduler while coding.
