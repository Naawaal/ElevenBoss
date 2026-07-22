# Feature Specification: Match Engine V3 — Deterministic Tactical Engine

**Feature Branch**: `041-match-engine-v3`

**Created**: 2026-07-22

**Status**: Draft

**Parent / overlays**: Existing production NSS v2 (`packages/match_engine`), match integrity US-42.4 (`033-match-integrity`), injury/fatigue (`002`/`016`), live immersion (`004`), league lifecycle (`026`), economy/XP pipes (US-23 / US-25). Constitution Principles I–VII apply.

**Input**: User description: "MASTER PROMPT — ElevenBoss Match Engine V3 (Deterministic Tactical Engine): architecture and implementation plan before production code; Phase 0 Simulation Core Refactor; event-driven SoT; immutable context; decoupled AI; tactical transition behaviour (not probability inflation); Dixon-Coles as calibration only; preserve locks, settle-once, recovery, rewards, leagues, commentary."

## Clarifications

### Session 2026-07-22

- Q: Phase 0 scope for architecture strengthenings (Possession, DecisionWindows, schema version, Golden Corpus, etc.)? → A: **Option A** — all listed items are mandatory Phase 0 *architectural* deliverables; exclude new tactical transition profiles, Adaptive AI, advanced policies, rich explainability UI, and player-traits expansion. Phase 0 objective is **architectural parity** (no intentional gameplay behaviour change); Golden Corpus must reproduce same outcomes or stay within explicitly defined statistical tolerances where exact parity is impossible.

- Q: Phase 0 Golden Corpus parity tolerances (exact_parity vs stats_parity)? → A: **Option B (refined)** — Default classification is exact_parity (~80–90% of corpus): exact event hash, event order, final score, scorers/assists, injuries, cards, and settlement outputs (coins, XP, fatigue, injuries). stats_parity only with a documented architectural reason (never to bypass regressions): identical final score, winner/draw, and settlement outputs; win-rate drift <2 pp; possession drift <3 pp; shot-count drift <5%; average goals/match drift <2%.
- Q: What does exact_parity hash against once Possession scaffolding exists? → A: **Option A (refined)** — Three formal digests: (1) **Sporting Digest** for v2↔v3 (gameplay-significant events only: KICKOFF/HT/FT/GOAL/SAVE/MISS/Card/Injury/Sub/Tactical Decisions + final score + settlement inputs; excludes possession-boundary scaffolding, replay checkpoints, internal transitions, Projection). (2) **Deterministic Replay Digest** for v3↔v3 (every deterministic event including possession boundaries, windows, internal transitions, replay metadata). (3) **Settlement Digest** for integrity (coins, XP, fatigue, injuries, league points, match history payload, idempotency keys).
- Q: DecisionWindows vs no intentional gameplay change in Phase 0? → A: **Option B (refined)** — Phase 0 ships DecisionInbox, window metadata, persisted Decision events, and replay/recovery of those events, but application semantics remain immediate (NSS v2 parity). Fixed DecisionWindows (15/30/45/60/75/85) become authoritative in Wave 1 with simulation_schema_version bump, Golden Corpus regeneration, and player-facing changelog. Rule: simulation_schema_version defines gameplay semantics (not only data shapes); any intentional behaviour change requires a bump.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Same match, same outcome forever (Priority: P1) 🎯 MVP

A manager (or ops/recovery path) can replay any completed or interrupted match from its recorded inputs and seed and get **byte-identical sporting outcomes and event order**. Crash recovery after a bot restart produces the same goals, injuries, and key moments as if the process had never died.

**Why this priority**: Determinism and recoverability are the non-negotiable foundation; without them, tactics and AI cannot be trusted or tested.

**Independent Test**: Fix squads + seed + decision log; run simulation twice (and once via recovery path); compare full ordered event streams and final score — must match exactly.

**Acceptance Scenarios**:

1. **Given** identical kickoff inputs and seed, **When** the match is simulated twice with no human mid-match decisions, **Then** the ordered event stream and final score are identical.
2. **Given** a mid-stream crash with a durable run and seed, **When** recovery completes the match, **Then** the recovered result matches a clean full replay of the same inputs.
3. **Given** any hidden clock, global RNG, or unordered map iteration would affect outcomes, **When** the simulation runs, **Then** those sources are not used for sporting outcomes.

---

