# Feature Specification: Autonomous League Administration Policy

**Feature Branch**: `027-league-autonomous-admin`

**Created**: 2026-07-21

**Status**: Draft

**Input**: User description: "The league must be a fully autonomous internal system. Discord admins should not manually control its lifecycle." — Guild admins may configure only league timezone and daily match resolution hour (future seasons only). Remove `/admin → League Management` lifecycle controls; expose League Time under `/admin → Server Settings`. Internal League Lifecycle Engine is sole authority for registration through next-cycle opening. Player `/league hub` remains input-only. Emergency recovery is operator/internal only, never ordinary Discord admin commands.

**Amends / supersedes (Discord admin surface)**: Admin lifecycle controls described in `026-league-lifecycle-rulebook` (including pause/resume/force-end/manual start via Discord, dual league-mode selection, and broad `/admin → League Management`). Competitive calendar, matchday, standings, rewards, and promotion rules remain owned by `026` unless this document explicitly overrides a Discord-facing control.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Admins only set League Time (Priority: P1)

A guild administrator opens `/admin → Server Settings → League Time`, chooses a valid IANA timezone and a local daily resolution hour, and sees a clear preview of when matches will resolve (local wording plus current UTC equivalent). They understand the change applies from the **next** season, not the active one. They cannot start, stop, pause, advance, or settle the league from Discord.

**Why this priority**: Removing babysitting controls only works if the remaining admin surface is obvious, safe, and limited to schedule preference.

**Independent Test**: On a guild with an active season, change League Time; confirm active season deadlines are unchanged and the preview states next-season application. Confirm no Discord control exists for registration open/close, season start/end, pause, matchday advance, force-simulate, or rewards.

**Acceptance Scenarios**:

1. **Given** a guild administrator with permission to use `/admin`, **When** they open Server Settings → League Time, **Then** they can set only timezone (IANA) and daily local resolution time.
2. **Given** they enter a valid timezone and hour (e.g. `Asia/Kathmandu` and `20:00`), **When** they save, **Then** the UI shows a preview equivalent to: matches resolve daily at that local time in that zone, with the current UTC equivalent, and that the change applies from the next season.
3. **Given** an active season with a frozen timing snapshot, **When** League Time is changed, **Then** that season’s matchday deadlines and timezone snapshot do not change.
4. **Given** an invalid timezone string or a raw offset such as `UTC+5:45`, **When** they attempt to save, **Then** the setting is rejected with a clear validation message; only installed IANA timezone identifiers are accepted.
5. **Given** product inventory of Discord admin surfaces, **When** this feature ships, **Then** `/admin → League Management` no longer exposes lifecycle or competitive controls (it is removed or reduced so League Time lives only under Server Settings).

---

### User Story 2 - League runs without admin babysitting (Priority: P1)

Managers and admins experience a continuous autonomous cycle. No Discord interaction starts or advances lifecycle phases. Registration opens, closes, prepares, runs fourteen matchdays, settles, promotes/relegates, enters offseason, and opens the next registration under the internal engine alone.

**Why this priority**: The product promise is a living league; admin availability must not gate progression.

**Independent Test**: Run (or simulate) one full cycle on a guild with automation enabled and confirm zero Discord admin lifecycle actions are required for the happy path.

**Acceptance Scenarios**:

1. **Given** a guild eligible for a new cycle, **When** the next registration time is reached, **Then** registration opens without an admin “Open Registration” action.
2. **Given** registration, preparation, matchdays, settlement, promotion/relegation, and offseason deadlines, **When** each is due, **Then** the internal engine performs the transition; Discord buttons/commands cannot force those transitions.
3. **Given** a manager uses `/league hub`, **When** they register, withdraw, view info, fixtures, standings, lineup, opponents, results, stats, or final results, **Then** those actions provide allowed input or read-only views and do **not** control when lifecycle transitions occur.
4. **Given** any Discord interaction (admin or player), **When** it completes, **Then** it has not directly mutated lifecycle phase authority outside of permitted player inputs (e.g. registration during an already-open window).

