# Research: League Rulebook and Autonomous Lifecycle Engine V1

**Date**: 2026-07-21  
**Purpose**: Resolve design unknowns for plan Phase 0; map research-backed rulebook onto ElevenBoss monorepo constraints.

---

## 1. Audit — what already exists

| Piece | State |
|-------|--------|
| Seasonal league tables | `leagues`, `league_members`, `league_seasons`, `league_participants`, `league_fixtures` (007+) |
| Dynamics (020) | `pacing_mode`, UTC midnight windows, 8/tier, MoMD, promo RPC, `resolved_by` |
| Automation (021) | `league_state_machine_job` 00:05 UTC; registration open/close; announce digests; shared `start_dynamics_season_from_registration` |
| Standings | Computed from fixtures (`fetch_standings`); no immutable final table |
| Match locks / runs | `match_locks`, `match_runs` with fixture FK |
| Economy | Entry fees `charge_league_entry_fees`; prizes `distribute_season_prizes`; coins via `apply_club_economy` |
| Weekly ladder | `players.league_points` — **must stay decoupled** |
| Time handling | Dynamics assumes UTC midnight; no guild IANA timezone column |

**Gap**: No frozen ruleset/engine versions; no matchday entity; no operation journal/outbox; season statuses collapse cancel into completed; assistant repair is ad-hoc auto-sim, not a documented lineup priority; no guild-local resolution hour; dual conceptual engines (020 tick + 021 automation) instead of one rulebook executor.

---

## 2. Decisions

### D1 — Clarifications (locked)

| ID | Decision | Rationale |
|----|----------|-----------|
| Q1 | Guild IANA timezone + local resolution hour in V1; freeze + precompute UTC windows at preparation | Foundational; retrofit would touch schedule, reminders, pause/resume, recovery |
| Q2 | 0–0 double forfeit, 0 points, MP+1/L+1 both; not draw/clean sheet/unbeaten/appearance/promo-eligible | Prevents intentional illegal-squad collusion |
| Q3 | Feature-flagged exclusive per-guild cutover; one final rule path; 021 → thin wake-up | Avoid permanent dual modes; safe grandfather + rollback = stop new V1 seasons |

### D2 — DST ambiguous / nonexistent local times

**Decision**:  
- **Gap** (spring forward): use the first valid local time **after** the gap.  
- **Overlap** (fall back): use the **earlier** (DST) offset occurrence.  
Document both in the season `ruleset_snapshot`.

**Rationale**: Deterministic, matches common “prefer DST / skip missing” operational practice; must be identical in Python `zoneinfo` and any SQL generation helpers.

**Alternatives**: Always UTC midnight — rejected (Q1). Post-gap vs pre-gap for overlap — earlier offset chosen for stability across libraries.

### D3 — Schedule storage

**Decision**: Store on season: `timezone` (IANA), `resolution_hour_local` (0–23), `ruleset_version`, `engine_version`, `ruleset_snapshot` (JSONB). Precompute per-matchday (and per-fixture) `window_start`/`window_end` UTC at preparation. Never recompute from live guild settings.

**Rationale**: FR-006; SC-007 pause/resume rebases from stored windows, not live config.

**Alternatives**: Recompute from guild settings each tick — rejected (settings drift mid-season).

### D4 — Lifecycle engine placement

**Decision**: Pure transition predicates and math in `packages/leagues`. Orchestrator `LeagueLifecycleEngine` in `apps/discord_bot/core/` performs DB IO + RPC calls. Scheduler only calls `process_due_transitions(now)` (+ outbox flush + recovery).

**Rationale**: Constitution I (no Discord in packages); FR-033; YAGNI vs a new microservice.

**Alternatives**: Put engine in packages with injected DB port — more abstraction than needed for one bot.

### D5 — Status model vs legacy columns

**Decision**: Expand `league_seasons.status` check constraint to V1 statuses (`dormant`, `registration_open`, `registration_locked`, `preparing`, `active`, `paused`, `settling`, `completed`, `cancelled`, `failed`). Map grandfather 020/021 rows: `registration`→`registration_open`, existing `active`/`paused`/`completed` unchanged semantics; never rewrite living windows.

