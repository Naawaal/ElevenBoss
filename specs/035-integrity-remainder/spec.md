# Feature Specification: Game Integrity Remainder (US-42.6–42.10)

**Feature Branch**: `035-integrity-remainder`

**Created**: 2026-07-22

**Status**: Locked

**Parent epic**: `specs/029-game-integrity` (US-42)

**Child IDs (consolidated)**: US-42.6 Marketplace · US-42.7 Economy · US-42.8 Scheduler · US-42.9 Database/RPC · US-42.10 Security & Edges

**Depends on**: Locked US-42.1–42.5 (`030`–`034`); domain specs `017` (marketplace), US-25 (economy), `026`/`027` (league jobs already overlaid)

**Input**: User description: "Create one Speckit spec for all remaining US-42 tasks: marketplace integrity, economy faucet/sink registry, scheduler job catalog, database/RPC guarantees, security anti-abuse & edge catalog (US-42.6–42.10). Parent 029. Do not reopen Locked 42.1–42.5. Non-goals: no new gameplay hubs; no second economy/XP pipes; no second league calendar."

**Consolidation note**: Epic §0.3 preferred separate children. This feature **intentionally merges** remaining children into one Speckit package for delivery efficiency, with **workstreams W6–W10** that preserve each child’s obligations and INV ownership. Plan/tasks MAY still ship in waves without splitting folders.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Marketplace list/buy/expire stays fair (US-42.6) (Priority: P1) 🎯 MVP-A

Managers list and buy players on `/marketplace` without double-sale, self-buy, listed-while-busy exploits, or silent price changes. Exactly one buyer wins a race; losers keep their coins; tax sinks; min hold / floors from `017` remain enforced server-side (INV-13).

**Why this priority**: Highest remaining economy-theft surface after match/league integrity.

**Independent Test**: Concurrent two-buyer purchase → one success, one unchanged balance; list while MatchLocked/Hospital/Evolving/Academy → Block (US-42.2); expiry/cancel terminal once.

**Acceptance Scenarios**:

1. **Given** an active listing, **When** two buyers confirm purchase at the same time, **Then** exactly one receives the card and is debited; the other is unchanged and sees unavailable.
2. **Given** seller’s own listing, **When** they try to buy it, **Then** Block.
3. **Given** a card Listed, **When** seller tries drill / XI include / start match with it, **Then** Block until cancel/expire/sold (US-42.2).
4. **Given** listing past expiry, **When** expiry job runs (possibly twice), **Then** listing becomes Expired once; card returns to seller once.
5. **Given** buyer has insufficient coins or fails tax/floor checks, **When** they attempt buy, **Then** no card move and no partial debit.

---

### User Story 2 — Every faucet and sink is registered and ledgered (US-42.7) (Priority: P0) 🎯 MVP-B

Engineering and ops can open a **living Economy Source/Sink Registry** that lists every coin/energy/gem (if any) movement, its idempotency key pattern, owning feature, and pipeline (`apply_club_economy` family). New features cannot ship a parallel coin writer. Friendly remains non-faucet. Inflation signals are defined enough to query without Discord.

**Why this priority**: Epic P0; stops silent second economies after 42.1–42.5 closed identity/match holes.

**Independent Test**: Grep/audit: zero direct `players.coins` updates outside pipe; registry covers match, store, wages, transfer tax, prizes, packs, drills/fusion sinks, etc.; missing registry entry fails review checklist.

**Acceptance Scenarios**:

1. **Given** the registry, **When** a reviewer lists all known faucets/sinks from Locked features, **Then** each has a named entry + key pattern + owner.
2. **Given** a replay of any registered grant with the same key, **When** mutation re-runs, **Then** at most one durable ledger effect (INV-08).
3. **Given** friendly match complete, **When** economy is inspected, **Then** no competitive coin faucet row (INV-11).
4. **Given** Top.gg / external entitlement degraded, **When** claim is attempted, **Then** fail closed — no invent grant (P7).

---

### User Story 3 — Background jobs catch up without double pay (US-42.8) (Priority: P1)

Daily recovery, payroll, listing expiry, league lifecycle wakes, vote entitlement sweeps, and similar jobs use a **job catalog + run-key** standard: missed fires catch up safely; double wakes no-op; competitive rules stay in RPCs/rulebooks, not cron expressions.

**Why this priority**: Render restarts are routine; duplicate interval jobs are a known class.

**Independent Test**: Catalog lists each job with schedule intent, run key, catch-up rule; double invoke same key → one durable effect; league jobs remain compatible with US-42.5 `_run_once`.

**Acceptance Scenarios**:

1. **Given** bot offline across a daily job window, **When** it recovers, **Then** catch-up runs once per due logical day/key — not N times for N missed ticks unless catalog explicitly batches with unique sub-keys.
2. **Given** two workers wake the same job key, **When** both finish, **Then** ≤1 durable mutation for that key.
3. **Given** league deadline job, **When** catalog is read, **Then** it points at lifecycle engine / `026` — not a divergent prize cron.

---

### User Story 4 — Mutating RPCs prove schema and atomicity (US-42.9) (Priority: P0)

Every new/changed mutating RPC follows a **guarantee checklist**: columns exist only via migrations; schema guards updated; RLS when Data API exposed; no app-level multi-step money/ownership loops; fail closed if schema incomplete (INV-16).

**Why this priority**: Epic P0; half-migrated production is worse than downtime.

**Independent Test**: Publish RPC template + constraint checklist; sample audit of economy/marketplace/match RPCs against checklist; verify_required_schema covers bot-required objects for this remainder’s additions.

**Acceptance Scenarios**:

1. **Given** a proposed column used in bot/RPC code, **When** no migration defines it, **Then** review fails (INV-16 class).
2. **Given** a new bot-required table via Data API, **When** shipped, **Then** RLS + policies exist in the same migration wave.
3. **Given** complex purchase/settle, **When** implemented, **Then** it is an RPC (or documented equivalent atomic unit) — not a Python loop of partial updates.

---

### User Story 5 — Soft anti-abuse and exhaustive edges (US-42.10) (Priority: P1)

A threat model and **edge-case catalog** cover identity, match, league, marketplace, economy, scheduler, Discord UX, and external deps. Soft economic guards (floors, holds, caps, owner checks) are in scope; accusation-based hard bans are out. Stale interactions fail closed. Minimum integrity analytics signals are named.

**Why this priority**: Completes epic §8 index; reduces support-class unknowns.

**Independent Test**: Catalog has Expected / Reasoning / Recovery for each epic §8 category relevant to remaining domains; stale custom_id → safe reject.

**Acceptance Scenarios**:

1. **Given** stale marketplace/store button after restart, **When** pressed, **Then** reject with re-open guidance — no mutation.
2. **Given** alt-friendly flip attempt within min hold, **When** re-list/buy path runs, **Then** Block per `017` / registry.
3. **Given** the edge catalog, **When** an engineer picks category “scheduler miss”, **Then** they find a documented recovery pointing at US-42.8.

---

### Edge Cases *(remainder-focused; full matrix in workstream W10)*

| ID | Domain | Scenario | Expected |
|----|--------|----------|----------|
| E1 | Market | Two buyers race | One win; loser unchanged |
| E2 | Market | Buy own listing | Block |
| E3 | Market | Expiry job twice | One return to seller |
| E4 | Market | List while MatchLocked | Block |
| E5 | Economy | Direct coins UPDATE in cog | Forbidden / grep fail |
| E6 | Economy | Replay claim same key | No second grant |
| E7 | Economy | Top.gg 5xx on vote pack | Fail closed |
| E8 | Jobs | Double APScheduler wake | One run key success |
| E9 | Jobs | Offline across payroll day | Catch-up once |
| E10 | DB | Ship RPC using undeclared column | Guard/review fail |
| E11 | DB | Table without RLS on Data API | Forbidden |
| E12 | Security | Stale custom_id | Reject |
| E13 | Security | Webhook replay | Idempotent consume |
| E14 | UX | Empty select / timeout | Safe no-op |
| E15 | Cross | Transfer then claim pending XP | Current owner (INV-14) |

---

## Requirements *(mandatory)*

### Functional Requirements — Cross-cutting

- **FR-001**: This feature MUST NOT reopen or contradict Locked US-42.1–42.5 behavior; it extends registries, checklists, and remaining domains only.
- **FR-002**: No new slash commands or integrity-only hubs; extend `/marketplace`, `/store`, `/development`, `/league` as already designed.
- **FR-003**: Single coin pipe (`apply_club_economy` family) and single XP pipe (`apply_card_xp` family) remain mandatory (INV-05/06).
- **FR-004**: Presentation failures after durable success MUST retry display only (P8).
- **FR-005**: Player-facing changes managers notice MUST update `change_log.md` when shipped.
- **FR-006**: Implementation MAY proceed in workstream waves W6→W10 (or W7 parallel to W6); Lock of this feature requires all workstreams Done or explicitly deferred with epic amendment.

### Functional Requirements — US-42.6 Marketplace

