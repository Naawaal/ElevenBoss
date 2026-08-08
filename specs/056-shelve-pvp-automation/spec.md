# Feature Specification: Shelve PvP and Fix Surviving Automations

**Feature Branch**: `056-shelve-pvp-automation`

**Created**: 2026-08-08

**Status**: Draft

**Input**: User description: "Completely remove all PvP-related changes (matchmaking, rivalry, queue, /battle bot replacement). Keep and fix only two lightweight automations from that work: changelog sender (post only on new version header) and Top.gg vote reminder DM. Selective restore to pre-PvP baseline while preserving Youth Academy and automation migration 107."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Shelve PvP and Restore Classic Battle (Priority: P1)

As a manager, I want `/battle` to offer only the classic Bot Battle and Friendly modes again, with no ranked queue, rivalry, Find Opponent, Practice-as-PvP fallback, or ghost-manager opponents, so that the game behaves exactly as it did before the shelved PvP initiative.

**Why this priority**: PvP is being shelved entirely. Leaving partial matchmaking or feature flags live would confuse managers and risk broken match flows. Restoring the pre-PvP battle experience is the primary deliverable of this cleanup.

**Independent Test**: After cleanup, open `/battle`, confirm only Bot Battle and Friendly are available, run a Bot Battle and verify it matches pre-PvP AI/bot behavior, and confirm searches for PvP/rivalry/queue surfaces find no active product code or docs.

**Acceptance Scenarios**:

1. **Given** a registered manager, **When** they open `/battle`, **Then** they see Bot Battle and Friendly only — no Find Opponent, Ranked PvP, Practice, queue, rivalry, or ghost-manager options.
2. **Given** a manager starts Bot Battle, **When** the match completes, **Then** the flow matches the pre-PvP bot-battle behavior (original AI/bot match), not ranked/Practice fallback logic.
3. **Given** the product codebase and active schema requirements after cleanup, **When** operators search for PvP matchmaking, rivalries, ghost managers, and PvP feature flags, **Then** no active product paths, config flags, or schema-guard requirements remain (historical Git history may still mention them).
4. **Given** Youth Academy V2 work that landed in the same era as early PvP commits, **When** PvP is removed, **Then** Academy behavior and its migrations remain intact and unchanged by this cleanup.

---

### User Story 2 - Changelog Posts Only on New Version (Priority: P2)

As a server manager/admin watching the announcement channel, I want a changelog embed posted only when a new version section appears in the player-facing changelog, so that routine bot restarts and redeploys of the same version stay silent.

**Why this priority**: The current behavior announces on every restart/commit, creating announcement spam and eroding trust in release notes. Version-only posting is the required correction for the automation we keep.

**Independent Test**: Restart the bot with the same latest changelog version (same or different deploy identity) and confirm silence; add a new `## [X.Y.Z]` section and confirm exactly one announcement; edit text under an existing version and confirm silence.

**Acceptance Scenarios**:

1. **Given** the latest changelog version header is already recorded as posted, **When** the bot restarts (same or different deploy/commit identity), **Then** no changelog embed is posted.
2. **Given** a new version header such as `## [1.6.0]` is added above prior sections, **When** the bot starts up, **Then** exactly one changelog embed is posted to the configured announcement channel (or its fallback), and that version is recorded as posted.
3. **Given** only the body text under the current version header changes (no new version header), **When** the bot starts up, **Then** no changelog embed is posted.
4. **Given** two bot instances start at the same time after a new version header appears, **When** both attempt to announce, **Then** exactly one embed is posted.
5. **Given** the bot claims a new version but fails to deliver the Discord message, **When** a later restart occurs with the same latest version still unpublished, **Then** the announcement remains retryable until a successful post records that version.

---

### User Story 3 - Reliable Top.gg Vote Reminder (Priority: P3)

As a manager who votes on Top.gg, I want at most one reminder (DM or Store fallback) per expired vote window, with correct cooldown timing and a working disabled-DM fallback, so that I am nudged to vote without being spammed.

