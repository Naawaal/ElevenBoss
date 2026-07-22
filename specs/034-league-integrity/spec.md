# Feature Specification: League Integrity (US-42.5)

**Feature Branch**: `034-league-integrity`

**Created**: 2026-07-22

**Status**: Locked

**Parent epic**: `specs/029-game-integrity` (US-42)

**Child ID**: US-42.5 — League Integrity

**Depends on**: US-42.3 (`032`), US-42.4 (`033`); sporting + autonomy rulebooks `026` / `027`

**Overlays**: Club soft lifecycle & LeagueSeated (`032`); match settle-once / locks (`033`); economy prize faucet (US-25 / US-42.7 registry later)

**Input**: User description: "Continue next step — US-42.5 League Integrity after 42.1–42.4. Parent 029. Integrity overlay on 026/027: pause/resume, no-show/assistant, guild unreachable, prize once, catch-up idempotency, multi-guild seat. Non-goals: no second league calendar; no marketplace races; no faucet registry rewrite."

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Lifecycle transitions settle once under retry (Priority: P1) 🎯 MVP

When registration closes, a matchday deadline fires, fixtures resolve, prizes pay, or promotion applies, each **logical league operation** commits **at most once**. Bot restarts, scheduler double-wakes, and operator re-runs of the same overdue window produce the same terminal season state — never duplicate fixtures, standings mutations, or prize grants.

**Why this priority**: Epic SC-004 / INV family for prizes; `026` already mandates once-only — this child binds integrity acceptance and closes any remaining gap classes.

**Independent Test**: Freeze a season at a known “now”; run lifecycle evaluation N times without advancing time → zero duplicate prize/fixture/promotion rows; after advancing past a deadline once, second catch-up is a no-op.

**Acceptance Scenarios**:

1. **Given** a season with an overdue matchday deadline and bot recovery, **When** catch-up runs twice in a row, **Then** each due fixture settles at most once and standings reflect a single settlement.
2. **Given** end-of-season settlement already paid prizes, **When** lifecycle runs again at the same logical end, **Then** no second prize payment occurs.
3. **Given** promotion/relegation already applied for season S, **When** settlement is re-entered, **Then** division moves are not re-applied.

---

### User Story 2 — Infrastructure outage pauses; it does not invent forfeits (Priority: P1)

If the guild is unreachable, the bot is offline across deadlines, or Discord cannot present results, competitive state **pauses or catch-up-settles** per `026`. Infrastructure failure alone MUST NOT invent sporting forfeits for clubs that still have a legal team under assistant rules. Presentation may lag; durable fixture/season truth does not invent a 3–0 from downtime.

**Why this priority**: Epic E-05 / US-3 outage story; highest trust failure for league managers.

**Independent Test**: Simulate guild unreachable → season enters paused (or equivalent durable pause); no mass forfeit rows; on resume, unresolved windows rebase per `026`; catch-up does not double-pay.

**Acceptance Scenarios**:

1. **Given** the bot is removed or the guild is unreachable mid-season, **When** the outage is detected, **Then** the season pauses (or remains safely non-advancing) — fixtures are not bulk-forfeited solely because Discord is down.
2. **Given** a paused season, **When** wall-clock time passes, **Then** unresolved deadlines do not silently expire into forfeits; on resume, remaining play windows rebase forward by pause duration (`026`).
3. **Given** Discord cannot post commentary after a fixture already settled once, **When** presentation retries, **Then** sporting result and rewards stay as settled (no second settle).

---

### User Story 3 — Absence uses assistant / legal XI — not “who clicked” (Priority: P1)

Managers who miss a play window still get a fair result via saved/submitted lineup + assistant repair (`026`). No-show is **not** an automatic forfeit unless no legal team can be fielded after repair. Early Play is immersion only; deadline resolution remains authoritative for clubs that did not present.

**Why this priority**: Core async contract of `026`; integrity child ensures absence paths stay idempotent and do not race with human Play (US-42.4 locks).

**Independent Test**: Club A plays early (settle once); Club B misses deadline → assistant fields legal XI → one fixture result; illegal XI after repair → forfeit only for that club per `026`.

**Acceptance Scenarios**:

1. **Given** both clubs have legal plans and neither plays early, **When** deadline resolves, **Then** assistant/path resolves once with a normal settled result (not double-run).
2. **Given** one club already settled the fixture via Play, **When** deadline catch-up sees the fixture, **Then** it no-ops (already played).
3. **Given** a club cannot field any legal XI after assistant repair and the opponent can, **When** resolution runs, **Then** that club receives the sporting forfeit outcome defined in `026` — once.

---

### User Story 4 — Seats, leave-guild, and AI stay bounded (Priority: P2)