---

### User Story 3 - Defaults work without blocking the league (Priority: P2)

A guild that never configured League Time still runs the league using defaults. Admins may be notified that defaults are active, but the league does not stall waiting for configuration.

**Why this priority**: Rigid “must configure before anything works” recreates Dynamics-style friction and blocks autonomous operation.

**Independent Test**: Create or use a guild with no League Time saved; confirm cycle proceeds with UTC and midnight local resolution; confirm optional admin notice does not block transitions.

**Acceptance Scenarios**:

1. **Given** a guild with no League Time configuration, **When** a season enters preparation, **Then** the frozen snapshot uses timezone `UTC` and daily resolution hour `00:00`.
2. **Given** defaults are in effect, **When** the engine operates, **Then** league progression is not blocked pending admin configuration.
3. **Given** defaults are in effect, **When** administrators are notified (if notification is enabled), **Then** the notice is informational only and does not require acknowledgment to continue the cycle.

---

### User Story 4 - Failures recover without Discord admin tools (Priority: P1)

When a transition fails, Discord is down, or a scheduler wake is missed, the league continues via automatic recovery and trusted operator-only mechanisms. Ordinary guild admins cannot “unstick” the league by editing standings, forcing simulate, or manually advancing phases in Discord.

**Why this priority**: Removing manual Discord controls makes internal recovery mandatory; without it, a single stuck transition leaves the guild helpless.

**Independent Test**: Simulate a failed transition and a missed wake-up; confirm automatic retry/catch-up. Confirm Discord admin inventory has no recovery/force/lifecycle buttons. Confirm an operator recovery path can retry via the same engine with audit + idempotency, without direct standings/reward edits.

**Acceptance Scenarios**:

1. **Given** a lifecycle operation fails transiently, **When** recovery runs, **Then** the same engine path retries with an idempotency key and an audit record.
2. **Given** one or more scheduler wakes were missed, **When** the next recovery/wake occurs, **Then** overdue transitions catch up in order without Discord admin intervention.
3. **Given** Discord announce delivery fails, **When** competitive settlement is due, **Then** sporting progression continues and announcement delivery retries separately.
4. **Given** an infrastructure failure (e.g. match simulation unavailable), **When** resolution is attempted, **Then** the operation remains retryable and does **not** invent a sporting forfeit.
5. **Given** a trusted operator uses an internal recovery mechanism, **When** they request a retry, **Then** recovery uses the same rule paths as normal automation, creates an audit record, requires an idempotency key, and never directly edits standings or rewards or converts a living season to another ruleset.
6. **Given** retry limits are exceeded, **When** the system detects a stuck operation, **Then** an alert is raised for operators; guild Discord admins still have no ordinary command to bypass the rulebook.

---

### Edge Cases

- Active season already running when League Time changes → only future seasons adopt the new timezone/hour; active frozen snapshot unchanged.
- Guild never configured League Time → defaults `UTC` + `00:00`; league still operates.
- Invalid IANA name or raw UTC offset entered → reject; do not store.
- DST transitions for the configured zone → schedule generation uses the timezone database (per `026` DST rules); offsets alone are insufficient and forbidden as the configured identity.
- Discord outage during a deadline → internal progression continues; announcements retry.
- Missed scheduler runs → automatic catch-up; no admin “advance matchday” button.
- Multiple workers wake simultaneously → exactly-once commit per operation via idempotency.
- Operator recovery attempted mid-flight → must reuse engine transitions; cannot rewrite standings, prizes, or ruleset version on a living season.
- Legacy grandfathered seasons (pre-cutover) → finish under their existing ruleset; this policy governs Discord surfaces after cutover and all new Lifecycle seasons.
- Player double-taps Register or views stale hub embeds → registration rules and phase gates still owned by the engine; UI cannot open registration early or keep it open after lock.

---

## Requirements *(mandatory)*

### Functional Requirements

#### Authority and surfaces

