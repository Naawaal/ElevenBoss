# Feature Specification: Match Engine V3 Production Rollout

**Feature Branch**: `044-match-v3-rollout`

**Created**: 2026-07-24

**Status**: Code complete — bot soak ops pending (flags remain off)

**Input**: User description: "Master project audit after Marketplace Intelligence (043) completion — recommend the single highest-ROI next major task. Chosen direction: safely enable Match Engine V3 (already implemented under 041) on bot then league, with player-facing post-match explainability, without new slash commands or parallel settlement systems."

**Parent / related**: Extends Implemented `specs/041-match-engine-v3` (engine already in-tree; flags off). Integrity overlays US-42.4 (`033`). Does **not** reopen marketplace feature work.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Bot matches run on V3 under a controlled soak (Priority: P1)

Ops enables V3 for bot battles in a staging or limited production soak. Managers playing `/battle` bot matches get V3 Decision Windows and tactical transition styles, while settlement (coins, XP, fatigue, injury) remains the same pipes and settle-once rules. In-flight v2 runs never mid-switch engines.

**Why this priority**: The match is the daily climax; V3 code is already shipped — the missing product step is a safe flag rollout, not a new system.

**Independent Test**: With bot flag on and league/friendly flags off, complete three bot matches; confirm `match_runs.engine_version` is `nss_v3`, rewards apply once, and a concurrent league match (if any) still uses v2.

**Acceptance Scenarios**:

1. **Given** `match_engine_v3_bot` is enabled and league/friendly flags remain off, **When** a manager completes a bot battle, **Then** the match runs on V3 (Decision Windows + available transition styles) and coins/XP/fatigue/injury settle exactly once via existing pipes.
2. **Given** a bot match is already in progress on v2 when the flag flips, **When** that run completes or recovers, **Then** it finishes on the engine version pinned at kickoff — no mid-run engine swap.
3. **Given** the bot flag is off, **When** managers play bot battles, **Then** behavior matches pre-rollout v2 (no forced V3).

---

### User Story 2 — Managers understand why the match turned (Priority: P1)

After a V3 bot (and later league) match, the manager sees a short, readable explainability summary — key turning points and/or tactical moments — so a loss feels attributable to decisions/context, not opaque RNG.

**Why this priority**: Retention comes from “I can improve,” not from engine internals. Projector data already exists; managers need it on the post-match surface they already see.

**Independent Test**: Finish a V3 bot match; post-match embed/follow-up includes at least one turning-point or decision-window insight derived from the match event stream (not invented text).

**Acceptance Scenarios**:

1. **Given** a completed V3 match with recorded events, **When** the post-match result is shown, **Then** the manager sees a concise explainability section (turning points and/or decision moments) consistent with the event stream.
2. **Given** a match with few notable moments, **When** explainability is shown, **Then** the UI degrades gracefully (short empty/minimal copy) rather than fabricating drama.
3. **Given** a v2 match (flag off or pinned v2), **When** the post-match result is shown, **Then** existing result presentation remains usable (no broken V3-only fields).

---

### User Story 3 — League can adopt V3 after bot soak confidence (Priority: P2)

After bot soak criteria pass, ops enables V3 for league matches. Auto-sim, live league play, and recovery continue to honor settle-once, standings, and pause/resume rules.

**Why this priority**: League is the weekly retention hook; it must not cut over before bot soak proves sporting + integrity stability.

**Independent Test**: With league flag on, complete one live and one auto-sim league fixture; both pin `nss_v3`, update standings once, and recover cleanly if interrupted.

**Acceptance Scenarios**:

1. **Given** bot soak criteria are met and `match_engine_v3_league` is enabled, **When** a league fixture is played live or auto-simmed, **Then** it uses V3 and league points/standings update exactly once.
2. **Given** league V3 is on, **When** a matchday lock or pause/resume occurs, **Then** existing league integrity behavior is preserved (no sporting forfeit from infrastructure alone).
3. **Given** league flag remains off, **When** bot V3 is on, **Then** league matches stay on v2.

---

### User Story 4 — Friendly remains a safe sandbox choice (Priority: P3)

Friendly matches can stay on v2 during bot/league soak, or be enabled later under a separate flag — without applying competitive economy rewards.

**Why this priority**: Friendies are sandbox; they must not block the competitive rollout or invent reward paths.

**Independent Test**: With only bot flag on, a friendly still completes as a sandbox (no coins/XP/evo) on its configured engine pin.

**Acceptance Scenarios**:

1. **Given** friendly V3 flag is off, **When** managers play a friendly, **Then** sandbox rules hold and engine pin follows the friendly flag (default v2).
2. **Given** friendly V3 is later enabled, **When** a friendly completes, **Then** sandbox economy rules still hold (no competitive faucets).

