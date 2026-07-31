# Feature Specification: Performance, Cleanup & Scalability Hardening

**Feature Branch**: `050-performance-cleanup-scaling`

**Created**: 2026-07-31

**Status**: Draft

**Parent / Related**:
- `specs/038-db-scalability-performance` (US-43) — architecture constitution for scale, caching, idempotency, monitoring
- `specs/039-hub-hot-path-wave2` (US-44) / `specs/040-hub-hot-path-wave3` (US-45) — prior hub round-trip waves
- `specs/029-game-integrity` (US-42) — must not invent parallel XP/economy pipes or weaken mutation integrity
- `specs/044-match-v3-rollout` — Match Engine V3 soak / V2 retirement sequencing

**Input**: User description: "ElevenBoss — Performance, Cleanup & Scalability Hardening Roadmap: lower DB/API load and command latency while simplifying the codebase and preparing for horizontal scaling; extend existing singleton client, config cache, perf signals, and job-claim patterns; Phase 0 baseline; delete dead training packages; fix energy install; remove Alembic runtime deps; wire Sentry; hot-path leaderboard/market/development RPCs; cache abstraction; indexes from measured queries; feature-flag maturity; durable outbox; no Redis/Kafka/Celery yet."

---

## 0. Epic Framing

### 0.1 Purpose

US-46 (working ID) is the **operational hardening epic** that turns existing scale foundations into measurable wins: fewer wasted reads on hot hubs, a cleaner dependency and package surface, honest observability, and a staged path toward multi-instance bots — without new player-facing gameplay.

Managers should feel hubs and common actions respond faster and more reliably as the club count grows. Operators should see latency, errors, and cache effectiveness, and know when infrastructure upgrades (not more code) are required.

### 0.2 Target interaction shape

Move typical interactive work toward:

1. Optional disposable cache lookup for slow-changing display data  
2. One purpose-built read of hub/page state when needed  
3. One atomic mutation when state changes  
4. Discord response  

Move expensive non-interactive work toward durable claimed jobs woken by the scheduler — not fire-and-forget in-memory tasks alone.

### 0.3 Principles (frozen)

| Principle | Meaning |
|-----------|---------|
| Postgres is source of truth | Cache is disposable; mutations re-check authority in the database |
| Mutations stay atomic | Same economy/XP/ownership pipes as US-42 / US-23 / US-25 |
| Bot processes stay effectively stateless for business truth | No critical session-only balance/lock authority |
| Jobs are idempotent / claimable | Safe under restart and (later) multi-instance |
| Extend, do not replace foundations | Singleton hosted async client, HTTP pooling, config TTL cache, perf signals, APScheduler, existing job-claim patterns |

### 0.4 Relationship to prior performance specs

| Spec | Role vs this epic |
|------|-------------------|
| `038` | Constitution & phase gates — still authoritative for capacity premises and multi-instance rules |
| `039` / `040` | Earlier hub waves — this epic continues unfinished hot paths (notably division leaderboard full-load and marketplace browse filter-in-app) and adds cleanup / observability / flag maturity |
| `044` | Owns Match V3 product soak — this epic schedules V2 retirement **after** soak, never in the same deploy as major hot-path rewrites |

### 0.5 Non-goals

- New slash commands, hubs, or gameplay loops for “performance UI”
- Raising HTTP connection pools as a first lever (do query reduction first)
- Introducing Redis, Kafka, RabbitMQ, Celery, microservices, a separate REST backend, or ORM schema tools in this epic’s early phases
- Deleting Match Engine V2 before controlled soak and recoverable-run drain
- Caching authoritative mutation checks (coins, energy, ownership, locks, SP, listing ownership)
- Folding `packages/energy` into another package in the first sprint (install-fix only; consolidation optional later)
- Closing remaining rarity-potential manager notification ops inside this epic (tracked separately under `049`)

### 0.6 Delivery model

One parent spec with phased waves. Concrete migrations, RPC names, indexes, and module layouts are owned by `/speckit.plan` and `/speckit.tasks`. Prefer **additive** read RPCs and dual-read compatibility so a previous bot build can roll back without a destructive schema break.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Operators can see whether hubs are fast or slow (Priority: P1)