**Why this priority**: The vote reminder is one of the two automations retained from the shelved work. Correctness (dedupe, timing, DM fallback) must be verified and tightened so the kept feature is trustworthy.

**Independent Test**: Seed one expired vote window, run the periodic reminder job (alone and under concurrent instances), confirm a single DM or a single Store fallback; verify Top.gg-provided next-vote time is preferred for scheduling; confirm disabled DMs produce one Store notice that clears after display.

**Acceptance Scenarios**:

1. **Given** a manager whose vote cooldown has expired and Top.gg confirms they have not voted again, **When** the periodic reminder job runs, **Then** they receive exactly one DM for that vote window.
2. **Given** two bot instances process the same due reminder window, **When** both claim work, **Then** only one reminder completes for that window key.
3. **Given** Top.gg provides a next-vote eligibility time, **When** the reminder schedule is written, **Then** that time is used; only if it is unavailable does the system fall back to last-vote-time plus the standard 12-hour cooldown.
4. **Given** a reminder DM cannot be delivered because DMs are disabled, **When** that failure is recorded, **Then** the vote window is marked handled with a Store fallback pending; opening Store shows the fallback once and clears it; the same window never produces additional DMs.
5. **Given** a transient Top.gg or network failure during a reminder attempt, **When** the job backs off and retries later, **Then** a successful later send still produces at most one reminder for that vote window.

---

### Edge Cases

- What if PvP schema objects were already applied on a connected database? Product files for those migrations are removed from the repo, and a single forward cleanup restores the database to the pre-PvP (post–Youth Academy) shape so live environments are not left with orphaned PvP tables, flags, or RPCs.
- What if shared files contain both Youth Academy/non-PvP fixes and PvP hunks? Only PvP-specific changes are removed; Academy and unrelated later fixes stay.
- What if the automation commit also touched Friendly/battle paths beyond Top.gg and changelog? Those PvP-adjacent battle changes are cleaned out; only changelog sender and vote reminder survive from that line of work.
- What if `change_log.md` is missing or has no valid version header? Startup skips announcement quietly and does not block the bot.
- What if no announcement channel is messageable? Changelog send is skipped without recording the version as posted, so a later start can retry after permissions are fixed.
- What if Top.gg says the user already voted when a reminder is due? No DM is sent; the next eligibility window is updated instead.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST remove all active PvP product surfaces, including matchmaking queue, rivalries, ghost/backfill managers, Practice-as-PvP fallback, Find Opponent / Ranked entry points, and PvP feature flags from config and player-facing documentation.
- **FR-002**: System MUST restore `/battle` so managers can only start Bot Battle (original AI/bot match) and Friendly Battle, matching the last pre-PvP battle baseline behavior.
- **FR-003**: System MUST preserve Youth Academy V2 behavior and its associated schema era; Academy work MUST NOT be rolled back as part of shelving PvP.
- **FR-004**: System MUST remove PvP-only specifications, tests, scratch tooling, and temporary assets that were introduced for the shelved initiative, while retaining Youth Academy and vote-reminder/changelog automation assets that are still in scope.
- **FR-005**: For environments where PvP schema was already applied, System MUST ship one forward cleanup that drops PvP-only tables, columns, flags, check-constraint values, indexes, policies, and RPCs and restores shared constraints/functions to their pre-PvP (post–Academy) definitions.
- **FR-006**: Schema verification and product requirements MUST no longer require any PvP objects or flags after cleanup.
- **FR-007**: Changelog announcement MUST decide whether to post solely by comparing the latest changelog version header to the last successfully posted version; deploy/commit identity, file mtime, restart count, and whole-file hash MUST NOT trigger a post.
- **FR-008**: Editing text under an existing version header MUST NOT cause a new announcement; only adding a new version header MUST make a post eligible.
- **FR-009**: Claiming and recording a changelog version MUST be atomic across concurrent bot instances so a new version produces exactly one successful channel post.
- **FR-010**: Failed Discord delivery of a changelog MUST leave that version unrecorded (or otherwise retryable) so a later successful start can post it once.
- **FR-011**: System MUST keep the periodic Top.gg vote reminder job, reminder state, Store fallback path, and related schema introduced for that automation.
- **FR-012**: System MUST treat the vote-window identity as authoritative so at most one completed reminder (DM or handled fallback) exists per window across concurrent bot instances.
- **FR-013**: System MUST schedule reminder checks from Top.gg’s next-vote time when available, falling back to last-vote-time plus 12 hours only when that time is missing.
- **FR-014**: When a reminder DM is forbidden, System MUST mark that window handled with a one-time Store fallback; Store MUST show the notice once and clear it; transient failures may retry with backoff but MUST NOT create multiple reminders for the same window.
- **FR-015**: After cleanup, active searches for PvP matchmaking, rivalry, ghost manager, Practice PvP fallback, and PvP enablement flags MUST find no remaining product code paths (Git history excluded).

