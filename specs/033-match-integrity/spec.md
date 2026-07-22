# Feature Specification: Match Integrity & Concurrency (US-42.4)

**Feature Branch**: `033-match-integrity`

**Created**: 2026-07-22

**Status**: Locked

**Parent epic**: `specs/029-game-integrity` (US-42)

**Child ID**: US-42.4 — Match Integrity & Concurrency

**Depends on**: US-42.1 (`030`), US-42.2 (`031`), US-42.3 (`032`) — ownership, card busy matrix, club MatchLocked overlay

**Overlays**: League fixtures & deadlines (`026`/`027`) for sporting schedule only; economy pipe (US-25 / US-42.7 registry later); progression XP pipe (US-23)

**Input**: User description: "Continue next step — US-42.4 Match Integrity after 42.1–42.3. Parent 029. Match types; lock lifecycle; settlement order; reward once; disconnect/abandon; replay protection. INV-09, INV-10, INV-17. Child template. Non-goals: no second league calendar; no marketplace races; no faucet registry rewrite."

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — One durable match run, reward once (Priority: P1) 🎯 MVP

Every competitive or bot match that can grant coins/XP is identified by a durable **match run**. Settlement writes a durable result and applies rewards **at most once** for that run (or fixture×club where applicable). Restarting the bot, double-tapping Play, or retrying a failed Discord embed never double-pays.

**Why this priority**: INV-09; double-finalize is the highest-cost integrity failure.

**Independent Test**: Double-invoke settle / replay with same match_run_id → one ledger+XP effect; second call returns prior success or clear already-settled.

**Acceptance Scenarios**:

1. **Given** a bot match that settled successfully, **When** the same settlement path is invoked again with the same run id, **Then** coins/XP/energy are not applied a second time.
2. **Given** Discord fails to post the result embed after settlement, **When** presentation retries, **Then** rewards are not re-run.
3. **Given** two concurrent finalize attempts for the same run, **When** both finish, **Then** at most one durable reward application occurs.

---

### User Story 2 — Lock lifecycle blocks mid-match tampering (Priority: P1)

While a club is MatchLocked, roster, development, sale/list, and new match-start actions are Blocked (aligned with US-42.2 / US-42.3 matrices and INV-17). Locks are acquired before simulation that commits rewards and released on terminal success, abandon, or documented failure recovery — never left forever without an ops/recovery path.

**Why this priority**: Mid-match XI swaps and drills are classic exploit/support classes.

**Independent Test**: With lock present, squad swap / drill / league join / new match start Block; after release, Allowed subject to other states.

**Acceptance Scenarios**:

1. **Given** MatchLocked during a live bot/league sim, **When** the manager tries squad swap or start evolution, **Then** Block.
2. **Given** settlement completes successfully, **When** lock release runs, **Then** MatchLocked clears for that club.
3. **Given** a run is abandoned or fails after lock, **When** recovery completes, **Then** lock is cleared (or explicitly held only under documented ops rule — default = clear on terminal abandon/fail).

---

### User Story 3 — Settlement order is DB-authoritative (Priority: P1)

Simulation may stream in Discord for drama, but **durable truth** is the settled match run / history / fixture result. Rewards never precede a durable settled result without sharing one atomic unit of work with that result (INV-09). Evolution match progress ticks **at most once** per card per match settlement (INV-10).

**Why this priority**: Historical friendly double-tick and reward-without-result classes.

**Independent Test**: Grep/audit: evo tick only inside settlement pipe for rewarding matches; friendly sandbox does not grant economy/XP/evo tick.

**Acceptance Scenarios**:

1. **Given** a bot or league match settlement, **When** XP/economy/evo tick apply, **Then** they occur with or after durable result commit — never as a lone Discord-only success.
2. **Given** the same card appears once in a settled XI, **When** settlement runs once, **Then** evolution progress increments at most once for that card for that result.
3. **Given** a friendly match, **When** it completes, **Then** no coin faucet, no match XP pipe, and no evolution tick (sandbox logs/presentation only).

---

### User Story 4 — Disconnect / abandon / restart recovery (Priority: P2)