As an operator/owner, I can review per-command and per-hub latency and load signals (including percentiles and data round-trip pressure) over a baseline window before and after changes, without guessing which surface to optimize next.

**Why this priority**: Measurement is the gate for every later wave; without it, “improvements” cannot be proven.

**Independent Test**: Capture a 24–72 hour baseline for named hubs; confirm the same signals remain available after cleanup-only changes; verify owner-only admin performance view (or equivalent operator surface) exposes the agreed metrics.

**Acceptance Scenarios**:

1. **Given** production traffic for at least one full day, **When** an operator reviews performance signals, **Then** each tracked command/hub shows request volume, p50/p95 (and p99 where available), round-trip pressure, cache hit/miss, and error/throttle classes.
2. **Given** a proposed optimization, **When** it ships, **Then** the same metrics can show before/after comparison for that hub.
3. **Given** metrics aggregation, **When** flushed for retention, **Then** monitoring does not write one durable row per individual command invocation.

---

### User Story 2 — Dead code and broken installs no longer confuse the platform (Priority: P1)

As an engineer onboarding or deploying the bot, unused legacy training packages are gone, the energy package installs deterministically with the rest of the monorepo, and obsolete schema-migration runtime libraries are not shipped as production bot dependencies.

**Why this priority**: Low risk, immediate clarity; reduces accidental imports and shrinks the production dependency surface.

**Independent Test**: Fresh install from documented requirements files succeeds; repository search shows no application imports of removed packages; production dependency set excludes confirmed-unused Alembic/ORM stack after import verification.

**Acceptance Scenarios**:

1. **Given** a clean environment, **When** production bot dependencies are installed, **Then** `energy` is available as an editable local package alongside the other game packages.
2. **Given** the repository after cleanup, **When** searching for the deleted training packages, **Then** only history/docs remain — no live application imports.
3. **Given** production bot dependency files, **When** reviewed, **Then** Alembic/SQLAlchemy/Mako/greenlet are absent from runtime if verification found no required imports; direct database tooling lives in an ops/dev dependency set when still needed.

---

### User Story 3 — Division and global leaderboards stay correct without loading entire divisions (Priority: P1)

As a manager, when I open the Division or Global leaderboard, I see a correct page of standings, my rank, and promotion/relegation (or global rank) context — even when the division has thousands of managers — without waiting for a full-table download into the bot.

**Why this priority**: Full-division fetch is the clearest current hot path and becomes worse linearly with growth.

**Independent Test**: With a large synthetic or staging division, open leaderboard pages; assert returned page size matches the UI page size; viewer rank and cutoffs remain correct across page moves.

**Acceptance Scenarios**:

1. **Given** a division larger than one page, **When** a manager opens the Division leaderboard, **Then** only the displayed page of rows is transferred for rendering (not the entire division roster).
2. **Given** the same manager, **When** they navigate pages via stable cursors, **Then** ordering remains stable for ties and their personal rank remains accurate.
3. **Given** Global LP leaderboard, **When** opened, **Then** paging uses a stable tie-breaker (score then identity), not score alone.

---

### User Story 4 — Transfer Board results reflect the whole market, filtered server-side (Priority: P1)

As a manager browsing the Transfer Board with filters (position, OVR, age, potential, sort), I see a page of listings that truly match those filters across the active market — not only whatever happened to be in a small first fetch.

**Why this priority**: Fetch-then-filter-in-app is both slow at scale and logically incomplete.

**Independent Test**: Seed many listings outside the old “first N” window that match a filter; confirm they appear when browsing with that filter; page size equals the UI page.

**Acceptance Scenarios**:

1. **Given** filters that match listings beyond the former small prefetch window, **When** the manager browses, **Then** matching listings are discoverable via server-side filter/sort/page.
2. **Given** a sort mode (newest, price, etc.), **When** paging, **Then** keyset/cursor pagination is used — not growing OFFSET scans on the listing table.
3. **Given** sell eligibility and marketplace hub entry, **When** those screens open, **Then** eligibility and hub summary arrive from consolidated reads (not multi-request fanout for the same screen).