### User Story 2 — Simulation is not tied to Discord pacing (Priority: P1) 🎯 MVP

Match simulation advances in discrete steps that can run with Discord live delays, in silent/fast-forward mode (auto-sim, recovery), or in offline tests — without changing sporting results. Live presentation, commentary, and sleep timers consume events; they do not invent them.

**Why this priority**: Phase 0 Simulation Core Refactor; Discord coupling is the main barrier to testability and recovery parity.

**Independent Test**: Run the same seed via live-paced consumer and silent collector; event streams and scores match; only wall-clock timing differs.

**Acceptance Scenarios**:

1. **Given** a seeded match, **When** it is stepped to completion without Discord, **Then** a complete ordered event stream and final state are produced.
2. **Given** the same seed, **When** a live Discord consumer plays events with delays, **Then** sporting outcomes match the silent run.
3. **Given** commentary or UI failure mid-match after durable progress exists, **When** settlement proceeds, **Then** rewards still follow existing settle-once rules using the simulation result — not Discord presentation success.

---

### User Story 3 — Event stream is the sporting source of truth (Priority: P1) 🎯 MVP

Everything managers care about after a match — score, possession feel, shots, goals, injuries, tactical changes — is explainable from an ordered match event stream. Statistics and commentary are projections of that stream, not parallel competing truths.

**Why this priority**: Explainability and single source of truth; prevents “stats say X, ticker said Y.”

**Independent Test**: Derive possession/shots/goals/MOTM candidates only from the event stream; compare to any live counters — must agree; remove live counters and projections still work.

**Acceptance Scenarios**:

1. **Given** a finished match event stream, **When** box-score stats are projected, **Then** goals, shots, and possession agree with the stream.
2. **Given** a goal event in the stream, **When** commentary and rewards attribute scorer/assist, **Then** they use the same event fields — not a separate memory of the live ticker.
3. **Given** a match is recovered from durable data, **When** the stream is replayed, **Then** projected stats match the originally settled sporting result.

---

### User Story 4 — No regression of integrity, rewards, or match types (Priority: P1)

Bot, friendly, and league matches keep today’s integrity guarantees: locks, settle-once, friendly sandbox (no coins/XP/evo), league standings/LP rules, fatigue/injury pipes, and energy costs. V3 must dual-run or cut over without double-paying or inventing sporting forfeits from infrastructure failure.

**Why this priority**: Production already ships US-42.4 guarantees; engine evolution must not reopen exploit classes.

**Independent Test**: Re-run match-type matrix and settle-once / friendly-audit / recovery tests against V3 path; all pass unchanged in intent.

**Acceptance Scenarios**:

1. **Given** a bot or league match under V3, **When** settlement runs twice for the same run, **Then** coins/XP/energy/fatigue apply at most once.
2. **Given** a friendly under V3, **When** it completes, **Then** no coin faucet, match XP, or evolution tick.
3. **Given** MatchLocked during a V3 live sim, **When** the manager tries squad or development mutations gated today, **Then** they remain blocked until lock release.

---

### User Story 5 — Manager understands why the match went that way (Priority: P2)

After a competitive or bot match, the manager can see a short, plain-language explanation of the decisive moments (e.g. possession shifts, failed chances, goals, tactical changes) grounded in the event stream — not “RNG said so.” **Rich explainability UI is post–Phase 0**; Phase 0 only requires Replay/Explain projector stubs.

**Why this priority**: Explainability is a primary product goal; depends on P1 event SoT.

**Independent Test**: For a known fixture stream with a late equalizer, the summary cites that goal and preceding chance/turnover events; two replays produce the same summary inputs.

**Acceptance Scenarios**:

1. **Given** a completed bot/league match (post–Phase 0 UI), **When** the manager views the result summary, **Then** they see at least one explainable reason chain for the result (scoreline + key turning events).
2. **Given** identical replays, **When** explanations are generated, **Then** they reference the same ordered events.
3. **Given** a match with no goals, **When** explanation is shown, **Then** it still cites possession/chance patterns rather than empty or random text.

---

### User Story 6 — Tactical styles change transition behaviour (Priority: P2)

Managers (and AI) can select named tactical styles (at least: Balanced, Possession, Counter, Long Ball, High Press). Styles change **how the match flows** (build-up length, transition speed, press/turnover frequency, fatigue pressure) — not by simply padding goal probability. **Not in Phase 0** — ships only after architectural parity is accepted and `simulation_schema_version` is bumped for the intentional behaviour change.