If the bot restarts mid-stream, Discord thread dies, or the manager disconnects, the system either completes settlement once from durable run state, marks the run abandoned/failed without inventing a free win, or offers a documented recovery — never silent double pay and never infrastructure-invented sporting forfeits for league fixtures (those stay `026`).

**Why this priority**: Live-service restarts are routine on Render.

**Independent Test**: Simulate restart with run in streaming/completing → catch-up settles once or abandons cleanly with lock released.

**Acceptance Scenarios**:

1. **Given** a streaming bot match and bot restart, **When** recovery runs, **Then** either one settlement completes or the run is abandoned/failed without a second reward key.
2. **Given** a league fixture run interrupted, **When** recovery interacts with fixture state, **Then** sporting terminal rules defer to `026` (forfeit/assistant) — this child only ensures lock/reward idempotency.
3. **Given** stale Play button after run already completed, **When** pressed, **Then** server rejects or no-ops without new rewards.

---

### User Story 5 — Match types stay distinct (Priority: P2)

Bot, friendly, and league matches share lock/settlement integrity patterns but keep distinct reward and competitive rules. Managers can tell which type they played; integrity rules do not collapse friendly into a coin faucet.

**Why this priority**: Prevents “friendly farm” regressions and keeps XP multipliers honest.

**Independent Test**: Matrix of type × (coins, XP, evo tick, fixture binding) matches this spec.

**Acceptance Scenarios**:

1. **Given** bot match, **When** settled, **Then** economy + XP via existing pipes with run idempotency; evo tick once via settlement.
2. **Given** league match, **When** settled, **Then** fixture-bound history unique; rewards once; evo tick once.
3. **Given** friendly, **When** completed, **Then** no economy faucet / match XP / evo tick.

---

### Edge Cases

| ID | Scenario | Expected | Recovery |
|----|----------|----------|----------|
| E1 | Double-tap Play | ≤1 active lock/run per club policy | Second → locked/busy |
| E2 | Settle twice same run id | One reward | Idempotent return |
| E3 | Embed timeout after settle | Rewards kept; retry embed | Presentation only |
| E4 | Lock without run row | Fail closed; clear orphan lock via recovery | Ops/recovery job |
| E5 | Run completed, lock stuck | Recovery clears lock | Sweeper / release RPC |
| E6 | Friendly + evo UI still visible | No tick applied | Audit INV-10 |
| E7 | League fixture two managers | Each club lock/rules; one fixture result truth | `026` + run uniqueness |
| E8 | Squad invalid at start | Block start; no lock or immediate abort | Fix squad |
| E9 | Energy insufficient after lock race | Abort; release lock; no rewards | Retry |
| E10 | Concurrent bot + league start | Second Block while MatchLocked | Wait |
| E11 | Card Listed in snapshot | Start blocked by card/club gates before lock | US-42.2 |
| E12 | Soft Abandoned club starts bot | Allowed per US-42.3 matrix (progression); still lock/settle once | Soft ≠ match ban |
| E13 | Restart during completing | Complete once or fail without double pay | Idempotent key |
| E14 | Wrong owner presses stale thread button | Reject ownership | US-42.1 |

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Every rewarding match MUST have a durable match run identity used as the primary idempotency key for settlement/rewards (or an equivalent documented key that is unique per logical match).
- **FR-002**: Settlement MUST write durable result state before or together with rewards in one atomic unit of work (INV-09).
- **FR-003**: Replaying settlement for the same key MUST NOT double-apply coins, energy, match XP, or evolution ticks.
- **FR-004**: Presentation failures after successful settlement MUST retry display only — never re-enter reward application.
- **FR-005**: MatchLocked MUST be acquired before reward-committing simulation and MUST Block roster/dev/sale/new-match mutations until cleared (INV-17; US-42.2/42.3 matrices).
- **FR-006**: Terminal success, abandon, and fail paths MUST release MatchLocked for affected human clubs (or document a time-bounded hold with automatic clear).
- **FR-007**: Evolution match progress MUST tick at most once per card per settled rewarding match (INV-10); friendly MUST NOT tick.
- **FR-008**: Friendly matches MUST NOT grant coins via the economy faucet, MUST NOT grant match XP via the XP pipe, and MUST NOT tick evolutions.
- **FR-009**: Bot and league rewarding paths MUST use existing economy and XP pipes (`apply_club_economy` / `apply_card_xp` families) — no parallel coin/XP writers.
- **FR-010**: League fixture binding MUST prevent duplicate durable history rows for the same player×fixture where uniqueness already exists; settlement is fixture-aware.
- **FR-011**: Start gates MUST re-check current ownership (US-42.1), card busy matrix (US-42.2), and club MatchLocked (US-42.3) before creating a rewarding run.
- **FR-012**: Stale interactive controls after terminal state MUST fail closed (no new run/rewards).
- **FR-013**: Infrastructure outages MUST NOT invent league sporting forfeits; defer sporting terminals to `026`.
- **FR-014**: Orphan locks / stuck runs MUST have a documented recovery behavior (manual RPC and/or startup/sweeper path).
- **FR-015**: Match types remain `bot` | `friendly` | `league` with distinct reward rules in §B.
- **FR-016**: No new slash commands or hubs for integrity alone.
- **FR-017**: This feature MUST NOT rewrite the `026` calendar or marketplace purchase races (US-42.6).
- **FR-018**: Player-facing behavior changes managers notice MUST update `change_log.md` when shipped.