A human club holds at most one active seat per guild season rules (INV-12 / US-42.3). Leaving the Discord guild mid-season does **not** delete the club or wipe cards; the club remains assistant-controlled until season end per `026`. AI/bot clubs never consume human prize identity or promotion slots (INV-15). Soft Inactive/Abandoned affects **new** registration only — not mid-table destruction.

**Why this priority**: Epic E-07; multi-guild / leave-guild support class.

**Independent Test**: Leave guild mid-season → club + seat persist for sporting continuity; second register same season Block; AI never appears as human prize winner.

**Acceptance Scenarios**:

1. **Given** seated mid-season, **When** the owner leaves the guild, **Then** club inventory remains; fixtures continue under assistant rules (`026`); no hard withdraw+delete.
2. **Given** already seated in guild G season S, **When** they attempt a second join for S, **Then** Block / already-seated (idempotent).
3. **Given** end-of-season prizes, **When** AI clubs finish on the podium positions, **Then** human prize identity follows `026` (bots do not take human prize slots).

---

### User Story 5 — Managers see one coherent league story (Priority: P2)

Pause, resume, catch-up, and already-settled states surface as clear outcomes (ephemeral/hub/commentary as appropriate) — not raw failures or silent double announcements. Stale Play after fixture settled fails closed. No new integrity-only slash commands; `/league` remains the manager surface; ops pause remains non-Discord-exposed per `027`.

**Why this priority**: Trust and support load; aligns with US-42.4 present-retry pattern for league presentation.

**Independent Test**: Stale Play on settled fixture → clear already-played; catch-up after outage → at most one public result line per fixture where presentation is attempted.

**Acceptance Scenarios**:

1. **Given** fixture already settled, **When** manager presses Play, **Then** reject/no-op with already-played guidance — no new match run rewards.
2. **Given** season paused, **When** manager tries to play, **Then** Block with pause reason.
3. **Given** catch-up settles three overdue fixtures, **When** announcements run, **Then** each fixture is presented at most once for that settlement (retries allowed; duplicates of the durable result are not).

---

### Edge Cases

| ID | Scenario | Expected | Recovery |
|----|----------|----------|----------|
| E1 | Lifecycle wakes twice same overdue deadline | One settle per fixture / transition | Operation run key / already-played |
| E2 | Prize job after prizes paid | No second grant | Idempotent season settlement |
| E3 | Guild deletes bot mid-matchday | Pause; no mass forfeit | Resume / rebase (`026`) |
| E4 | Owner leaves guild mid-season | Club remains; assistant continues | Offseason inactivity per `026` |
| E5 | Human Play + deadline overlap | One fixture truth; US-42.4 locks | Active run → deadline skip |
| E6 | Pause 48h+ then resume | Windows rebase; no instant expire | `026` SC-007 class |
| E7 | Force-end / cancel season | Cancelled ≠ completed; prizes per `026` threshold rules | Ops path only |
| E8 | Soft Abandoned tries new registration | Block until Active (US-42.3) | Recover then register |
| E9 | AI on podium | No human prize identity to AI | INV-15 |
| E10 | Discord 429 after settle | Result kept; retry present | Presentation only |
| E11 | Two humans race Play on same fixture | One run wins; other Block | US-42.4 + fixture unique active run |
| E12 | Clock skew across hosts | Competitive “now” is server/UTC rulebook time | Single lifecycle evaluator |
| E13 | Incomplete XI at deadline | Assistant repair; forfeit only if zero legal | `026` FR-018 |
| E14 | Season `failed` / `cancelled` labeled completed | Forbidden | Status vocabulary (`026`) |

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: This child MUST treat `026` / `027` as the **sole sporting and autonomy rulebooks**; it MUST NOT redefine matchday counts, division size, promo slots, assistant priority order, or League Time config surfaces.
- **FR-002**: Every durable league lifecycle transition that mutates fixtures, standings, prizes, promotion, or season status MUST be **idempotent** under retry, double-wake, and catch-up (epic FR-002 / INV prize-once class).
- **FR-003**: End-of-season prizes MUST pay **at most once** per ruleset/season (align `026` FR-026); replays return prior success or no-op.
- **FR-004**: Promotion/relegation application MUST be **at most once** per completed season settlement.
- **FR-005**: Fixture resolution (human Play or deadline/assistant) MUST produce **at most one** durable sporting result per fixture; already-played fixtures MUST be skipped by catch-up.
- **FR-006**: Infrastructure outage (bot offline, guild unreachable, Discord unavailable) MUST **pause or catch-up-settle** — MUST NOT invent sporting forfeits solely from outage (epic E-05).
- **FR-007**: Paused seasons MUST rebase unresolved windows on resume per `026` (no instant mass expiry into forfeits).
- **FR-008**: Absence / no-show MUST use assistant + legal XI rules from `026`; forfeit only when no legal team remains after repair.
- **FR-009**: Human Play and deadline resolution MUST not double-settle the same fixture (coordinate with US-42.4 match-run uniqueness and locks).
- **FR-010**: A club MUST have at most one active guild-season seat per INV-12 / US-42.3; re-register is idempotent already-seated.
- **FR-011**: Leaving the guild mid-season MUST NOT delete the club or cards; sporting continuity follows `026` assistant path.
- **FR-012**: AI/bot clubs MUST NOT receive human-only prizes or consume human promotion identity (INV-15).
- **FR-013**: Soft Inactive/Abandoned MUST Block **new** season registration until Active (US-42.3); MUST NOT wipe mid-season tables.
- **FR-014**: Presentation failures after durable fixture/season settlement MUST retry display only — never re-enter prize or fixture settlement.
- **FR-015**: Stale Play / interactions after settled or paused states MUST fail closed with clear reasons.
- **FR-016**: No new slash commands or integrity hubs; manager surface remains `/league`; Discord admin league controls remain League Time only (`027`).
- **FR-017**: Prize and league economy movements MUST use the existing economy pipe family — no parallel coin writers (US-25; registry detail US-42.7).
- **FR-018**: Match XP / evo ticks for league fixtures remain under US-42.4 settle-once / INV-10 — this child does not add a second tick path.
- **FR-019**: Player-facing behavior managers notice MUST update `change_log.md` when shipped.
- **FR-020**: This feature MUST NOT rewrite marketplace races (US-42.6) or the global job-catalog standard (US-42.8) beyond league-specific catch-up binding.