**Why this priority**: Core V3 gameplay differentiator; must not ship until Phase 0 architectural parity is accepted.

**Independent Test**: Same squads/seed, vary only tactic; event-type histograms and average phase timings differ in the direction specified for that style; win-rate gates stay within published regression bands unless intentionally rebalanced and documented.

**Acceptance Scenarios**:

1. **Given** Possession vs Counter on identical squads/seed families, **When** many matches are simulated, **Then** Possession shows longer build-up / more midfield control events; Counter shows faster transitions and fewer prolonged build-ups.
2. **Given** High Press, **When** matches are simulated, **Then** interception/turnover-related events and fatigue pressure increase relative to Balanced under the same intensity rules.
3. **Given** a tactic change mid-match at a DecisionWindow, **When** the match continues, **Then** the change is recorded as a Decision event and subsequent transitions use the new style.

---

### User Story 7 — Human tactical decisions are safe under replay (Priority: P2)

Managers change tactics via a **DecisionInbox** (receive → validate → collapse → apply). Each accepted decision is a Decision-category event with window metadata for recovery. **Phase 0**: apply remains **immediate** (same sporting effect timing as NSS v2). **Wave 1**: fixed DecisionWindows (15', 30', 45', 60', 75', 85') become authoritative apply points (schema bump + changelog).

**Why this priority**: Must keep drama and determinism without silently changing Phase 0 gameplay.

**Independent Test**: Phase 0 — spam/collapse still yields one effective stance change at apply time matching v2 immediacy; replay from Decision events matches. Wave 1 — clicks outside windows do not apply until the next window.

**Acceptance Scenarios**:

1. **Given** Phase 0 and a manager changes tactics mid-match, **When** the DecisionInbox applies, **Then** the stance takes effect immediately (v2 parity) and a Decision event is recorded (with window metadata).
2. **Given** a crash after an accepted tactic change, **When** recovery replays Decision events, **Then** the same apply timing semantics for that `simulation_schema_version` are reproduced.
3. **Given** Wave 1 schema with window enforcement, **When** a manager spam-clicks between windows, **Then** at most one collapsed intent applies at the next window and emits one Decision event.

---

### User Story 8 — AI managers decide via events, not by poking the sim (Priority: P3)

Bot/AI opponents use **BotBrain → Policy → DecisionIntent**. Phase 0 ships only a thin DefaultPolicy preserving today’s behaviour. Adaptive / difficulty policies are post–Phase 0. Simulation never receives mutable state from AI.

**Why this priority**: Extensibility without rewriting the sporting core; Phase 0 needs the seam, not rich policies.

**Independent Test**: Swap Policy module behind BotBrain; same simulation core accepts DecisionIntents; no AI path mutates score/squad directly.

**Acceptance Scenarios**:

1. **Given** an AI DecisionIntent at a DecisionWindow, **When** the step applies it, **Then** subsequent play reflects that decision and a Decision-category event is in the stream.
2. **Given** two Policy implementations, **When** only the Policy changes, **Then** BotBrain and SimulationEngine surfaces are unchanged.
3. **Given** DefaultPolicy, **When** a bot match runs under Phase 0, **Then** outcomes stay within architectural-parity gates vs NSS v2 (no intentional gameplay change).

---

### Edge Cases