- **FR-001**: The internal League Lifecycle Engine MUST be the sole authority that opens/closes registration, validates registrants, charges deposits, creates divisions, adds AI clubs, generates fixtures and matchday windows, sends reminders, resolves expired fixtures, applies forfeits, advances matchdays, updates standings, completes seasons, distributes rewards, applies promotion/relegation, enters offseason, opens the next registration cycle, recovers interrupted operations, and retries failed Discord announcements.
- **FR-002**: No Discord interaction (slash command, button, modal, select menu, or context menu) MAY directly modify league lifecycle phase or competitive authority. Player actions MAY supply allowed inputs only while the engine has already opened the relevant window (e.g. register/withdraw during open registration; prepare lineup before a deadline).
- **FR-003**: The scheduler (or equivalent wake mechanism) MUST only wake the engine to evaluate due work; it MUST NOT contain competitive decision rules of its own.
- **FR-004**: Discord guild administrators MUST NOT be able to: open/close registration; start a season; end or cancel a season; pause or resume a season; start or advance a matchday; force-simulate fixtures; change season duration; change league size; change entry fees; change prize values; add/remove participants manually; kick managers from an active league; modify standings or scores; apply promotion/relegation; distribute or repeat rewards; run the lifecycle manually; or select legacy vs lifecycle league modes.

#### Admin configuration (League Time only)

- **FR-005**: The only league-related Discord admin configuration MUST be available at `/admin → Server Settings → League Time`.
- **FR-006**: League Time MUST expose exactly two fields: (1) timezone as a valid IANA identifier (e.g. `Asia/Kathmandu`), and (2) daily resolution time as local guild time (e.g. `20:00`).
- **FR-007**: League Time UI MUST show a preview that states the local resolution wording, the current UTC equivalent, and that the change applies from the next season.
- **FR-008**: Timezone validation MUST use the installed timezone database. Raw UTC offsets (e.g. `UTC+5:45`) MUST NOT be accepted as a substitute for IANA identifiers.
- **FR-009**: League Time changes MUST apply only to **future** seasons. When a season enters preparation, the engine MUST store an immutable snapshot of IANA timezone, local resolution hour, and calculated UTC matchday deadlines for that season.
- **FR-010**: Changing guild timezone or resolution hour MUST NOT alter an active season’s frozen timing snapshot or deadlines.
- **FR-011**: Existing `/admin → League Management` MUST be removed or reduced so it no longer offers lifecycle or competitive administration; League Time MUST not remain duplicated as a competing “management” control surface.

#### Defaults

- **FR-012**: When a guild has not configured League Time, defaults MUST be timezone `UTC` and daily resolution time `00:00`.
- **FR-013**: Default League Time MUST NOT block league operation. The system MAY notify guild administrators that defaults are active; such notices MUST be non-blocking.

#### Player surface

- **FR-014**: Players MUST continue using `/league hub` for permitted actions only: register/withdraw during registration; view season information, fixtures, standings, opponents, match results, player statistics, and final season results; and prepare their league lineup. These actions MUST NOT control lifecycle transition timing.

#### Internal recovery (non-Discord)

- **FR-015**: Emergency recovery MUST NOT be exposed as ordinary Discord admin commands, buttons, or menus.
- **FR-016**: Recovery MUST be available only through trusted internal mechanisms (deployment/maintenance scripts, restricted operator console, server-side maintenance endpoint, directly invoked recovery worker, and/or database-backed retry queue).
- **FR-017**: Every recovery action MUST use the same lifecycle engine, require an idempotency key, create an audit record, never edit standings or rewards directly, and never convert a living season to another ruleset.
- **FR-018**: The engine MUST provide automatic retries, stuck-operation detection, mutual exclusion so concurrent workers cannot double-commit the same operation, transition audit logs, and alerts when retry limits are exceeded.

#### Invariants (normative for this policy)