- **FR-M01**: Listing states MUST include at least Active, Cancelled, Expired, Sold with clear entry/exit (`017` + epic §5.4).
- **FR-M02**: Purchase MUST be atomic: exactly one winner (INV-13); tax sink mandatory; own-listing buy forbidden.
- **FR-M03**: Price floors / min hold / listing caps from `017` MUST remain server-enforced (INV-18 class).
- **FR-M04**: List/buy MUST respect US-42.2 card busy matrix and INV-17 MatchLocked.
- **FR-M05**: Expiry and cancel MUST be idempotent under job retry.
- **FR-M06**: Agent sale and scouting remain separate paths but MUST NOT bypass card busy or economy pipe rules.

### Functional Requirements — US-42.7 Economy

- **FR-E01**: Maintain a living **Source/Sink Registry** (doc artifact under this feature’s contracts) covering all coin/energy/gem mutations.
- **FR-E02**: Each registry entry MUST name: source/sink id, direction, pipeline, idempotency key pattern, owning feature/spec, notes.
- **FR-E03**: New faucets/sinks MUST register before enablement (epic FR-011).
- **FR-E04**: Friendly MUST NOT be a coin faucet (INV-11).
- **FR-E05**: Define minimum inflation/observability signals (e.g. faucet velocity, duplicate-key hit count, ledger anomaly) queryable without Discord.
- **FR-E06**: Gems (if mutated) MUST be ledgered with the same idempotency discipline as coins when in scope.
- **FR-E07**: Progression-adjacent sinks/faucets (fusion coins, drill costs, mentor does not move coins) MUST appear in registry or explicit “N/A coins” rows.

### Functional Requirements — US-42.8 Scheduler

- **FR-J01**: Publish a **Job Catalog** listing each recurring/background job: name, purpose, schedule intent, run-key pattern, catch-up rule, owning module.
- **FR-J02**: Jobs MUST be catch-up safe and idempotent under double wake (INV-08 class).
- **FR-J03**: Competitive outcomes MUST NOT be invented solely by cron timing — defer to `026` / RPCs / prior children.
- **FR-J04**: League lifecycle jobs MUST remain compatible with US-42.5 operation keys.
- **FR-J05**: Clock/timezone handling MUST document UTC vs guild League Time where relevant (`027`).

### Functional Requirements — US-42.9 Database / RPC

- **FR-D01**: Publish an **RPC Guarantee Template** + **Constraint Checklist** used in review.
- **FR-D02**: No column/table without numbered migration; extend `verify_required_schema.sql` for bot-required objects (INV-16).
- **FR-D03**: Bot-required Data API tables MUST ship RLS + policies in the same wave.
- **FR-D04**: Complex multi-row money/ownership mutations MUST be RPC/atomic — forbid unsafe Python multi-step loops.
- **FR-D05**: Replacing RPC signatures MUST drop old overloads deliberately; diff prior migrations.
- **FR-D06**: Contract versioning note: breaking RPC changes require migration + caller grep (wiring check).

### Functional Requirements — US-42.10 Security & Edges

- **FR-S01**: Publish a soft **Threat Model** (assets, actors, abuse cases) — hard bans out of scope unless product asks later.
- **FR-S02**: Fill epic §8 edge categories for remaining domains with Expected / Reasoning / Recovery.
- **FR-S03**: Stale Discord interactions MUST fail closed with re-open guidance.
- **FR-S04**: Soft anti-abuse: floors, holds, caps, owner checks, rate-limit resilience — not accusation pipelines.
- **FR-S05**: Name minimum integrity analytics signals (may start as structured logs + SQL).
- **FR-S06**: External webhook/entitlement replay MUST be idempotent / fail closed.

### Key Entities

- **Listing**: Marketplace sell offer with terminal states Active|Cancelled|Expired|Sold.
- **PurchaseAttempt**: Idempotent buy intent; at most one success per listing.
- **RegistryEntry**: Named faucet or sink with key pattern and owner.
- **JobDefinition**: Catalogued background work unit with run key.
- **JobRun**: One execution instance of a JobDefinition.
- **RpcContract**: Documented mutating procedure with checklist proof.
- **ThreatCase / EdgeCase**: Catalog row with recovery.
- **IntegritySignal**: Countable event (duplicate key, race loss, catch-up volume, faucet velocity).

---

## Workstreams (delivery map)

| Wave | Child | Primary deliverables | Exit |
|------|-------|----------------------|------|
| **W6** | 42.6 | Market state/race audit + gap fixes; purchase atomicity tests | INV-13 locked |
| **W7** | 42.7 | Economy registry + pipe grep guards + signals doc | Registry complete for known features |
| **W8** | 42.8 | Job catalog + run-key standard + catch-up notes | Catalog + double-wake tests |
| **W9** | 42.9 | RPC template + constraint checklist + guard extensions as needed | Checklist used on W6–W8 diffs |
| **W10** | 42.10 | Threat model + edge catalog + stale UX rules + signals | Epic §8 remainder filled |

