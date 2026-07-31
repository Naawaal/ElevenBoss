# Feature Specification: Expired League Fixtures Stuck Pending Auto-Sim

**Feature Branch**: `048-fix-league-autosim`

**Created**: 2026-07-31

**Status**: Draft

**Input**: User description: "Seasonal League Hub shows Matchday 5/14 with window closed a day ago; two fixtures remain Expired (Pending Auto-Sim) (Bhavs FC™ vs Majestic FC AI; MANCHESTER CHOCO FC vs Dragon Club) while other matchday fixtures are Full Time. Season appears stuck."

**Parent / related**: Extends Implemented league pacing/auto-sim (`league_cog.auto_sim_expired_fixtures`, scheduler legacy job, hub-on-open sim) and integrity children **US-42.5** (league settle / pause). Related to contract past-grace gates (`019`) and fail-closed XI skips (`007`). Does **not** reopen Dynamics redesign or Match Engine V3 rollout.

**Investigation snapshot (live season)**: Guild season #2 is `pacing_mode=legacy`, `status=active`, matchday 5. Window ended ~2026-07-30. Two MD5 fixtures remain `is_played=false` with no `match_runs`. Auto-sim **skips** human clubs that fail XI/contract gates without settling the fixture — confirmed past-grace starters in XI for **Bhavs FC™** (3) and **Dragon Club** (7). Hub label “Expired (Pending Auto-Sim)” is display-only; nothing is guaranteed to complete.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Expired fixtures finish so the matchday can move on (Priority: P1)

After a fixture’s play window ends, every pairing on that matchday reaches a settled result (played scoreline or explicit forfeit/resolution) within a short, predictable bound — not left as “Pending Auto-Sim” for a day or more. Managers can see standings that include those results and the season can advance when the matchday is complete.

**Why this priority**: Unsettled expired fixtures block matchday advance and make the league hub look broken for everyone in the guild (Mirai MidNight and peers).

**Independent Test**: On a legacy active season with ≥1 expired unplayed fixture (including cases where a human side has past-grace / invalid XI), trigger the settle path (hub open and/or scheduled job). Fixture becomes played/settled; matchday advances when all MD fixtures are settled.

**Acceptance Scenarios**:

1. **Given** an expired unplayed fixture where both sides can legally auto-sim, **When** hub-on-open or the legacy auto-sim job runs, **Then** the fixture is settled with a score and is no longer labeled Pending Auto-Sim.
2. **Given** an expired unplayed fixture where at least one **human** side cannot legally field a match XI (past-grace contracts, incomplete XI, or `squad_invalid`), **When** the settle path runs, **Then** the fixture is still **resolved** (not left pending forever) via a defined fallback (e.g. forfeit against the blocking side, or other approved settle rule) — not a silent skip with no DB result.
3. **Given** all fixtures on the current matchday are settled, **When** the advance path runs, **Then** the season’s current matchday progresses (or season completes) according to existing league rules.
4. **Given** an AI opponent, **When** the human side is eligible, **Then** expired auto-sim still settles (AI clubs do not permanently block via empty squad_assignments).

---

### User Story 2 — Honest hub copy when settle is blocked or delayed (Priority: P2)

Managers opening Fixtures / Hub understand whether auto-sim is about to run, failed, or resolved via fallback — not a perpetual “Pending Auto-Sim” with no next step.

**Why this priority**: The reported UI already shows pending; without clearer status, managers think the bot is broken or must wait forever.

**Independent Test**: With one expired fixture blocked by past-grace XI, open Fixtures — copy names the blocking club/reason or shows a resolved forfeit; does not imply infinite wait with no action.

**Acceptance Scenarios**:

1. **Given** an expired unplayed fixture, **When** shown on Fixtures, **Then** status is either settled, clearly “auto-sim imminent/retrying”, or names why it cannot sim and what the manager must do (renew/replace) **or** that a forfeit/fallback applied.
2. **Given** the matchday window closed (hub “Window closes: a day ago”), **When** the manager views Season Progress / Fixtures, **Then** they are not told only “Pending Auto-Sim” with no recovery hint for > one settle cycle after window end.
3. **Given** settle just succeeded on hub open, **When** Fixtures refresh, **Then** the former pending rows show Full Time (or forfeit) scores.

---

### User Story 3 — Silent failures are visible to ops and recoverable (Priority: P3)

When auto-sim cannot resolve a fixture due to infrastructure (missing guild/threads) or unexpected errors, the system retries or surfaces a recoverable state instead of dropping the attempt with only a log line.

**Why this priority**: Secondary to the XI/contract skip hole; still needed so guild-unreachable cases do not strand seasons.