---

### User Story 5 — Development hub feels like one coherent load (Priority: P2)

As a manager opening `/development` (and common subflows such as skills or mentor targeting), I get a complete hub/submenu without long sequential “loading pieces of state” delays, while claim/create mutations remain separate from pure reads.

**Why this priority**: High-frequency progression surface; prior waves improved drills, but main hub and skills/mentor still over-fetch.

**Independent Test**: Measure round trips and latency for development hub and skills/mentor entry before/after; confirm UI parity and that read paths do not silently perform non-idempotent creates.

**Acceptance Scenarios**:

1. **Given** a registered manager, **When** they open `/development`, **Then** hub display state is obtained via a consolidated read-state path.
2. **Given** skills or mentor target selection, **When** opened, **Then** roster/summary and selected/eligible targets are not rebuilt via redundant full re-fetches of the same cards.
3. **Given** pending rewards or legendary preparation that mutate state, **When** those actions run, **Then** they remain explicit mutations — not hidden inside the hub read.

---

### User Story 6 — Shared read caches reduce repeated cold work without lying about balances (Priority: P2)

As the player base grows, repeated reads of slow-changing shared data (configuration, guild settings, standings snapshots, first leaderboard pages) are served quickly from disposable cache, while spending coins/energy/ownership still always re-validates live.

**Why this priority**: After queries are shaped correctly, caching multiplies the win; caching bad full-table reads would hide the real bug.

**Independent Test**: Hit shared hubs repeatedly within TTL; observe hit-rate and latency drop; mutate economy and confirm balances cannot be authorized from stale cache alone.

**Acceptance Scenarios**:

1. **Given** a single cache abstraction, **When** config/guild/standings/first-page leaderboard caches are enabled, **Then** business code does not grow ad-hoc dictionaries per module.
2. **Given** many managers request the same standings just after expiry, **When** stampede protection is active, **Then** refresh does not fan out into one database load per concurrent requester.
3. **Given** a mutation that spends resources, **When** authorization runs, **Then** live database/RPC checks decide success — never a stale display cache.

---

### User Story 7 — Mature rollouts stop living as permanent kill switches (Priority: P3)

As product/engineering owners, Match Engine V3, Mentor Transfusion, and league lifecycle modes follow an explicit mature-or-remove policy: soak, make permanent, then delete obsolete parallel paths — without mixing that risk into the same deploy as major query rewrites.

**Why this priority**: Reduces long-term branch complexity; deliberately sequenced after hot-path stability.

**Independent Test**: Document flag inventory; after soak criteria, remove designated mature flags; confirm only one authoritative league lifecycle path remains for each responsibility.

**Acceptance Scenarios**:

1. **Given** Match V3 flags enabled for all match types for the agreed soak, **When** soak metrics are acceptable, **Then** new matches stop creating V2 runs and V2 execution can later be removed once recoverable V2 runs are drained.
2. **Given** Mentor Transfusion stable in production, **When** maturation completes, **Then** the environment kill switch is removed and the feature is treated as standard gameplay.
3. **Given** league automation/dynamics/lifecycle overlap, **When** audit completes, **Then** obsolete parallel modes/jobs are removed or consolidated — not merely “all flags set true.”

---

### User Story 8 — Background and multi-instance readiness without drama (Priority: P3)

As operators approaching multiple bot processes, important background work survives restarts via durable claimed jobs, scheduler work is multi-instance-safe or explicitly single-worker, and optional shared cache remains behind the same abstraction — without requiring Redis on day one.

**Why this priority**: Unblocks horizontal scale; high risk if rushed ahead of hot-path and measurement work.

**Independent Test**: Kill a process mid-job; confirm claimed work resumes or fails safely once; run two workers against a claimable job without double-apply.

**Acceptance Scenarios**:

1. **Given** notification fanout, analytics, cleanup, or chunked season prizes, **When** moved off the interaction path, **Then** work is durable and idempotent under restart.
2. **Given** two bot instances, **When** a scheduled job wakes, **Then** it does not double-settle the same work.
3. **Given** multi-instance still not justified, **When** Phase 3 cache ships, **Then** memory backend + short TTL suffice; Redis remains optional behind the same interface.

---

### Edge Cases

- Baseline window interrupted by deploy/incident — extend capture rather than comparing unequal days blindly.
- Leaderboard ties and rapid LP changes mid-page — cursors must remain stable enough that managers do not see duplicate/missing rows for the same snapshot semantics defined in plan.
- Marketplace filters that match zero listings — empty page with clear UX, not an error.
- Transient upstream throttling on safe reads — retry with backoff; mutations without idempotency keys must not blind-retry after uncertain timeout.
- Persistent Discord views referencing deleted custom IDs — catalog before deleting placeholder UI.
- Free-tier storage/egress pressure — metrics retention stays aggregated; full-table leaderboard/market patterns must not return.
- Connection-pool tuning — do not raise concurrency ceilings until hot-path round trips drop; load-test small steps only.

---

## Requirements *(mandatory)*

### Functional Requirements

#### Measurement & observability

- **FR-001**: System MUST capture a production baseline (24–72 hours) of per-command/hub volume, p50/p95/p99 latency, data round trips, cache hits/misses, and error/throttle classes before claiming optimization success.
- **FR-002**: Existing performance signal collection MUST be extended rather than replaced by a parallel monitoring framework.
- **FR-003**: Owner-only admin (or equivalent operator) surface MUST expose performance summary: uptime, instance identity, request volume, latency percentiles, round trips, retries, throttle/server errors, cache effectiveness, scheduler/job health indicators when jobs exist.
- **FR-004**: Durable metrics persistence MUST use short in-memory aggregates flushed periodically — not one stored row per command.
- **FR-005**: Error reporting integration (when configured via existing DSN) MUST initialize at startup and tag safe context (command/hub, instance, guild, RPC name, latency class, error category) without tokens or sensitive payloads.

#### Cleanup & dependencies

- **FR-006**: Unused legacy `training` and `training_engine` packages MUST be deleted after repository verification shows no live application imports; exclusive abandoned tests MUST be moved or removed.
- **FR-007**: Production dependency install MUST include the `energy` package as an editable local package so fresh installs are deterministic.
- **FR-008**: Confirmed-unused Alembic/ORM runtime libraries MUST be removed from production bot dependencies after import verification; direct database tools needed only for ops MUST live in a separate ops/dev requirements set.
- **FR-009**: Placeholder/dead Discord UI (unused views, obsolete aliases, unplanned “Coming Soon” controls) MUST only be removed after a catalog of loaded cogs, app commands, persistent views, and custom ID handlers exists.

#### Hot-path reads (Phase 2 priority)

- **FR-010**: Division leaderboard MUST serve page-sized results with viewer rank, total count, and promotion/relegation cutoffs via server-side paging — not full-division transfer into the application for pagination.
- **FR-011**: Global leaderboard MUST serve page-sized results with viewer rank/LP and stable tie-break cursors.
- **FR-012**: Growing list surfaces (leaderboards, transfer listings, match history, sales/audit history) MUST use keyset/cursor pagination — not OFFSET on growing tables.
- **FR-013**: Transfer Board browse MUST filter, sort, and page in the database and return exactly the displayed page.
- **FR-014**: Marketplace sell eligibility MUST be obtainable in one consolidated read of relational eligibility state.
- **FR-015**: Marketplace hub summary (manager economy summary, transfer enabled, listing count/cap) MUST be obtainable in one consolidated read.
- **FR-016**: Development hub display state MUST be obtainable via a consolidated read-state path separated from claim/create mutations.
- **FR-017**: Skills and mentor target flows MUST avoid redundant roster/card re-fetch patterns for the same interaction.
- **FR-018**: Remaining clusters of per-request configuration reads on the same path MUST use the existing batched configuration helper (or one purpose-specific read).

#### Caching