**Suggested implement order**: W7 (P0 registry) ∥ W6 (market) → W8 → W9 (formalize what waves already obeyed) → W10. W9 checklist may be drafted early and enforced continuously.

---

## A. Epic invariant touch list

| INV | Primary workstream |
|-----|-------------------|
| INV-04/05/08/11/18 | W7 |
| INV-13/14 | W6 (14 bound) |
| INV-03/17 | W6 bound to 42.2 |
| INV-16 | W9 |
| INV-08 (jobs) | W8 |
| Soft abuse / UX | W10 |

---

## B. Marketplace lifecycle (normative names)

| State | Meaning |
|-------|---------|
| **Active** | Purchasable |
| **Cancelled** | Seller cancelled; card returned |
| **Expired** | Job expired; card returned |
| **Sold** | Buyer owns card; seller paid net of tax |

Buy-it-now only. No bidding in this remainder.

---

## C. Logical actions & idempotency (remainder)

| Action | Key pattern (logical) | Workstream |
|--------|----------------------|------------|
| `list_card` | listing id / card id active unique | W6 |
| `buy_listing` | listing id purchase | W6 |
| `expire_listing` | listing id expire | W6/W8 |
| `claim_store_faucet` | existing store keys | W7 |
| `apply_club_economy` | per-call idempotency key | W7 |
| `job_run` | job_name + period key | W8 |
| `pause/resume` league | already US-42.5 | — |

---

## D. Source of truth

| Concern | Durable truth | Must not decide alone |
|---------|---------------|------------------------|
| Listing | DB listing row | Stale board embed |
| Coins | Ledger + club balance | Hub number alone |
| Job success | Job run / operation key | Scheduler memory |
| Schema | Migrations + guards | App assumptions |

---

## E. Outage & catch-up

| Failure | Behavior |
|---------|----------|
| Bot restart mid-purchase | RPC atomicity; retry safe |
| Missed expiry job | Catch-up expires due listings once |
| Top.gg down | Fail closed on vote entitlements |
| Migration mid-flight | Fail closed if guards incomplete |

---

## F. Implementation non-goals

- Reopening Locked US-42.1–42.5 designs except citation
- Second league calendar or Discord admin pause UI
- Hard account bans / KYC / real-money policy
- New gameplay loops, gacha redesign, tactics engine
- Multi-club accounts
- Full observability dashboards (signals + queries enough)
- Splitting this folder back into five Speckit features (optional later; not required)

---

## G. Acceptance tests (integrity remainder)

| Test | Expected |
|------|----------|
| Two-buyer race | One win |
| Buy own listing | Block |
| Expiry twice | One terminal |
| Registry completeness vs known faucets | 100% mapped |
| Grep direct coins UPDATE in cogs | Zero (or allowlisted none) |
| Job double wake | ≤1 mutation |
| Undeclared column in bot | Fail review/guard |
| Stale button | Reject |
| Friendly complete | No coin faucet |

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In ≥50 concurrent purchase trials on the same listing, winners = **1** and loser balances unchanged = **100%**.
- **SC-002**: Economy registry covers **100%** of known coin/energy mutations from Locked features at time of Lock (spot-check ≥20 entries).
- **SC-003**: Job catalog lists **100%** of recurring bot jobs found by code search at Lock; each has a run-key pattern.
- **SC-004**: RPC/constraint checklist is applied to every migration introduced by this feature (0 unguarded bot-required objects).
- **SC-005**: Edge catalog covers all epic §8 categories that apply to W6–W10 domains (≥1 row each).
- **SC-006**: A new engineer can navigate “market race / registry / job key / RPC checklist / threat model” from this one spec in ≤30 minutes.

---

## Assumptions

- Locked children 42.1–42.5 remain source of truth for identity, card/club state, match, league overlays.
- `017` remains sporting/product marketplace design; this feature is integrity overlay + gap closure.
- US-25 economy pipe remains singular; this feature adds registry and audit, not a rewrite.
- Soft anti-abuse is sufficient for v1; hard bans are a separate product decision.
- Consolidating 42.6–42.10 into one Speckit feature is an explicit process exception to epic §0.3 separate-folder preference.

---

## Dependencies

| Depends on | Why |
|------------|-----|
| `specs/029-game-integrity` | Parent constitution |
| `specs/030`–`034` | Locked prior children |
| `specs/017-player-transfer-market` | Marketplace product rules |
| US-25 / economy migrations | Coin pipe |
| `026`/`027` | Job compatibility for league |

**Downstream**: Parent epic Lock / SC updates; optional future split of workstreams into separate folders if desired.
