# Feature Specification: Database Scalability & Performance Architecture

**Feature Branch**: `038-db-scalability-performance`

**Created**: 2026-07-22

**Status**: Implemented (2026-07-22) — Waves US1–US6 shipped under `tasks.md` (T001–T054). Multi-instance economy shared-cache and remaining job wraps stay gated in `contracts/phase-gate-checklist.md` / `job-claim-catalog.md`.

**Parent / Related**: `specs/029-game-integrity` (US-42), especially US-42.8 (Scheduler), US-42.9 (RPC Guarantees), US-42.7 (Economy Integrity). Does **not** replace gameplay specs. Overlays performance, caching, concurrency, and growth readiness onto existing single-pipe XP/economy and RPC integrity rules.

**Input**: User description: "Redesign the database layer so the Discord bot can scale from hundreds of users to tens/hundreds of thousands without a major rewrite — covering scalability, query performance, rate-limit resilience, caching, architecture patterns, high-concurrency safety, monitoring, and a phased migration roadmap. Prefer simple maintainable solutions; only add advanced patterns when measurable benefit is clear. Incorporate peer-review corrections: no false Free-tier REST request cap premise; idempotency for all mutating transactions; cache coherency under multi-instance; safe background-job ownership; single shared DB client lifecycle."

---

## 0. Epic Framing

### 0.1 Purpose

US-43 is the **architecture constitution for database scalability and command responsiveness**. Managers experience fast, reliable slash-command and hub interactions as the player base grows; operators can observe load and upgrade hosting without rewriting the bot.

This epic freezes **outcomes, constraints, and phased delivery gates**. Concrete indexes, cache keys, RPCs, and migrations are owned by `/speckit.plan` and child implementation waves — not invented ad hoc in cogs.

### 0.2 What this epic delivers now

| Deliverable | In this epic (`038`) | Deferred to plan / tasks |
|-------------|----------------------|--------------------------|
| Scale goals & non-goals | Frozen | — |
| Correct capacity premises | Frozen (see §0.4) | Hosting plan upgrades |
| Phased roadmap (P0–P3) | Frozen exit gates | Per-wave migrations & code |
| Caching coherency rules | Frozen | Cache key catalog |
| Idempotency & concurrency overlays | Frozen (extends INV-08) | Per-action key wiring gaps |
| Monitoring & alert intents | Frozen | Concrete dashboards/tools |
| Implementation | None in specify | After `/speckit.plan` + Locked → `/speckit.tasks` |

### 0.3 Relationship to Game Integrity (US-42)

| Concern | Owner | This epic adds |
|---------|-------|----------------|
| Atomic money/XP/ownership | US-42.7 / 42.9 | Fewer round-trips; same pipes |
| Reward ≤ once (INV-08) | US-42 | **All** interactive mutations need durable idempotency keys (not only trades) |
| Scheduler settle-once | US-42.8 | Multi-instance job ownership so jobs do not fire N times |
| Fail-closed / no sporting forfeit from infra | US-42.5 | Performance outages must degrade gracefully, not invent results |

**Rule**: Performance work MUST NOT invent parallel coin/XP pipes, skip exclusive-state checks, or weaken idempotency for speed.

### 0.4 Corrected capacity premises (mandatory)

Peer review rejected a false Free-tier “2 REST requests/second” premise. Planning MUST assume:

1. **Hosted data-API request volume is not the Free-tier bottleneck** in the form claimed; observed throttling / stalls are more often auth limits, gateway limits, **connection-pool exhaustion**, CPU/IO saturation, or client mis-use.
2. **Connection and compute headroom** matter more than raw request count as concurrency grows.
3. **N+1 round-trips and uncached hot reads** remain first-class problems regardless of plan tier — they waste latency and amplify load under spikes.
4. Architecture must remain valid when upgrading the hosted plan or moving to self-hosted PostgreSQL later — no Free-tier-only dead ends.

### 0.5 Non-goals

- New slash commands, hub buttons, or gameplay loops solely for “performance UI.”
- Premature sharding or multi-region databases.
- Replacing Discord with another client.
- Speculative microservices or message-bus rewrites before single-instance Phase 0–1 gains are exhausted.
- Weakening US-42 invariants for throughput.

### 0.6 PL/pgSQL maintainability bound (Principle II)

Keeping Principle II means multi-table atomicity and durable idempotency live in server-side procedures. To avoid the “all domain logic in the database” trap:

- **Pure formulas and gates** remain in `packages/` (Python) as the source of truth for curves, prices-as-math, and eligibility checks.
- **Procedures** are thin transactional shells: validate ownership/locks, enforce idempotency, apply already-computed amounts, write ledger rows, return a structured outcome.
- New complex gameplay algorithms MUST NOT be invented only in SQL when a package mirror is required by existing monorepo rules (US-23/US-25 progression/economy).

---

## Clarifications

### Session 2026-07-22

- Q: Keep Principle II (RPC mutations) or amend constitution for direct pooled SQL in Python? → A: Option A — Keep Principle II; packages own formulas; procedures stay thin transactional shells; no `asyncpg` without a later constitution amendment.
- Q: How must economy tunables (prices/rates) stay coherent under multi-instance? → A: Option A — Shared cache or active cross-instance invalidation; process-local TTL alone is insufficient once multi-instance is live.
- Q: What must idempotent mutations return so retries render success UI? → A: Option A — Structured outcome distinguishing `applied` vs `already_applied`, plus result payload; collisions must not surface as raw errors / false failures.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Commands feel fast under normal and peak play (Priority: P1)

As a manager, when I open hubs (`/development`, `/store`, league hub, profile, squad) or run common actions during busy hours, I get a timely Discord response — not multi-second waits that feel like the bot is stuck.

**Why this priority**: Perceived speed is the primary player-facing value of this epic; slow hubs drive churn and support noise.

**Independent Test**: Time p50/p95 for a named set of top commands before/after Phase 0–1; confirm Discord interaction completes with a legible result within the success targets without raw errors.

**Acceptance Scenarios**:

1. **Given** a registered manager with a normal club, **When** they open a top hub command under light load, **Then** they receive a complete UI within the Success Criteria latency targets.
2. **Given** many managers in one or more guilds acting at once, **When** the same hubs are used, **Then** responses remain within degraded-but-usable targets (not silent hangs or unexplained failures).
3. **Given** a command that previously needed many sequential data fetches, **When** refactored under this epic’s Phase 1 gate, **Then** the manager still sees the same correct data with fewer delays.

---

### User Story 2 — Growth does not force a rewrite (Priority: P1)

As the product owner, I can grow from hundreds of registered managers toward tens or hundreds of thousands of accounts, and later add bot instances or upgrade hosting, without discarding the repository/service shape or rewriting core game rules.

**Why this priority**: Avoiding a “scale rewrite” is the stated strategic goal.

**Independent Test**: Architecture review checklist (phases, coherency rules, job ownership, client lifecycle) is Locked; Phase gates name when Redis / workers / replicas become justified.

**Acceptance Scenarios**:

1. **Given** Phase 0–1 complete, **When** registered users and concurrent command volume grow within published Phase 2 thresholds, **Then** no emergency rewrite is required — only planned Phase 2 work items.
2. **Given** a future need for multiple bot processes, **When** that decision is made, **Then** the Locked multi-instance rules (cache coherency + job ownership) apply without redesigning game logic.
3. **Given** a hosting upgrade or self-hosted PostgreSQL move, **When** connection settings change, **Then** application contracts (RPC pipes, idempotency, schema migrations) remain the same.

---

### User Story 3 — Spikes do not corrupt economy or inventory (Priority: P1)

As a manager (and as the opposing manager), simultaneous pack opens, transfers, coin spends, match settlements, and inventory changes never double-grant, lose updates, or leave half-applied balances — including when Discord retries or the interaction times out and is re-pressed.

**Why this priority**: Speed without integrity destroys trust; extends US-42 INV-08 to performance-driven consolidation of writes.

**Independent Test**: Double-invoke and concurrent-mutation suites for Phase-prioritized write paths; at most one durable effect per logical action key.

**Acceptance Scenarios**:

1. **Given** Discord delivers two interactions for the same reward or purchase intent, **When** both are processed, **Then** durable state changes at most once and the second outcome is safe (“already done” / prior result / clear reject).
2. **Given** two managers contend on the same listing or scarce resource, **When** both confirm, **Then** exactly one success path completes and neither side is left with partial coin/card state.
3. **Given** a consolidated multi-step write (single atomic operation), **When** a network retry occurs, **Then** idempotency prevents double charge / double grant (closing the “atomic but not once-only” loophole).
4. **Given** the durable write commits but the bot never receives the success response (dropped reply / timeout), **When** the manager presses the same control again with the same logical action key, **Then** the bot acknowledges success using the prior committed result (`already_applied`) — not an error that implies the first attempt failed.

---