- **FR-019**: Disposable caching MUST go through one replaceable cache backend abstraction (get/set/delete/prefix/get-or-set/stats) rather than scattered module dictionaries.
- **FR-020**: Cache tiers MUST cover at least: game configuration, guild configuration, short-lived profile display summaries, and standings/first-page leaderboard snapshots — with TTLs appropriate to change rate.
- **FR-021**: Cache MUST NEVER authorize mutations for coins, energy, ownership, locks, SP, evolution claims, or registration uniqueness.
- **FR-022**: Memory cache MUST implement per-key single-flight refresh to limit expiry stampedes.
- **FR-023**: Shared/remote cache backends remain optional until multi-instance or measured read load justifies them; invalidation strategy MUST be documented for single- and multi-instance phases.

#### Resilience & clients

- **FR-024**: Hosted HTTP client MUST remain a singleton/reused client; pool sizes MUST be configurable and chosen from load tests after query reduction — not increased as a substitute for fewer queries.
- **FR-025**: Process-local concurrency backpressure MUST cap non-critical read fanout under burst load (limits from load tests).
- **FR-026**: Safe reads MUST support jittered exponential backoff on transient throttle/gateway/timeouts; mutations MUST NOT blind-retry without a durable idempotency identity.

#### Background work & scale readiness

- **FR-027**: Core match settlement effects that gameplay depends on immediately (result, lock release, coins/rewards, XP when required, fatigue/injury, league fixture result) MUST remain committed before the match is treated as complete — not deferred solely to best-effort background tasks.
- **FR-028**: Good async candidates (notification fanout, journals, analytics/rollups, cleanup, chunked season prizes) MUST use durable claimed jobs with idempotency keys, reusing existing outbox/claim patterns.
- **FR-029**: Every scheduler job MUST be either distributed-safe (claim/lock/idempotency) or explicitly single-worker via configuration.
- **FR-030**: Before multi-instance production: mutations idempotent where interactive; no important process-only business truth; match locks database-backed; instance identity in logs/metrics; Discord sharding approach documented.

#### Feature maturity (sequenced)

- **FR-031**: Temporary rollout flags MUST record introduced-at, expected-remove-after, owner, and rollback purpose; mature features MUST shed permanent environment kill switches after soak.
- **FR-032**: Match V2 deletion MUST follow: all V3 mode flags soaked → V3 default → stop new V2 runs → remove V2 execution only after no active/recoverable V2 runs remain — never in the same deploy as major hot-path RPC rewrites.
- **FR-033**: League dynamics/automation/lifecycle overlap MUST be audited from execution traces; obsolete parallel modes/jobs removed or consolidated to one authoritative path per responsibility.

#### Quality gates

- **FR-034**: Structural/CI checks MUST catch regressions such as oversized leaderboard/market pages, client-side market filtering returning, hot hubs exceeding round-trip budgets, and unbatched config clusters.
- **FR-035**: Load-test scripts MUST exercise hub/RPC helpers against non-production Discord traffic (dev/staging data plane), including mixed read/mutation workloads, and stop at saturation rather than aiming to crash the database.
- **FR-036**: Indexes MUST be added only after measured query evidence (not intuition alone) and must not duplicate existing constraints.

### Key Entities

- **Command/Hub Performance Sample**: Aggregated latency and load observations for a named interactive surface over a time bucket.
- **Leaderboard Page**: Ordered slice of standings plus viewer context and cursors for the next/previous page.
- **Market Browse Page**: Filtered/sorted slice of active listings sized for one UI page.
- **Hub Read State**: Display-only snapshot for marketplace or development entry (explicitly non-authoritative for spends).
- **Cache Entry**: Disposable keyed value with TTL and optional single-flight refresh.
- **Durable Job**: Claimable background unit with type, payload, idempotency key, attempts, and status.
- **Feature Flag Record**: Temporary rollout control with ownership and removal target (distinct from permanent economy tunables).

### Round-trip budgets (operator targets)