- Bot restart mid-injury interactive pause: recovery must auto-resolve or resume without inventing a second injury or double settlement.
- One side disconnected in friendly: existing abandon/log behaviour preserved; V3 must not grant competitive rewards.
- Extremely lopsided OVR: immersion floor and win-rate regression bands still apply unless explicitly retuned in a documented balance change.
- Empty or exhausted bench on injury: ten-men / emergency GK paths remain deterministic and recorded as events.
- Dual-running V2 and V3: a match started on one engine version must finish and settle on the same version.
- Auto-sim / silent league resolution: must use the same step engine as live, not a parallel score inventer.
- Concurrent finalize and recovery for the same run: settle-once still holds.
- Tactic change exactly at half-time / full-time boundary: DecisionWindow at 45' applies; never half-applied across the boundary.
- Projection-category outputs (commentary text, match summary copy) MUST NOT be used as replay inputs.
- A fixture MUST NOT be reclassified to `stats_parity` solely because a test failed `exact_parity` — requires documented architectural reason in fixture metadata (SC-011).

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST produce identical ordered event streams and final scores for identical kickoff inputs, seed, and recorded mid-match decisions (determinism).
- **FR-002**: System MUST NOT use wall-clock time, process-global RNG, or non-deterministic iteration order for sporting outcomes.
- **FR-003**: System MUST expose a step-based simulation progression usable by live Discord, silent auto-sim, recovery, and offline tests without changing sporting results.
- **FR-004**: System MUST treat the ordered match event stream as the sole sporting source of truth; commentary and statistics MUST be derived from that stream.
- **FR-005**: System MUST record every material sporting occurrence as an event (including at minimum: kickoff, half-time, full-time, possession lifecycle, phase transitions of record, chances, shots outcomes, goals, saves, misses, fouls/cards if present, injuries, substitutions/resolutions, tactical decisions, and AI decisions when applicable).
- **FR-006**: System MUST support durable persistence of match run metadata + append-only events; competitive (bot/league) flushes MUST occur on **possession boundaries** (and forced barriers: HT/FT/injury await/completing).
- **FR-007**: System MUST preserve existing match-type behaviour: bot and league settle via current reward/integrity pipes; friendlies remain sandbox (no coins, match XP, or evolution tick).
- **FR-008**: System MUST preserve match locks, settle-once, and recovery semantics defined by match integrity (US-42.4); infrastructure failure MUST NOT invent sporting forfeits.
- **FR-009**: System MUST migrate from NSS v2 to V3 with dual-run and version pinning (`engine_version` + `simulation_schema_version`) so in-flight matches do not cross engines or simulation schemas mid-run.
- **FR-010**: System MUST keep existing fatigue, injury, XP, and economy settlement call sites semantically equivalent for rewarding match types (same pipes; no parallel coin/XP writers).
- **FR-011**: After Phase 0 acceptance, system MUST support named tactical styles that alter transition behaviour (build-up length, transition speed, press/turnover patterns, fatigue pressure) rather than only inflating shot/goal probabilities. **Not in Phase 0.**
- **FR-012**: System MUST route human tactical changes through DecisionInbox with persisted Decision-category events. **Phase 0**: application semantics remain **immediate** (NSS v2 parity) while recording window metadata. **Wave 1+**: fixed DecisionWindows (15', 30', 45', 60', 75', 85') become the authoritative apply points (requires `simulation_schema_version` bump).
- **FR-013**: System MUST route AI through BotBrain → Policy → DecisionIntent only — AI MUST NOT mutate match sporting state directly. Phase 0 MUST ship DefaultPolicy only (no Adaptive/advanced policies).
- **FR-014**: System MUST provide a manager-facing post-match explanation for bot and league matches that cites stream-derived turning events. **Rich explainability UI is post–Phase 0**; Phase 0 MAY ship projector stubs only.
- **FR-015**: System MUST keep Dixon-Coles / interval xG engine out of the live Discord path; calibration MUST live under the match engine calibration surface (not ad-hoc only).
- **FR-016**: System MUST version both the **event schema** and the **simulation schema** (`simulation_schema_version`) so older runs remain replayable under their pinned versions. **`simulation_schema_version` defines gameplay semantics**, not only data structures — any intentional change to match behaviour (DecisionWindow enforcement, transition logic, tactical routing, AI policy defaults, etc.) MUST bump it even if code packaging is unchanged.
- **FR-017**: System MUST remain testable offline via a **Golden Match Corpus** (50–100 deterministic fixtures, default exact_parity, optional documented stats_parity) plus determinism, recovery, integrity, and performance gates; every engine change MUST pass the corpus before merge (SC-008/SC-009/SC-011).
- **FR-018**: Phase 0 MUST deliver architectural parity only (no intentional gameplay behaviour change) including: step core, MatchContext, Possession aggregate, possession-boundary flush, DecisionInbox with window metadata and **immediate** decision apply (v2 parity), event categories (Sporting / Decision / Administrative; Projection never replay inputs), three digests (FR-021), thin BotBrain→Policy, Replay projector interface/stub, package `contracts/` and `calibration/`, Golden Corpus, quantified acceptance gates, dual-run readiness. Fixed DecisionWindow **enforcement** (15/30/45/60/75/85), new tactical transition profiles, Adaptive AI, advanced policies, rich explainability UI, and player-traits expansion are **not** Phase 0.
- **FR-019**: Match events MUST be categorized; **Projection-category artifacts MUST never be replay inputs** (replay uses Sporting + Decision + Administrative only).
- **FR-020**: System MUST expose a Replay projector interface (timeline-capable) so future Discord/website replay UIs consume projections without changing the simulator.
- **FR-021**: System MUST compute three versioned digests — **Sporting Digest** (cross-version gameplay compare), **Deterministic Replay Digest** (v3 self-replay/recovery), and **Settlement Digest** (progression integrity). Projection events MUST NOT enter Sporting or Replay digests as authoritative inputs; scaffolding (possession-boundary markers, replay checkpoints, internal-only transitions) MUST NOT enter the Sporting Digest.