### Key Entities

- **Pre-PvP Battle Baseline**: The classic Bot Battle + Friendly battle product state managers expect after shelving; reference point for restored behavior (last clean pre-PvP battle revision).
- **Changelog Version Record**: The single stored identifier of the last successfully announced changelog version header; compared on startup to the latest header in the player-facing changelog.
- **Vote Reminder Window**: One eligibility interval per manager vote cooldown, uniquely identified so reminders and Store fallbacks cannot duplicate for that interval.
- **PvP Artifact Set**: Shelved tables, flags, RPCs, modules, specs, tests, and tools that must be erased from the active product and cleaned from applied databases via forward migration.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of managers using `/battle` after cleanup see only Bot Battle and Friendly; zero PvP/queue/rivalry entry points remain in the live battle UI.
- **SC-002**: Bot Battle completion matches the pre-PvP baseline outcome path in acceptance checks (no ranked/Practice substitution).
- **SC-003**: Active-code and schema-requirement searches for PvP matchmaking, rivalries, ghost managers, and PvP feature flags return zero remaining product hits.
- **SC-004**: On a normal restart with no new changelog version header, announcement channels receive 0 changelog posts.
- **SC-005**: When a new version header is added, announcement channels receive exactly 1 changelog post for that version, even if multiple bot instances start together or the bot restarts again on the same version.
- **SC-006**: Edits under an existing version header produce 0 announcements.
- **SC-007**: Each expired Top.gg vote window produces at most 1 DM or 1 Store fallback notice, including under concurrent reminder processing.
- **SC-008**: Youth Academy acceptance behavior that existed before this cleanup remains passing / unchanged.
- **SC-009**: Operators can apply the forward DB cleanup and schema verification with no remaining PvP requirements in the guard list.

## Assumptions

- Rollback boundary for battle/matchmaking behavior is the last pre-PvP reference revision identified in the cleanup plan (`1737df6`); PvP work begins immediately after that revision.
- The first mixed commit that introduced Youth Academy V2 alongside early PvP pieces is cleaned **selectively**: Academy preserved, PvP removed — not a wholesale revert.
- Later pure-PvP commits in that series are fully removed from the active tree; the Top.gg reminder + changelog automation commit is **not** wholesale-reverted — those two features survive and are fixed in place.
- A later commit that exposed commit-based changelog keys and touched battle/Friendly paths is cleaned selectively: keep automation intent, remove PvP-adjacent battle material, and fix version-only changelog dedupe.
- Youth Academy migrations in the 095–097 era remain; PvP migration artifacts 098–106 are removed from the repo; automation migration 107 remains; applied databases get one forward cleanup after 107 rather than rewriting history.
- Changelog channel resolution and embed presentation from the existing automation remain; only the “when to post” contract changes to version-header comparison.
- Vote reminder cadence remains approximately every 30 minutes; that latency after eligibility is acceptable versus continuous spam.
- The Top.gg listing used by reminders remains the ElevenBoss bot listing already configured for this product.
- No new slash commands, hubs, or tables are introduced beyond what is required to restore pre-PvP battle behavior and correct the two retained automations.
- Detailed file/commit inventory and implementation sequencing belong in the technical plan (`/speckit-plan`); this specification defines the required end state and acceptance outcomes.
)