### Key Entities

- **LeagueSeason**: Durable season with status vocabulary from `026` (including paused / completed / cancelled / failed).
- **LifecycleTransition**: Idempotent operation (close registration, resolve matchday, settle season, etc.) with a logical run key.
- **FixtureResult**: Single sporting truth per fixture (played / forfeit per `026`).
- **AssistantResolution**: Deadline path that fields legal XI or forfeits only when illegal.
- **SeasonPause**: Durable pause overlay for unreachable/outage/ops; rebases windows on resume.
- **PrizeSettlement**: Once-only end-of-season (or threshold) payout keyed by season.
- **LeagueSeat**: Club×guild×season registration overlay (US-42.3).

---

## A. Epic invariant touch list

| INV | Role in US-42.5 |
|-----|-----------------|
| **INV-02** | Bound — seats/ownership use current club owners |
| **INV-04/05** | Bound — prizes via economy pipe |
| **INV-09** | Bound — fixture settle once (with US-42.4) |
| **INV-10** | Bound — no second evo tick path |
| **INV-12** | Primary — one active seat per season rules |
| **INV-15** | Primary — AI never takes human prize/promo identity |
| **INV-17** | Bound — MatchLocked during live Play (US-42.4) |
| **INV-18** | Bound — caps still server-side where league grants apply |

Does not weaken epic INVs. Does not fork `026` sporting rules.

---

## B. Integrity overlay (not a second calendar)

### B.1 Ownership split

| Concern | Owner |
|---------|--------|
| Matchdays, windows, assistant priority, forfeit scoreline, promo slots, bot fill | **`026`** |
| League Time timezone / resolution hour; no Discord pause UI | **`027`** |
| Soft Active/Inactive/Abandoned → new registration gate | **US-42.3** |
| Match run settle-once, dual locks, present-retry | **US-42.4** |
| Pause/unreachable behavior binding, prize/transition idempotency acceptance, leave-guild continuity, AI prize bound | **US-42.5 (this child)** |

### B.2 Season integrity states (informative names)

Logical overlays this child cares about:

| Overlay | Meaning |
|---------|---------|
| **Running** | Active matchday cycle advancing under rulebook time |
| **Paused** | Deadlines not consuming unresolved windows; no outage-forfeits |
| **CatchingUp** | Processing overdue transitions in order, each once |
| **SettlingSeason** | Prizes + promo once |
| **Terminal** | completed / cancelled / failed — no further sporting grants |

Mapping onto concrete `league_seasons.status` values is an implementation concern; guarantees above are normative.

### B.3 Absence vs outage

| Event | Sporting outcome source | Integrity rule |
|-------|-------------------------|----------------|
| Manager no-show at deadline | Assistant / forfeit-if-illegal (`026`) | Resolve once |
| Guild/bot unreachable | Pause (`026`/`027`) | No invented forfeit |
| Discord present fail after settle | — | Present-retry only |

---

## C. Logical actions & idempotency

