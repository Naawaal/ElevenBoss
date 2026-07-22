# Feature Specification: Hub Hot-Path Wave 2 (Squad / League / Profile)

**Feature Branch**: `039-hub-hot-path-wave2`

**Created**: 2026-07-22

**Status**: Implemented (2026-07-22)

**Parent / Related**: [`038-db-scalability-performance`](../038-db-scalability-performance/spec.md) (US-43) — extends Phase 1 hot paths HP-4…HP-6. Integrity: US-42.5 (no sporting forfeit from infra), US-42.7/42.9 (no parallel coin/XP pipes).

**Input**: Continue US-43 patterns on remaining hubs: `/squad`, `/league hub`, `/profile` (and light touch on related read paths). Create a proper Speckit feature package before code. Prefer measure → gather/batch/cache → hub_timer; no Redis; no new slash commands.

**US citation**: **US-44** (child of US-43 scalability constitution). Mutating PRs cite **US-44 + US-43**; league paths also cite **US-42.5** where pause/resume/auto-sim touch integrity.

---

## 0. Framing

### 0.1 Purpose

Managers opening **Squad**, **League Hub**, and **Profile** get the same responsiveness gains already shipped for Development / Training Drills / Store: fewer sequential remote round-trips, cached non-sensitive reads, and observable hub latency — without changing gameplay outcomes or inventing caches for live balances / exclusive match state.

### 0.2 In scope

| ID | Surface | Entry | Approach |
|----|---------|-------|----------|
| HP-4 | Profile | `profile_cog.show_profile` | Gather independent reads; TTL-cache `global_divisions`; reuse energy-line pattern from US-43 |
| HP-5 | Squad open | `squad_cog.fetch_squad_data` | `asyncio.gather` independent selects; count cards without pulling full id lists |
| HP-6 | League hub | `league_cog.league_hub` / `show_hub` / `build_hub_embed` | Parallel guild+league load; batch/cache join-gate config; skip redundant reg counts; **keep** auto-sim / pause-resume live |

### 0.3 Out of scope (this wave)

- New slash commands, hub buttons, or tables
- Shared Redis / multi-instance cache (still US-43 Phase 3)
- Marketplace / leaderboard full rewrite (may get a follow-up if measured) → **done in** [`040-hub-hot-path-wave3`](../040-hub-hot-path-wave3/spec.md) (US-45)
- Collapsing league auto-sim into a cached “fast hub” that skips settle work
- New dashboard RPCs unless gather/batch cannot meet SC-004 (YAGNI)

### 0.4 Non-negotiables

- Constitution Principle II — no `asyncpg`; mutations stay on existing RPCs
- US-42.5 — hub open must not invent match results or skip pause/resume when guild is reachable
- Live inventory, coins, energy after sync, match locks, season status: **not** TTL-cached as source of truth
- Defer interactions immediately (existing pattern)

---

## Clarifications

### Session 2026-07-22

Inherited from US-43:

1. Principle II kept (RPC / PostgREST shells).
2. Economy-priced `cfg:*` need shared/active invalidation under multi-instance — this wave only uses process cache for **non-priced** join gates + **global_divisions** rows.
3. Idempotent Outcome Contract unchanged (no new mutators required for open-hub reads).

Wave-2 specific:

- Q: Skip auto-sim on hub open for speed? → **A: No** — integrity over RT on that branch; optimize surrounding reads only.
- Q: New consolidated SQL RPC for squad/league dashboard? → **A: Not in MVP** — gather + count + config batch first; RPC only if SC-004 fails after measure.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — League hub feels snappier (Priority: P1)

As a manager, when I run `/league hub`, the Seasonal League Hub appears promptly with the same correct status (registration / active / paused resume / no season).

**Independent Test**: Source await-count on `league_hub` + `build_hub_embed` drops ≥50% on the *configurable* slice (join limits + parallel guild/league); Discord smoke shows correct embed; paused seasons still resume when guild reachable.

**Acceptance Scenarios**:

1. **Given** an active season, **When** the manager opens `/league hub`, **Then** they see current matchday UI without missing auto-sim of expired windows.
2. **Given** registration open, **When** they open the hub, **Then** entry fee / join limits match `game_config` (cached or batched, not stale beyond TTL).
3. **Given** a paused season and reachable guild, **When** they open the hub, **Then** resume behavior from US-37 still applies (not skipped for speed).

### User Story 2 — Squad opens with fewer waits (Priority: P1)

As a manager, `/squad` loads formation, XI, reserves count, and lock state without five serial round-trips.

**Independent Test**: `fetch_squad_data` uses concurrent fetches; card total uses count (or equivalent) not full id dump; pitch UI unchanged.

**Acceptance Scenarios**:

1. **Given** a registered club with XI + reserves, **When** they open `/squad`, **Then** embed matches pre-change data (formation, assignments, reserves, lock, invalid flag).
2. **Given** match lock active, **When** they open squad, **Then** locked UI still shows.

### User Story 3 — Profile refreshes faster (Priority: P2)

As a manager, `/profile` shows finance, hospital, energy, and division progress with fewer serial reads; division ladder table is not re-fetched every open within TTL.

**Independent Test**: Warm second profile open does not re-query `global_divisions`; coins/energy still live from player row + energy sync.

**Acceptance Scenarios**:

1. **Given** a registered manager, **When** they open `/profile` twice within TTL, **Then** division progress is consistent and second open avoids divisions RT.
2. **Given** hospital patients, **When** they open profile, **Then** hospital summary still accurate (live query).

---

## Requirements

### Functional

- **FR-001**: Instrument HP-4…HP-6 with `perf_signals.hub_timer` (names `profile`, `squad`, `league_hub`).
- **FR-002**: Parallelize independent PostgREST reads on HP-5 and HP-6 loaders via `asyncio.gather`.
- **FR-003**: Replace sequential `get_game_config` pair in `_league_join_limits` with `get_game_config_many` / cached int helpers.
- **FR-004**: Cache `global_divisions` rows process-locally (TTL ≤10 min) behind an explicit key; invalidate via prefix clear on admin mutation if such path exists (else TTL backstop).
- **FR-005**: Squad card inventory count MUST NOT fetch every card id solely to compute `len` when a count query suffices.
- **FR-006**: League hub MUST retain auto-sim-on-open for non-`lifecycle_v1` seasons and pause/resume integrity paths.
- **FR-007**: No new slash commands, hub buttons, or tables in this wave.
- **FR-008**: Update US-43 `hot-path-catalog.md` After RTs for HP-4…HP-6; keep `039` contracts as SoT for wave-2 acceptance.

### Success criteria

- **SC-001**: Source or scratch baseline shows ≥50% reduction on countable sequential RTs for each of HP-4…HP-6 vs pre-wave estimates (5 / 5 / 8), or wall-clock hub_timer p95 ≤2s under light load when ops validates.
- **SC-002**: Pytest covers gather/count contracts and divisions cache hit; no Discord import under `packages/`.
- **SC-003**: Persona walkthrough: manager double-open hub, locked squad, paused league — no wrong balances or skipped resume.

---

## Assumptions

- Single bot instance (US-43 Phase 1–2 default).
- `get_game_config_many` (migration 081) already applied in environments that run the bot.
- Join-gate keys are non-priced (eligibility, not shop math) — process TTL OK under multi-instance per US-43 FR-012.

---

## Dependencies

| Dep | Why |
|-----|-----|
| US-43 `config_cache`, `economy_rpc.get_game_config_many`, `perf_signals` | Reuse — do not fork |
| US-37 pause/resume | Must not regress |
| Indexes from mig 080 | League fixtures already covered |

---

## Checklist pointers

- [ ] Spec + plan + tasks exist under `specs/039-hub-hot-path-wave2/`
- [ ] `.specify/feature.json` points at this feature while active
- [ ] `.specify/specs/v1.0.0/plan.md` links US-44
- [ ] Hot-path catalog updated after implement
- [ ] `change_log.md` player-facing blurb if UX snappiness ships