### Key Entities

- **MatchRun**: Durable run with type, status, participants, optional fixture, snapshot, completion key.
- **MatchLock**: Club overlay blocking mutations (INV-17).
- **Settlement**: Atomic result + reward application for a run key.
- **PresentationAttempt**: Non-authoritative Discord render/retry.
- **MatchType**: bot | friendly | league.

---

## A. Epic invariant touch list

| INV | Role in US-42.4 |
|-----|-----------------|
| **INV-02** | Bound — start/settle use current owners |
| **INV-04/05** | Bound — match coins via economy pipe only |
| **INV-06** | Bound — match XP via XP pipe only |
| **INV-09** | Primary — settle+reward atomic / ordered |
| **INV-10** | Primary — evo tick ≤1 per card per result |
| **INV-17** | Primary — lock lifecycle |
| **INV-18** | Bound — daily match XP caps still server-side when Allowed |

Does not weaken epic INVs. Aligns epic §5.3 names with durable run/lock semantics.

---

## B. State machine / lifecycle

### B.1 Match run (logical)

| State | Meaning | Entry | Exit |
|-------|---------|-------|------|
| **Created** | Run id reserved / row started | Start accepted | Lock or Abort |
| **Locked** | MatchLocked held; snapshot frozen for sim | Acquire lock | Simulating / Abort |
| **Simulating** | Engine / stream in progress | Sim starts | Settled / Abort |
| **Settled** | Durable result committed | Result write | Rewarded (may be same txn) |
| **Rewarded** | Economy/XP/evo applied once | Settlement unit | Presented |
| **Presented** | Discord updated (best effort) | Embed/thread update | Terminal |
| **Aborted** | No rewards (or rolled back) | Gate fail / abandon / fail | Lock released |

Informative mapping to existing run statuses (e.g. streaming≈Simulating, completed≈Settled+Rewarded, abandoned/failed≈Aborted) is an implementation concern — logical guarantees above are normative.

### B.2 Lock overlay

| Event | Lock |
|-------|------|
| Enter Locked | Acquire for human club(s) that must not mutate |
| Rewarded / Aborted terminal | Release |
| Restart recovery | Ensure terminal or release orphan |

### B.3 Type × reward matrix

| Effect | Bot | League | Friendly |
|--------|-----|--------|----------|
| MatchLocked during live | Yes | Yes | Yes (if used) |
| Coins / energy economy | Yes (pipe) | Yes (pipe) | No faucet |
| Match XP | Yes | Yes | No |
| Evo tick | Yes (once) | Yes (once) | No |
| Fixture binding | No | Yes | No |

### B.4 Failure recovery

| Failure | Behavior |
|---------|----------|
| Crash after Settled+Rewarded, before Present | Retry present only |
| Crash before Settled | Abort or resume-to-settle once; no duplicate key |
| Double settle | Idempotent |
| Lock stuck | Recovery clears |

---

## C. Logical actions & idempotency