### User Story 4 — Operators can see health and act before outage (Priority: P2)

As an operator / tech lead, I can see whether the bot is slow because of data access, cache misses, connection pressure, or error spikes — and receive alerts before managers flood support.

**Why this priority**: Blind scaling ships regressions; observability is required to prioritize the next phase.

**Independent Test**: Documented metrics and alert thresholds exist; a dry-run shows operators can answer “are we healthy?” from the published signals.

**Acceptance Scenarios**:

1. **Given** elevated command latency, **When** an operator checks the published signals, **Then** they can distinguish user-facing slowness from background-job load.
2. **Given** error or retry rates cross thresholds, **When** alerts fire, **Then** operators have a named first response (not “restart and hope”).
3. **Given** Phase 1 caching is live, **When** operators inspect hit/miss signals, **Then** they can tell whether cache is helping or serving stale mutable data incorrectly.

---

### User Story 5 — Background work stays once-only when the bot scales out (Priority: P2)

As an operator, daily recovery, league automation, leaderboard refresh, and similar jobs run exactly as designed — once per due window — even if multiple bot processes exist.

**Why this priority**: Peer review identified APScheduler-in-every-instance as a duplicate-fire risk under horizontal scale.

**Independent Test**: With two processes configured under Phase 3 rules, a due job produces one logical run (or one leader-owned run), not N parallel settlements.

**Acceptance Scenarios**:

1. **Given** a single bot instance (Phase 0–2 default), **When** scheduled jobs run, **Then** behavior matches today’s settle-once / US-42.8 expectations.
2. **Given** multiple bot instances are enabled, **When** a job is due, **Then** only one owner executes the durable side effects.
3. **Given** a job retries after a crash mid-run, **When** recovery completes, **Then** durable rewards/settlements remain once-only (existing run keys still apply).

---

### User Story 6 — Phased delivery prefers simple gains first (Priority: P3)

As the engineering owner, I implement the highest-impact, lowest-complexity improvements first (indexes, round-trip reduction, local cache for stable data, retries) and only introduce shared cache, workers, or write-behind when Phase exit metrics say they are needed.

**Why this priority**: Matches YAGNI / Ponytail and the user’s “no unnecessary complexity” mandate.

**Independent Test**: Roadmap phases have exit gates; Phase 3+ items are blocked until gates fail or capacity thresholds are hit.

**Acceptance Scenarios**:

1. **Given** Phase 0–1 incomplete, **When** someone proposes Redis or sharding, **Then** the proposal is deferred unless a measured gap proves local cache / RPC consolidation insufficient.
2. **Given** Phase 1 exit metrics met, **When** concurrent load still violates Success Criteria, **Then** Phase 2 items become eligible in priority order.
3. **Given** any recommendation, **When** reviewed, **Then** complexity, risk, and expected gain are recorded (see Roadmap trade-off table in plan — required before implement).

---

### Edge Cases

- Interaction timeout + user retry on a consolidated write → must not double-apply.
- **Successful retry (committed, response lost):** Database commits; HTTP/API reply to the bot drops; manager clicks again → second call returns `already_applied` with prior result payload; UI shows success (updated balances/items), never a raw conflict/500 that looks like failure.
- Stale hub embed after bot restart while cache holds old profile/economy summary → manager must not see inventable balances; critical balances prefer short TTL or invalidate-on-write.
- Two bot instances with local-only mutable cache → forbidden once multi-instance is live (split-brain).
- Two bot instances with divergent cached **economy prices/rates** → forbidden; managers must not be able to shop a cheaper shard (FR-012).
- Hosting connection pool near exhaustion → commands fail closed with friendly error; no silent partial writes.
- Leaderboard or standings under heavy read → slightly stale cached view acceptable within published TTL; match settlement truth remains source of record.
- Season/matchday lock or pause in progress → performance paths must not bypass league integrity gates.
- Free-tier or small-plan resource saturation → degrade gracefully; do not assume unlimited compute.
- Cache invalidation missed after spend → next read within TTL may be stale; for coin/energy, invalidation-on-write is mandatory where cached.
- Consolidated nested reads without supporting indexes → may be slower than N+1; Phase 1 must verify plans before/after (FR-020).

---

## Requirements *(mandatory)*

### Functional Requirements

#### Responsiveness & round-trips