| Action | Actor | Idempotency pattern | Success | Reject / no-op |
|--------|-------|---------------------|---------|----------------|
| `register_season` | Manager | season×club unique seat | Seated | Already seated; soft Inactive; `026` gates |
| `play_fixture` | Manager | fixture active run / already played | One result | Locked; paused; already played |
| `resolve_deadline_fixture` | System | fixture id + terminal | One result | Already played |
| `advance_matchday` | System | season×matchday key | Advance once | Incomplete fixtures; already advanced |
| `pause_season` | System/ops | season id | Paused | Already paused |
| `resume_season` | System/ops | season id | Running; windows rebased | Not paused |
| `settle_season_prizes` | System | season id / settlement key | Prizes once | Already settled |
| `apply_promotion` | System | season id | Once | Already applied |
| `present_fixture` | System | presentation retry | Announce | Discord errors |

---

## D. Source of truth

| Concern | Durable truth | Presentation | Must not decide alone |
|---------|---------------|--------------|------------------------|
| Fixture score / played | Fixture + match run / history | Commentary / journal | Thread alone |
| Season phase | Season status + phase deadlines | Hub embeds | Client clock |
| Prizes | Economy ledger keyed by season settlement | Announcement | Button spam |
| Seat | Registration / membership rows | `/league` UI | Leave-guild client event alone |
| Pause | Season paused + rebase metadata | “Season paused” copy | Missing Discord channel alone without durable pause |

Cite parent SoT matrix (`specs/029-game-integrity/spec.md` §3).

---

## E. Outage & catch-up

| Failure | Behavior |
|---------|----------|
| Bot offline across deadline(s) | On recovery, process overdue transitions **in order**, each once (`026` catch-up) |
| Guild unreachable / bot removed | Pause; no mass forfeit; resume when reachable |
| Discord 429 on announce | Durable settle kept; retry present |
| Double scheduler wake | Second wake no-ops committed operations |
| Deploy mid-Play | US-42.4 run recovery + this child’s already-played skip |
| Force-end | Cancelled path; prizes only per `026` published threshold rules |

---

## F. Implementation non-goals

- Second league calendar, alternate matchday counts, or new forfeit scorelines
- Rewriting assistant priority or bot-fill sport rules (`026`)
- Restoring Discord admin pause/resume/force-end menus (`027` removed them)
- Marketplace purchase races (US-42.6)
- Global economy faucet/sink registry (US-42.7) or full job catalog (US-42.8)
- New slash commands / integrity hubs
- Hard club delete / multi-club
- Changing card exclusive matrix (031) beyond citing MatchLocked during Play

---

## G. Acceptance tests (integrity)

| Test | Expected |
|------|----------|
| Catch-up twice after one overdue deadline | One fixture settle; second no-op |
| Prize settlement twice | One payout set |
| Guild unreachable mid-season | Pause; zero outage-only forfeits |
| Resume after ≥48h pause | Windows rebased; no instant mass expiry |
| Leave guild mid-season | Club persists; fixtures continue under assistant |
| Play then deadline | Deadline skips already-played |
| Stale Play after settled | Reject; no new rewards |
| AI podium | No human prize identity to AI |
| Soft Abandoned register | Block until Active |

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 50 scripted double catch-up trials against an unchanged “now”, duplicate fixture settlements = **0** and duplicate prize rows = **0**.
- **SC-002**: Simulated guild-unreachable outage produces **0** infrastructure-only forfeit rows; season is paused (or equivalently non-advancing) until resume.
- **SC-003**: After pause ≥48h and resume, unresolved fixtures do **not** all instantly expire; remaining windows match rebase rules (`026` class).
- **SC-004**: Leave-guild mid-season drills show club + cards retained and season table intact (assistant continuity).
- **SC-005**: Already-played + deadline overlap suite shows **≤1** durable result per fixture.
- **SC-006**: A new engineer can explain “`026` owns sport; 42.5 owns once/pause/seat integrity” from this spec in ≤15 minutes.

---

## Assumptions

- `026` / `027` remain Locked sporting/autonomy sources; this child closes integrity gaps and acceptance binding, not a redesign.
- US-42.3 already gates soft Inactive/Abandoned for **new** registration and defines LeagueSeated as overlay.
- US-42.4 already owns match-run settle-once, dual human locks, and present-retry for league Play paths.
- Prize coin amounts stay configurable; this child freezes **once-only** and pipe usage, not every percentage.
- Global scheduler job-catalog standardization is US-42.8; league catch-up behavior here must remain compatible.
- Exhaustive exploit catalog remains US-42.10.

---

## Dependencies

| Depends on | Why |
|------------|-----|
| `specs/029-game-integrity` | Parent constitution |
| `specs/026-league-lifecycle-rulebook` | Sporting rules |
| `specs/027-league-autonomous-admin` | Autonomy / League Time; no Discord pause UI |
| `specs/032-club-state-machine` | Soft lifecycle + seat gates |
| `specs/033-match-integrity` | Play settle-once / locks / present-retry |
| `specs/030-identity-ownership` | Leave-guild club persistence |

**Downstream**: US-42.7 (prize faucet registry), US-42.8 (job run keys), US-42.9 (RPC guarantees), US-42.10 (edge catalog fill).