### Key Entities

- **Match Run**: Durable identity for a simulation instance (type, seed, `engine_version`, `simulation_schema_version`, status, participants, optional fixture link).
- **Match Context**: Immutable read model of the match at a point in time (score, minute, momentum, fatigue snapshots, formations, active tactics, current Possession, weather if used).
- **Possession**: First-class aggregate spanning one or more phases — owner side, started/ended minute, end reason, nested sporting events; natural flush and replay boundary.
- **Decision Context**: Read-only view used by human UI or Policy to choose actions (phase, possession, recent events, legal actions, open DecisionWindow).
- **DecisionWindow**: Fixed match-minute apply points (15', 30', 45', 60', 75', 85') — **metadata in Phase 0**; **authoritative enforcement in Wave 1** (schema bump).
- **DecisionInbox**: Pending human/AI intents with validate → collapse → apply semantics (not an unbounded FIFO queue of duplicate effects).
- **Match Event**: Versioned, ordered, append-only record with category Sporting | Decision | Administrative | Projection; sporting SoT excludes Projection from replay inputs.
- **Decision Record**: Accepted human or AI choice at a DecisionWindow; stored as Decision-category events.
- **Event Projection**: Derived views (box score, commentary inputs, explainability, **replay timeline**) rebuilt from non-Projection events.
- **BotBrain / Policy**: Brain selects/invokes a Policy; Policy emits DecisionIntent; DefaultPolicy only in Phase 0.
- **Tactical Style**: Named transition profile — **post–Phase 0**.
- **Engine Version Pin / Simulation Schema Version**: Ensure a run finishes on the same engine package ruleset and simulation schema it started with.
- **Golden Match Fixture**: Corpus entry with inputs (seed, squads, tactics, match type), parity class (exact_parity default | stats_parity + documented architectural reason), and expected Sporting Digest, Deterministic Replay Digest, Settlement Digest, score, scorers/assists, injuries, cards, key stats.
- **Sporting Digest / Deterministic Replay Digest / Settlement Digest**: Formal deterministic hashes over defined event/settlement subsets (FR-021); recipes are versioned so scaffolding can evolve without weakening sporting gates.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Deterministic Replay Digest identity **100%** — seeded silent replays (N ≥ 100 CI seeds + full Golden Corpus) produce identical Deterministic Replay Digests (and scores) on repeat runs / recovery / silent sim.
- **SC-002**: Recovery identity **100%** — interrupted-run completion matches clean replay score and critical event set for every Golden Corpus recovery fixture.
- **SC-003**: Integrity matrix **100%** — settle-once / friendly sandbox / lock checks remain green after V3 cutover for each match type.
- **SC-004**: CPU **< 50 ms** silent full-match on CI reference hardware (no Discord I/O); memory **< 5 MB** for one in-process sim + event buffer (excluding Discord client).
- **SC-005**: After tactical styles ship (post–Phase 0), blind A/B identifies Possession vs Counter above 80% accuracy on a fixed seed batch.
- **SC-006**: ≥80% playtest managers identify the primary turning event from rich explainability UI (post–Phase 0 gate).
- **SC-007**: Zero production double coin/XP incidents attributable to V3 dual-run/cutover in first 14 days post-enable.
- **SC-008**: Phase 0 Golden Corpus gates — **exact_parity** (default; ≈80–90%): **100%** match on **Sporting Digest**, sporting-core event order, final score, scorers/assists, injuries, cards, and **Settlement Digest** vs baseline. **stats_parity** (documented architectural reason only): identical final score, winner/draw, and Settlement Digest; Monte Carlo: win-rate drift **<2 pp**, possession drift **<3 pp**, shot-count drift **<5%**, average goals/match drift **<2%**. Deterministic Replay Digest validity **100%** for v3 self-replay on all fixtures.
- **SC-011**: Corpus classification hygiene — every stats_parity fixture MUST cite an architectural reason in its fixture metadata; unmarked fixtures default to exact_parity and fail CI if they only pass looser stats gates.
- **SC-009**: Golden Match Corpus has **50–100** fixtures (even/underdog, morale extremes, formations, injury, bot/league/friendly, interruption recovery); every merge touching the match engine MUST pass the corpus.
- **SC-010**: Projection artifacts never appear in replay input sets (**100%** of corpus replay tests).