---

### Edge Cases

- Flag flip mid-matchday: in-flight runs keep kickoff engine pin.
- Recovery after bot restart: recovered V3 run matches deterministic replay of same seed/events.
- Dual-run monitoring: abnormal reward doubles or settle failures abort further flag expansion.
- Explainability on auto-sim (no human watching live): summary still available on result post / Match Center where results already surface.
- HTTP/DB flakiness during settlement: existing settle-once and recovery rules remain authoritative (no “engine caused forfeit”).
- Manager on mobile with weak connection: post-match explainability must not block reward settlement if presentation fails.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow independent enablement of V3 by match type via existing config keys (`match_engine_v3_bot`, `match_engine_v3_league`, `match_engine_v3_friendly`) without a new slash command.
- **FR-002**: Every match run MUST pin engine version at kickoff; completion and recovery MUST use that pin.
- **FR-003**: Bot V3 enablement MUST be the first production cutover step; league MUST NOT enable before documented bot soak criteria pass.
- **FR-004**: Settlement for coins, XP, fatigue, injury, league points MUST remain on existing pipes (no parallel reward path).
- **FR-005**: Friendly sandbox rules MUST remain (no competitive coins/XP/evo) regardless of engine version.
- **FR-006**: Post-match surfaces for V3 matches MUST show a concise explainability summary derived from the event stream / existing projectors (turning points and/or decision moments).
- **FR-007**: Explainability MUST NOT invent events; empty/minimal states are required when data is thin.
- **FR-008**: Auto-sim and live league paths MUST both honor the league engine flag and settle-once semantics.
- **FR-009**: Ops MUST have a clear rollback: disabling a type flag returns new kicks for that type to v2 without corrupting in-flight pinned runs.
- **FR-010**: Player-facing changelog MUST note V3 when bot (and later league) is enabled for real managers.
- **FR-011**: This feature MUST NOT add marketplace systems, new hubs, Redis/sharding, Ranked PvP, or wage-flag flips.

### Key Entities

- **Engine Flag**: Per match-type on/off control selecting NSS v2 vs v3 for new kicks.
- **Pinned Match Run**: Durable run record with engine version fixed at start.
- **Explainability Summary**: Short manager-facing projection from match events (turning points / decisions).
- **Soak Criteria**: Ops checklist of successful bot matches, integrity greps, and absence of double-settle before league enable.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With bot flag on, 100% of new bot kicks in the soak window pin `nss_v3` and settle rewards at most once.
- **SC-002**: Zero mid-run engine switches observed across soak + recovery drills.
- **SC-003**: ≥90% of completed V3 bot matches in a playtest sample show a non-empty explainability section when the event stream contains at least one turning-point candidate.
- **SC-004**: After league enable, live and auto-sim league fixtures update standings correctly with no duplicate point grants in a 20-fixture sample.
- **SC-005**: Rollback (bot flag off) returns subsequent bot kicks to v2 within one config refresh / process restart as documented — in-flight v3 runs still finish cleanly.
- **SC-006**: No increase in “coins vanished / double paid” support incidents attributable to the cutover during the first 14 days of bot soak (qualitative ops check).

## Assumptions

- Match Engine V3 implementation under `041` (T001–T079) is already in the codebase; this feature is **rollout + explainability surfacing**, not a re-build.
- Marketplace Intelligence (`043`) is treated as feature-complete for marketplace scope; no further market mechanics in this work.
- Bot soak default target: staging or limited guild first; then broaden bot; then league.
- Friendly V3 can remain off through bot+league soak unless a specific reason emerges.
- Existing HTTP client hardening (HTTP/1.1) remains; not in scope to redesign networking here.
- Squad “Tactics” Soon button is **out of scope** for this feature (follow-up after V3 is visible).

## Out of Scope

- New Ranked / matchmaking modes
- Further marketplace features
- Enabling wages payroll / league dynamics flags
- Redis, sharding, multi-instance economy cache
- Public website
- Adaptive AI, Dixon-Coles in live play, player-traits expansion
- New slash commands or hubs
- Full squad pre-match tactics UI (deferred follow-up)

## Dependencies

- `specs/041-match-engine-v3` implementation + migration `083`
- US-42.4 match integrity (settle-once, locks, recovery)
- Existing `/battle` and league play / auto-sim paths
- Existing explainability projectors / `turning_points` hooks already referenced from battle flows

## Risks & Compatibility Notes

- Sporting feel change when Decision Windows become authoritative — communicate in changelog.
- League cutover too early could amplify integrity incidents — hard gate on soak criteria.
- Explainability copy must stay short for Discord ephemeral/mobile.
- Dual-run period increases ops monitoring load briefly — accept as cost of safe rollout.
)