- **FR-019**: The system MUST uphold these invariants:
  1. The internal engine is the only lifecycle authority.
  2. Discord admins cannot manually start, stop, advance, or settle leagues.
  3. The scheduler only wakes the engine.
  4. Admin timezone/hour changes affect future seasons only.
  5. Every active season uses its frozen timing snapshot.
  6. Missed scheduler runs are recovered automatically.
  7. Discord outages do not stop internal league progression.
  8. Infrastructure failures do not cause sporting forfeits.
  9. Rewards and promotion operations execute exactly once.
  10. Internal recovery uses the same rule paths as normal automation.

### Key Entities

- **Guild League Time Settings**: Mutable guild preference for IANA timezone and local daily resolution hour; applies to seasons not yet snapshotted.
- **Season Timing Snapshot**: Immutable copy of timezone, local hour, and precomputed UTC matchday deadlines captured when a season enters preparation.
- **Lifecycle Engine**: Sole authority that evaluates durable league state and executes due transitions.
- **Scheduler Wake**: Non-authoritative trigger that asks the engine to evaluate due work.
- **Lifecycle Operation**: Idempotent unit of work with a key, audit trail, and retry/stuck semantics.
- **Operator Recovery Request**: Trusted non-Discord request to retry or re-wake an operation through the same engine.
- **Presentation Retry**: Outbound announcement delivery attempt that must not mutate competitive state.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a pilot guild with automation enabled, a full registration → 14 matchdays → settlement → offseason → next registration cycle completes with **zero** Discord admin lifecycle actions.
- **SC-002**: After delivery, Discord admin inventory shows **exactly one** league-related configuration surface (League Time) and **zero** controls for start/stop/pause/advance/settle/force-simulate/mode-select/manual participant or standings edits.
- **SC-003**: Changing League Time during an active season leaves **100%** of that season’s already-published matchday deadlines unchanged.
- **SC-004**: Guilds with no League Time configuration still complete a season cycle using UTC midnight defaults without requiring an admin save.
- **SC-005**: Invalid timezone input (unknown IANA name or raw offset form) is rejected **100%** of the time in acceptance tests.
- **SC-006**: After a simulated missed wake and a failed announcement, competitive state still reaches the correct terminal phase, and announcement delivery can succeed on retry without re-settling fixtures or re-paying rewards.
- **SC-007**: Re-running recovery **100 times** against an unchanged “now” does not duplicate rewards, promotion, or fixture settlement.
- **SC-008**: Managers can complete all permitted `/league hub` actions without any path that opens, closes, or advances a lifecycle phase from the player UI.

---

## Assumptions

- Competitive calendar lengths, division size, assistant-manager rules, standings, prizes, and promotion math remain defined by `026-league-lifecycle-rulebook`; this feature governs **who may control** lifecycle and **what Discord admins may configure**.
- Where `026` previously allowed Discord admin pause/resume/force-end/manual start, those Discord exposures are **removed** by this policy. If pause or cancel remains for extreme incidents, it is operator-only via trusted internal mechanisms and still must invoke the shared engine — never a parallel Discord path.
- Season duration, league size, entry fees, and prize values remain system/rulebook configuration — not Discord guild-admin tunables.
- Exclusive per-guild Lifecycle cutover from `026` remains; Discord must not offer a legacy-vs-lifecycle mode picker.
- “Server Settings” is the admin grouping under `/admin` that hosts League Time; other non-league server settings are out of scope except as navigation context.
- Default notice to admins about UTC/`00:00` is optional and non-blocking; exact copy may be refined in planning.
- Operator recovery tooling may live outside the Discord bot process; this spec requires the capability and invariants, not a particular product brand name for the console.

---

## Out of Scope

- Redesigning player `/league hub` beyond removing any accidental lifecycle-control affordances
- Changing match simulation algorithms or Weekly Division Rank
- Exposing a public “break glass” Discord admin recovery menu
- Allowing guild admins to edit economy prize tables or entry fees in Discord
- Converting living seasons between rulesets
- Building a full multi-tenant operator portal UI beyond the minimum trusted recovery mechanisms needed for retries and alerts