---

## Assumptions

- **Phase 0 = architectural parity only**: No intentional gameplay behaviour change. New tactical transition profiles, Adaptive AI, advanced policies, rich explainability UI, and player-traits expansion are **out of Phase 0**.
- **Phase 0 mandatory architecture**: `simulation_schema_version`, Possession aggregate, possession-boundary flushing, DecisionInbox + window metadata with **immediate** apply, event categories (Projection excluded from replay inputs), three digests, thin BotBrain→Policy, Replay projector stub, `contracts/` and `calibration/` surfaces, Golden Corpus (50–100), quantified gates, dual-run / `engine_version` pin. Fixed DecisionWindow enforcement is **Wave 1**.
- **Realism is subordinate** to determinism, replay, explainability, recovery, testability, and extensibility.
- **NSS v2 Markov phases** remain the Phase 0 behavioural baseline; later waves may retune transitions and bump simulation_schema_version.
- **Touchline Attack/Balanced/Defend** maps into DecisionInbox + DecisionWindows without new TransitionProfiles in Phase 0.
- **Weather** optional/unused in Phase 0.
- **Friendly** sandbox unchanged; durable events default off for friendlies.
- **Dixon-Coles** lives under calibration surface; never live Discord path.
- **Planning pack** under this feature is updated by clarifications where they supersede earlier defaults (possession-boundary flush; DecisionWindows over cooldown-only).
- **US-42 / constitution** remain binding.

---

## Scope Boundaries

### In scope

- Phase 0 architectural platform (FR-018) with gameplay **parity** objective.
- Dual-run / version pinning (engine_version, simulation_schema_version).
- Golden Match Corpus as merge gate.
- Post–Phase 0: tactical transition profiles, richer policies, rich explainability (separate acceptance).

### Out of scope

- Intentional gameplay rebalance during Phase 0.
- New tactical transition profiles, Adaptive AI, advanced policies, rich explainability UI, player-traits expansion (**not Phase 0**).
- Merging Dixon-Coles into live Discord matches.
- Rewriting economy, XP, fatigue, or league standings formula ownership.
- New slash commands beyond extending existing \/battle\ / league play surfaces as needed.
- Machine-learning training infrastructure.
- Pixel-perfect new pitch renderer.
- Breaking friendly sandbox or inventing competitive rewards for friendlies.

---

## Dependencies

- `033-match-integrity` (locks, settle-once, match types, recovery).
- NSS v2 production path (`stream_match` / battle orchestration) as behavioural baseline.
- Injury/fatigue intensity rules (`002`/`016`) for injury event semantics.
- Economy v2 / progression pipes for post-match settlement unchanged in ownership.
- League lifecycle auto-sim must call the same step engine after cutover.

---

## Planning Deliverables Gate *(mandatory before implementation)*

Implementation MUST NOT start until `/speckit.plan` (or equivalent architecture pack) completes and is internally consistent for:

1. Current architecture review (strengths, weaknesses, debt)
2. Gap analysis NSS v2 → V3
3. Domain model (aggregates, entities, value objects, events, repos/services)
4. Event model (fields, ordering, versioning, replay, idempotency)
5. Database design (if any) with concurrency, indexes, rollback
6. Public API design (simulation, events, AI, commentary)
7. Migration / dual-run strategy
8. Testing strategy (replay, property, probability regression, perf, concurrency, recovery, migration, fuzz)
9. Risk analysis per subsystem
10. Performance analysis (CPU, memory, writes, event growth)

These are planning artifacts, not substitute for this specification’s user-facing requirements.