| Surface | Target data requests per interaction |
|---------|--------------------------------------:|
| Profile | 1–2 |
| Squad | 1–2 |
| Development hub | 1–2 |
| Drill menu | ≤3 |
| Marketplace hub | 1 |
| Transfer Board page | 1 |
| Leaderboard page | 1–2 |

### Latency SLOs (internal)

| Path | p50 | p95 |
|------|----:|----:|
| Light hub | <300 ms | <750 ms |
| Normal management hub | <500 ms | <1.2 s |
| Heavy leaderboard/market | <800 ms | <1.8 s |
| Mutation after defer | <1 s | <2 s |

Discord interactions continue to defer immediately where appropriate.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After Phase 0, operators can produce a before/after latency and round-trip report for each named hot hub using the same signal definitions.
- **SC-002**: Hot hubs targeted in Phase 2 show at least 50% fewer data round trips versus their Phase 0 baseline under comparable traffic.
- **SC-003**: Light / normal / heavy hub and post-defer mutation latency meet the internal SLO table under normal load; degraded-but-usable behavior holds under documented peak tests without silent hangs.
- **SC-004**: Division and Global leaderboard interactions never transfer an entire division/global population into the application for pagination.
- **SC-005**: Transfer Board filtered browse returns only page-sized matching listings and can discover matches that would have been invisible under the former small prefetch window.
- **SC-006**: Shared slow-changing reads (config and equivalent Tier 1–2 data) achieve ≥80% cache hit rate in steady state after cache expansion; mutation authorization remains live-checked.
- **SC-007**: Fresh production installs succeed with `energy` present; deleted legacy training packages have zero live application imports; production runtime dependency set excludes verified-unused Alembic/ORM libraries.
- **SC-008**: Load tests identify a saturation “knee” (concurrency where errors/latency break SLOs) on staging/dev without using production Discord as a load generator.
- **SC-009**: With durable jobs enabled for chosen background work, process restart does not permanently lose that work; multi-instance job double-apply is prevented for claimed jobs.
- **SC-010**: Match V2 stops creating new runs only after V3 soak acceptance; V2 execution removal happens only after recoverable V2 drain — and not in the same release as Phase 2 hot-path rewrites.

---

## Assumptions

- Prior work in `038`/`039`/`040` remains the capacity and integrity baseline; this epic extends it rather than reopening Principle II (hosted async client + atomic RPCs).
- Potential-cap incident (`049`) notification ops can finish independently and are not a blocker for Phase 1 cleanup/measurement.
- Staging or a safe non-production data plane exists (or can be stood up) for load scripts; production Discord is never used as a load generator.
- Free-tier egress/storage limits make reducing returned row counts and round trips valuable even before paid upgrades.
- Infrastructure upgrade thresholds (storage, egress, sustained p95, CPU, throttles) from the roadmap guide when to stop squeezing code and buy capacity.
- Mentor Transfusion and Match V3 are close enough to “mature or schedule maturation” that flag policy applies; exact soak durations are set in plan/ops notes.
- Large cog extractions (`development` first) improve maintainability without UX changes; battle/league extractions wait until performance waves stabilize.
- HTTP pool defaults (20 / 5) stay until post–Phase 2 load tests justify a small step up.

---

## Phased delivery (summary for planning)

| Phase | Focus | Risk |
|-------|--------|------|
| 1 | Measurement, dead-package/deps cleanup, Sentry wiring, flag inventory, top-query report | Low |
| 2 | Leaderboard pages, market browse/sell/hub, development hub/skills/mentor reads, config batching | Medium |
| 3 | Cache backend + guild/standings/first-page/profile-display caches + single-flight | Medium |
| 4 | Measured indexes + cursor paging on remaining growing lists | Medium |
| 5 | Mentor/V3/league flag maturation (separate deploys from Phase 2) | Medium–High |
| 6 | Durable outbox generalization + notification/analytics off hot path | High |
| 7 | Multi-instance / sharding runbook; optional Redis behind same cache API | High |

**First sprint preference**: instrument → delete dead packages/fix energy/deps → division leaderboard page → Transfer Board server browse → collapse market/development hub reads → only then expand cache → index from evidence → soak V3 separately.