- **FR-001**: System MUST reduce unnecessary sequential data fetches for the highest-traffic manager commands so each command completes with the minimum number of remote data round-trips needed for correctness.
- **FR-002**: System MUST fetch related read data for a single command intent in one logical load where feasible (dashboard-style loads), rather than one remote call per related entity.
- **FR-003**: System MUST avoid retrieving unused wide payloads when only a small field set is required for the UI.
- **FR-004**: List/browse surfaces that can grow large (leaderboards, market listings, histories) MUST use pagination that remains efficient as row counts grow (cursor-style progression preferred over deep offset scans).

#### Integrity under consolidation

- **FR-005**: Multi-step state changes that must succeed or fail together MUST execute as one atomic durable unit (existing RPC / transaction discipline per constitution and US-42.9).
- **FR-006**: Every interactive state-mutating logical action in scope of this epic’s write waves MUST declare and enforce a durable idempotency key so retries and double-invokes cannot double-apply effects (extends INV-08 beyond trading alone).
- **FR-006a (Idempotent Outcome Contract)**: Idempotent mutating procedures MUST return a structured success outcome the application can render without guessing. At minimum the outcome distinguishes **`applied`** (first durable success) vs **`already_applied`** (replay / collision after prior commit) and includes a **result payload** sufficient to refresh the manager UI (e.g. balances, granted items, or prior snapshot fields). Unique-key / collision paths MUST be handled inside the procedure and MUST NOT surface to the manager as a raw constraint failure, HTTP 409/500, or “transaction failed” when the logical action already succeeded.
- **FR-007**: High-contention updates (coins, energy, pack grants, transfers, inventory ownership) MUST remain race-safe under concurrent managers — no lost updates, duplicate rewards, or half-applied states.
- **FR-008**: Performance optimizations MUST NOT introduce a second coin pipe, second XP pipe, or bypass exclusive-state / match-lock rules.

#### Caching

- **FR-009**: System MUST support a phased caching approach: start with per-process cache for slowly changing / reference data; introduce a shared cache only when multiple bot processes require coherent mutable reads.
- **FR-010**: Cache policy MUST specify, per data class: whether cached, where, TTL, and invalidation trigger (see Key Entities — Cache Policy).
- **FR-011**: Once multiple bot processes are live, mutable user/club economy and profile summaries MUST NOT rely on process-local cache as the sole coherency mechanism (split-brain prohibition).
- **FR-012**: Non-economy guild settings MAY use process-local cache with explicit invalidation or short TTL under multi-instance, provided staleness bounds are published. **Economy tunables** that affect prices, drop rates, faucet/sink amounts, or other manager-facing math MUST, under multi-instance, use a shared cache **or** active cross-instance invalidation (pub-sub / broadcast). Process-local TTL alone is forbidden for those tunables once multi-instance is live (prevents split-brain pricing exploits).

#### Capacity & resilience

- **FR-013**: Data-access clients MUST be created once at process startup and reused; command handlers MUST NOT create a new remote client per interaction.
- **FR-014**: Transient remote failures and rate/limit responses MUST use bounded retry with backoff/jitter where safe; non-idempotent paths MUST NOT blindly retry without FR-006 protection.
- **FR-015**: Non-interactive heavy work (daily recovery, season lifecycle batches, leaderboard recompute, bulk logging) MUST be eligible to run off the interactive command path so managers are not blocked by batch jobs.
- **FR-016**: When multiple bot processes run, scheduled jobs MUST have single-owner semantics for durable side effects (centralized coordination or dedicated worker process).

#### Observability

- **FR-017**: Operators MUST have access to signals for: command latency, data-access error/retry rate, cache effectiveness (where caching exists), and resource pressure indicators appropriate to the hosting plan.
- **FR-018**: Alert thresholds MUST be defined for unhealthy latency, error spikes, and sustained resource pressure (exact tooling in plan).

#### Governance & delivery

- **FR-019**: Delivery MUST follow the phased roadmap (Phase 0–3) with exit gates; advanced patterns (shared cache, write-behind buffers, read replicas, sharding) are out of scope until their gate criteria are met or explicitly waived in an amended Locked plan.
- **FR-020**: Index and query improvements MUST be validated against real slow paths (measurement first) — no speculative over-indexing. Consolidated / nested hot-path reads (FR-002) MUST capture before/after query-plan evidence in Phase 1 so a “single load” cannot regress into a worse join plan than the N+1 it replaces.
- **FR-021**: Project constitution Principle II (hosted async data client as the application DB interface; mutations via atomic server-side procedures) remains the write path for this epic. Direct pooled SQL sessions from application code are out of scope unless a future Locked constitution amendment says otherwise. Procedures MUST stay thin transactional shells; pure formulas and eligibility gates MUST remain in packages (see section 0.6).
- **FR-022**: Player-facing behavior and copy MUST remain correct under caching; economy/progression UX changes that alter manager-visible rules still update `change_log.md` when shipping.