**Rationale**: Spec FR-008 forbids labeling cancel as completed.

**Alternatives**: Parallel `lifecycle_status` column — rejected (two sources of truth).

### D6 — Matchday + fixture states

**Decision**: New `league_matchdays` table (season_id, matchday_number, window_*, status). Extend fixtures with `result_type` (`settled` | `forfeit` | `double_forfeit` | `void`) and non-terminal processing flags as needed; keep `is_played` for backward-compatible reads during cutover.

**Rationale**: Spec matchday SM + terminal fixture invariant; enables MoMD/settlement without scanning only fixtures.

### D7 — Exactly-once operations

**Decision**: `league_operation_runs` with unique `operation_key` (e.g. `season:{id}:prepare`, `fixture:{id}:settle`). Transition journal rows for audit. Outbox for Discord publishes keyed separately so Discord failure cannot roll back sporting settle.

**Rationale**: FR-034–FR-037; SC-003/SC-004.

**Alternatives**: Rely solely on economy ledger keys — insufficient for non-coin transitions (registration close, promo).

### D8 — Assistant manager V1 scope

**Decision**: V1 assistant operates on **existing squad / saved league lineup / submitted matchday plan** fields already in product. Priority: submitted → saved league → repair (injuries/suspensions/empty slots, preferred formation) → emergency legal XI → forfeit. No new slash command for “assistant settings.”

**Rationale**: FR-017–FR-019; Ponytail.

**Alternatives**: Full FM-style opponent instructions UI — out of scope.

### D9 — Cutover flag shape

**Decision**: Global `game_config.league_lifecycle_v1_enabled` + per-guild `guild_config.league_lifecycle_v1_enabled` (NULL inherit / true / false). Effective cutover only when flag on **and** no living non-V1 open season (or after that season completes). New season creation under cutover always writes `ruleset_version=league-v2.0` (or `lifecycle-v1`) and `engine_version`.

**Rationale**: Q3; rollback disables new V1 creation without mutating active V1 seasons.

### D10 — Wake-up cadence

**Decision**: ~**5 minute** interval job + **startup recovery pass**. Prefer catch-up over precise 00:05-only ticks because guild-local hours differ.

**Rationale**: Spec scheduler design; guild TZ means midnight UTC job is insufficient alone.

**Alternatives**: Keep only 00:05 UTC — rejected under Q1.

### D11 — MoMD and prizes

**Decision**: Retain MoMD as optional in-ruleset award if already present for Dynamics continuity, but settlement path must be invoked from lifecycle matchday completion (not a separate competitive brain). Prize RPC remains `distribute_season_prizes` or a V1 successor that understands double_forfeit and immutable finals — prefer extend with result_type awareness over parallel prize systems.

**Rationale**: One settlement path; YAGNI on inventing a second prize pipe.

### D12 — Relation to Weekly Division Rank

**Decision**: Unchanged. League settle path must not call `increment_match_career_stats` with ladder point deltas; use league-career or fixture-only aggregation as today for seasonal matches.

**Rationale**: FR-007; existing design guide.

---

## 3. Risks

| Risk | Mitigation |
|------|------------|
| DST edge cases differ between Python and docs | Single pure helper + golden tests for Asia/Kathmandu, America/New_York spring/fall |
| Dual code paths during rollout | Cutover exclusive; grandfather only; delete/disable Dynamics start for cutover guilds |
| Partial settle + Discord down | Sporting commit first; outbox retry; never forfeit for Discord |
| Admin Start vs engine race | Shared transition API; hide duplicate buttons when automation/cutover owns happy path |
| Large catch-up after outage | Process due items in order per season; lease per operation key |
| Status migration breaks old checks | Explicit mapping + verify_required_schema; smoke on grandfather season |

---

## 4. Open items deferred to tasks (not clarifications)

- Exact default `resolution_hour_local` when guild has never configured (recommend **20** local or **00** — pick in tasks with product default **20:00 local**).
- Whether MoMD coins remain identical under V1 (assume yes unless economy calibration says otherwise).
- Minimum eligible fixtures for promotion (numeric threshold) — default **7** of 14 in tasks unless sims say otherwise.