**Independent Test**: Documented path: after guild/threads available again, expired fixtures settle on next hub open or job; paused seasons follow existing pause/resume integrity.

**Acceptance Scenarios**:

1. **Given** guild/threads temporarily unavailable, **When** auto-sim runs, **Then** it fails closed without marking fixtures played, and a later successful run settles them.
2. **Given** a mid-sim exception, **When** handled, **Then** any active match run is abandoned/cleaned so a later settle can proceed (existing abandon behavior retained or improved).

---

### Edge Cases

- Both human clubs invalid XI → both-side fallback must still produce one settled result (define in plan: double forfeit / 0-0 administrative / home/away rule — pick one in plan).
- One human already played other MD5 fixtures manually; only the expired pairs remain.
- Active `match_runs` row → do not double-sim (keep skip-while-active).
- `lifecycle_v1` / Dynamics seasons: same “no infinite pending” outcome; entry points may differ (state machine vs legacy job) but managers must not see day-old Pending forever.
- AI vs AI expired fixtures (if any) still settle.
- Contract renew after window end: once XI is legal again, next settle cycle must clear pending (or fallback already settled).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Every fixture whose play window has ended MUST reach a settled terminal state (`is_played` / equivalent) without requiring the original play window to still be open.
- **FR-002**: Auto-sim MUST NOT leave an expired fixture unsettled indefinitely solely because a human club fails XI/contract eligibility — a fallback settle rule MUST apply when eligibility fails after window end.
- **FR-003**: Hub-on-open and scheduled legacy auto-sim (and Dynamics tick where applicable) MUST continue to attempt settle for expired unplayed fixtures on active seasons.
- **FR-004**: Fixtures UI MUST not present perpetual “Pending Auto-Sim” without either progress within one settle cycle or actionable/fallback status copy.
- **FR-005**: Matchday advance MUST run after settles so seasons do not remain on a completed-window matchday with only partial results.
- **FR-006**: Settlement MUST remain settle-once (no double standings/points for the same fixture) — **US-42.5**.
- **FR-007**: Pause/resume and guild-unreachable behaviour MUST remain integrity-safe (no sporting forfeit solely for bot outage; distinguish club eligibility failure from infrastructure failure) — align with absence-vs-outage principles.
- **FR-008**: No new slash command required; extend existing `/league` hub / auto-sim paths.
- **FR-009**: Feature MUST document the chosen fallback when a human side is ineligible after window end (forfeit vs other) so managers and ops share one rule.

### Key Entities

- **Expired fixture**: `window_end < now` and not yet played/settled.
- **Settle cycle**: One hub-on-open or scheduled auto-sim pass for a season.
- **Eligibility failure**: Human club cannot legally match (incomplete XI, `squad_invalid`, past-grace contracts in XI).
- **Infrastructure failure**: Guild/threads unavailable or transient bot errors (retry, do not sports-forfeit).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the reported Season #2 Matchday 5 (or equivalent fixture set), both currently pending fixtures reach settled status within one successful settle cycle after the fix is deployed (or via the defined fallback if still ineligible).
- **SC-002**: No expired unplayed fixture on an active legacy season remains unsettled for more than one scheduled auto-sim interval + one hub open after deploy (except while guild is unreachable / season paused for outage).
- **SC-003**: When a fixture is settled via fallback due to ineligibility, managers can tell from Fixtures/hub that it was not a normal played match (forfeit/admin label or equivalent).
- **SC-004**: Standings points for a fixture update at most once (settle-once).
- **SC-005**: After all MD fixtures settle, current matchday advances per existing rules.

## Assumptions

- Primary production hole: **silent skip** of ineligible human sides after window end (contracts/XI), leaving “Pending Auto-Sim” forever — evidenced by Bhavs / Dragon Club past-grace starters on the reported fixtures.
- Secondary risks: thread/guild resolve returning early; exceptions swallowed in auto-sim loop — plan must verify and harden if still present.
- Window-closed relative copy (“a day ago”) is correct time display; the defect is lack of settle, not the relative clock.
- Prefer a **single** fallback rule for ineligible post-window humans (likely: forfeit loss for the ineligible side; if both ineligible, fixed administrative result) — exact choice is a plan decision with max one clarification if product disagrees.
- AI clubs continue to use generated squads; empty `squad_assignments` for AI is not treated as human XI failure.

## Out of Scope

- Changing Season Pts vs Weekly Division Rank / Global LP explanations
- Redesigning Dynamics UTC midnight pacing
- Bulk auto-renew of past-grace contracts
- New admin slash command for “force sim all” (ops SQL/RPC in quickstart OK if needed)
- Reopening Match Engine V3 flag policy