### Key Entities

- **Logical Action**: One manager/system intent (open hub, buy refill, open pack, settle match) identified by an idempotency key for mutations.
- **Idempotent Outcome**: Structured procedure result with status `applied` | `already_applied` (and failure reason family when not applied) plus a result payload for UI refresh — never a raw unique-constraint error for replays.
- **Command Data Load**: The set of reads required to render one interaction response; target is one consolidated load where possible.
- **Cache Policy**: Per data class rules — cacheability, layer (process-local vs shared), TTL, invalidation trigger, acceptable staleness.
- **Phase Gate**: Named metric or capacity threshold that unlocks the next complexity tier.
- **Job Ownership Record**: Mechanism ensuring a due scheduled job’s durable effects run once across processes.
- **Hot Path Catalog**: Ordered list of highest-traffic commands/hubs chosen for Phase 1 consolidation (owned by plan).
- **Cache Key Catalog**: Named key patterns for shared cache entries (owned by plan before Phase 3 shared cache).

#### Cache policy defaults (assumptions; refine in plan)

| Data class | Cache? | Layer (single instance) | Layer (multi-instance) | TTL (default) | Invalidate when |
|------------|--------|-------------------------|------------------------|---------------|------------------|
| Economy tunables (prices / rates / faucets / sinks) | Yes | Process-local | **Shared or active invalidation** (not TTL-only local) | ~5 min or on change | Admin / config change (must reach all instances) |
| Other game tunables (non-priced flags) | Yes | Process-local | Process-local OK if non-exploitable | ~5 min or on change | Admin / config change |
| Guild settings (non-economy) | Yes | Process-local | Process-local OK | ~10 min | Settings update |
| Own profile summary | Yes | Process-local | Shared only | ~30 s | Attribute/XP/SP/match/etc. |
| Other profiles | Optional | Process-local | Shared or skip | ~5 min | Soft stale OK |
| Club economy summary | Yes | Process-local | Shared only | ~10 s | Coin/energy mutation |
| League standings | Yes | Process-local | Shared preferred | ~1 min | Matchday advance / settlement |
| Leaderboards | Yes | Process-local + periodic recompute | Shared rankings OK | ~5 min | Scheduled refresh |
| Vote / claim flags | Yes | Process-local | Shared if multi-instance | Long (hours) | Successful claim |
| Live inventory / active match | No (or ~0) | — | None | 0 | N/A |

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Under light load, managers receive a complete response for each Phase 1 hot-path command within **2 seconds** p95 (interaction → final UI), excluding Discord platform outages.
- **SC-002**: Under a controlled concurrency drill representing busy multi-guild peaks (target: on the order of **1,000** simultaneous command intents), the bot remains available and ≥95% of hot-path commands complete within **3 seconds** p95 or return a clear retryable error — no silent hangs and no corrupted balances.
- **SC-003**: Scripted double-invoke / retry suites for Phase-prioritized mutating actions show **zero** duplicate grants or double charges, and **zero** false-failure UIs when the first attempt already committed (`already_applied` renders as success).
- **SC-004**: After Phase 1, measured remote round-trips per hot-path command drop by **≥50%** versus the pre-epic baseline for those same commands (baseline captured in plan).
- **SC-005**: Operators can answer “are we healthy?” using published signals within **5 minutes** of an incident start (latency, errors, resource pressure).
- **SC-006**: With multi-instance enabled under Phase 3 rules, duplicate scheduled durable settlements for the same due window are **zero** in a two-process drill.
- **SC-007**: Architecture review confirms Phase 3+ complexity (shared cache, dedicated workers, replicas, sharding) is gated — not enabled by default in Phase 0–1.

---

## Assumptions