| Action | Actor | Idempotency key pattern | Pipeline | Success | Reject reasons |
|--------|-------|-------------------------|----------|---------|----------------|
| `start_match` | Owner | Natural: one active lock/run per club | Ownership + Competitive | Created→Locked | Busy lock; card/club gates; energy |
| `settle_match` | System | `match_run_id` / completion_key | Economy+XP+Competitive | Settled+Rewarded | Already settled; invalid state |
| `present_match` | System | Presentation retry; not reward key | Presentation | Embed shown | Discord errors |
| `abandon_match` | System/ops | Run id | — | Aborted; lock clear | — |
| `release_match_lock` | System | Club id | — | Lock gone | — |
| `tick_evolution_match` | Inside settle only | Implied by settle key + card | Progression | ≤1 tick | Friendly; duplicate settle |

---

## D. Source of truth

| Concern | Durable truth | Presentation | Must not decide alone |
|---------|---------------|--------------|------------------------|
| Match result | Match run / history / fixture | Stream embeds | Thread alone |
| Rewards | Ledger + XP rows keyed by run | Reward embed | Button retry |
| Lock | `match_locks` | “In match” UI | Client timer |
| Evo progress | Settlement pipe | Hub progress bar | Friendly log |

Cite parent SoT matrix (`specs/029-game-integrity/spec.md` §3).

---

## E. Outage & catch-up

| Failure | Behavior |
|---------|----------|
| Bot restart mid-stream | Recover run → settle once or abort; release lock |
| Discord 429/timeout on embed | Settlement kept; retry present |
| Render deploy mid-league fixture | No invented forfeit; `026` sporting rules + this child’s reward idempotency |
| DB timeout mid-settle | Fail closed / txn rollback; retry settle once |

---

## F. Implementation non-goals

- Second league calendar or forfeit table (`026`/`027` / US-42.5)
- Marketplace purchase races (US-42.6)
- Economy faucet/sink registry rewrite (US-42.7)
- New match simulation engine or tactics redesign
- New slash commands / integrity hubs
- Hard club delete / multi-club
- Changing card exclusive matrix beyond citing MatchLocked (031)

---

## G. Acceptance tests (integrity)

| Test | Expected |
|------|----------|
| Double settle same run | One coin/XP/evo effect |
| Present retry after settle | No second economy/XP |
| Lock during sim | Squad/dev Block |
| Lock cleared after complete | Mutations Allowed again |
| Friendly complete | Zero economy/XP/evo tick |
| Restart mid-stream | ≤1 settlement or clean abort |
| Stale Play after complete | No new rewards |

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 50 scripted double-settle trials for the same run key, durable reward applications = **1** each.
- **SC-002**: In 20 present-only retries after success, economy/XP deltas = **0**.
- **SC-003**: With MatchLocked, **100%** of sampled squad/dev/sale attempts Block until release.
- **SC-004**: Friendly completion suite shows **0** coin faucet rows, **0** match XP grants, **0** evo ticks.
- **SC-005**: Restart-recovery drills (streaming → restart) produce **≤1** settlement per run and **0** stuck locks after recovery.
- **SC-006**: A new engineer can explain “settle once / present many” and INV-10 from this spec in ≤15 minutes.

---

## Assumptions

- Existing `match_runs`, `match_locks`, `process_match_result`, and `apply_match_economy` patterns are the starting point; this child closes gaps rather than inventing a parallel match stack.
- US-42.2/42.3 already Block many mutations under MatchLocked; this child owns **acquire/release/settlement sequencing** and reward idempotency completeness.
- League assistant/forfeit sporting outcomes remain `026`.
- Soft Inactive/Abandoned clubs may still play bot matches (US-42.3); integrity here is still one settlement per run.

---

## Dependencies

| Depends on | Why |
|------------|-----|
| `specs/029-game-integrity` | Parent |
| `specs/030-identity-ownership` | Ownership |
| `specs/031-player-state-machine` | Card busy + MatchLocked matrix |
| `specs/032-club-state-machine` | Club overlay / join gates |
| `specs/026-league-lifecycle-rulebook` | Fixture sport only |

**Downstream**: US-42.5 (league integrity overlay), US-42.7 (economy registry cites match faucets), US-42.8 (job catch-up), US-42.9 (RPC template).