- Single bot process remains the default deployment through Phase 0–2; multi-instance is optional and gated.
- Existing repository/service modular boundaries and US-23/US-25 single XP/coin pipes remain; this epic optimizes access patterns around them.
- Hosted PostgreSQL (current Supabase project) remains the system of record; self-host is a future hosting choice, not a product rewrite.
- Free-tier and paid-tier differences are operational (connections, CPU, disk), not an excuse for different application semantics.
- Discord’s 3-second interaction acknowledge window continues to be handled via immediate defer (existing UI rule); success criteria measure time-to-final-UI after defer.
- The existing in-process scheduler remains the job runner unless Phase 3 introduces a dedicated worker; job *ownership* must be solved before scaling out processes. Plan may use a database-backed lock / claim table (or equivalent) so multi-instance can stay without a shared cache product in Phase 2 if desired.
- Idempotency keys for interactive mutations may use Discord interaction identity and/or existing domain keys (match run ids, economy ledger keys); plan chooses per action without requiring a single global table on day one if domain keys already suffice — gaps must be listed. All such paths still obey FR-006a.
- Optimistic UI (“show expected result then verify”) is optional and only where integrity risk is zero; default is wait for durable success.
- Write-behind buffering is Phase 3+ and forbidden for coin/XP/ownership without durable queue + crash recovery — prefer not for v1 of this epic.
- Sharding is explicitly last-resort and not expected before very large scale; a well-indexed primary database handles millions of rows for this product class.
- Constitution remains authoritative: Principle II write path confirmed for this epic (Clarifications 2026-07-22); no alternate application SQL driver path until Principle II is amended.

---

## Phased Roadmap *(mandatory for this epic)*

### Phase 0 — Measure & fix false premises (Immediate)

| Item | Intent |
|------|--------|
| Baseline hot-path latency & round-trip counts | Enable SC-004 |
| Identify true limit sources (pool, CPU, Auth, N+1) | Replace false REST-cap narrative |
| Index candidates from measured slow queries only | FR-020 |
| Confirm single shared DB client lifecycle | FR-013 |

**Exit**: Baseline numbers published in plan; top slow paths named.

### Phase 1 — No-regret (Immediate / first ship wave)

| Item | Intent |
|------|--------|
| Missing indexes for proven queries | Latency + load |
| Consolidate hot-path reads | FR-001–003 |
| Before/after query-plan snapshots for each consolidated hot-path load | FR-020 (avoid worse joins than N+1) |
| Process-local cache for config + safe summaries | FR-009–012 |
| N+1 audit on top commands | SC-004 |
| Safe retry/backoff on transient remote errors | FR-014 |
| Idempotency gap list + Idempotent Outcome Contract for consolidated writes | FR-006 / FR-006a |

**Exit**: SC-001 and SC-004 met for named hot paths; checklist green for integrity non-regression.

### Phase 2 — Short term (~5,000+ active managers or Phase 1 exit still failing under load)

| Item | Intent |
|------|--------|
| Critical write flows fully atomic + idempotent | FR-005–007 |
| Cursor pagination on large lists | FR-004 |
| Background recompute for heavy aggregates | FR-015 |
| Operator signals & alerts live | FR-017–018 |

**Exit**: SC-002 drill pass; SC-003 for Phase 2 write set; SC-005.

### Phase 3 — Multi-instance & smoothing (only when needed)

| Item | Intent |
|------|--------|
| Shared cache for mutable summaries **and** economy tunables (or active invalidation) | FR-011–012 |
| Job single-ownership / dedicated worker | FR-016, SC-006 |
| Cache Key Catalog before shared cache goes live | Naming collisions |
| Optional write-behind for **non-critical** telemetry only | High risk — explicit waiver |
| Optimistic locking where contention is low | FR-007 complement |

**Exit**: Two-process drill passes SC-006; no split-brain cache bugs in mutable data.

### Phase 4 — Large scale (100,000+ accounts / measured need)

| Item | Intent |
|------|--------|
| Read replicas for read-heavy paths | Hosting plan feature |
| Sharding evaluation | Last resort only |

**Exit**: Written decision record — adopt or explicitly defer.

### Complexity guidance (planning must expand)

| Recommendation | Complexity | Expected gain | Main risk |
|----------------|------------|---------------|-----------|
| Measured indexes | Low | High | Over-indexing slows writes |
| Process-local cache | Low | Very high (single instance) | Stale mutable data if invalidation missed |
| Read/write consolidation | Medium | High | Harder debugging; need idempotency |
| Shared cache | High | Required for multi-instance coherency | Ops cost; new failure mode |
| Write-behind | High | Peak smoothing | Data loss if buffer dies |
| Dedicated workers | Medium–High | Keeps interactive path fast | Job ownership bugs |
| Sharding | Very high | Only at extreme scale | Operational burden |

---

## Out of Scope (v1 of this epic)

- New public gameplay features.
- Replacing US-42 child specs.
- Mandatory Redis or mandatory direct SQL pooler in Phase 0–1.
- Analytics warehouse / real-time Discord push via database realtime as a Phase 0–1 deliverable.
