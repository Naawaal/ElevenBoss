# Research: Ranked PvP Matchmaking and Manager Rivalries

**Feature**: `053-pvp-matchmaking-rivalries`  
**Date**: 2026-08-04  
**Status**: Complete — Technical Context unknowns resolved against live battle/Friendly/LP code and `spec.md`.  
**Migration head**: **097** → reserve **098**.  
**Implementation**: Blocked on Feature 052 ACCEPT ([GATE.md](./GATE.md)).

---

## R1 — Reuse Friendly dual-human stadium vs new engine

**Decision**: Orchestrate Ranked PvP on existing V3 match-engine streaming, pitch/commentary handlers, squad snapshots, `match_runs`, injury presentation, and Friendly-style guild thread creation. Extract shared setup into `apps/discord_bot/core/pvp_match.py` rather than cloning `start_friendly_match`.

**Rationale**: Spec §3 / FR-009; `battle_cog.py` already runs bot + friendly + league through the same simulation surface. A second football engine violates YAGNI and US-42 integrity.

**Alternatives considered**:
- New PvP engine package — out of scope / forbidden.
- Force Friendly to become ranked — breaks sandbox contract (FR-013).

**Audit notes**:
- Hub today: `ArenaHubView` → Bot Battle + Friendly tip to `/battle friendly`.
- Bot: `execute_bot_battle` → `run_type="bot"`, `apply_bot_match_rewards`, **applies Global LP** via `global_lp_delta` + `increment_match_career_stats`.
- Friendly: `start_friendly_match` → thread from invite message, dual `acquire_match_lock(..., "friendly")` (not sorted), `run_type="friendly"`, no economy/XP/LP.
- Touchline / live tactics exist for bot (V3 inbox); MVP Ranked PvP is **watch-only** (no mid-match dual tactical buttons).

---

## R2 — `match_runs` / lock types for `pvp` and `practice`

**Decision**: Extend CHECK constraints (do not create a second run table):

- `match_runs.run_type`: add `'pvp'`, `'practice'` (keep `'bot'` for rollback soak).
- `match_locks.lock_type` + `acquire_match_lock` validation: add `'pvp'`, `'practice'`.
- Engine config keys: `match_engine_v3_pvp`, `match_engine_v3_practice` (mirror friendly/bot flags).

**Rationale**: Migration 019 defines `run_type IN ('bot','friendly','league')`; 011/047 lock types match. Spec §17.5 requires extending the run model.

**Alternatives considered**:
- Overload `bot` for Practice — conflates rollback and competitive LP leakage risk.
- Overload `friendly` for Ranked — destroys sandbox semantics.

---

## R3 — Global LP: only Ranked PvP

**Decision**:

1. `finalize_pvp_match` is the only battle path that applies non-zero Global LP (SQL-enforced).
2. `finalize_ai_practice_match` forces `global_lp_delta = 0`, skips rivalry, skips competitive PvP career counters.
3. While `battle_pvp_enabled`, hub primary CTA is Find Opponent; AI Practice uses Practice finalize — **legacy bot path that still writes LP must not remain the live Practice path**.
4. Rollback: flag off restores legacy Bot Battle presentation/path for soak window.

**Rationale**: FR-010 / SC-002. Today `apply_bot_match_rewards` always passes `p_lp_change` — that is the regression to eliminate for Practice.

**Pure helpers**: Keep `packages/leagues/leagues/match_points.py` as base deltas; extend with provisional loss reduction + optional relative-rating adjustment used by finalize (Python mirrors SQL). Spec provisional: first N ranked matches (default 5) reduced LP loss, normal gain.

**Alternatives considered**:
- Soft “Practice still awards LP but less” — violates core product rule.
- Client-computed LP posted to RPC — rejected (anti-cheat FR-011).

---

## R4 — Queue ownership and matchmaker

**Decision**: DB-owned queue (`pvp_matchmaking_queue`) with statuses `searching|matching|matched|cancelled|expired`. Bot APScheduler job every **5s** calls `try_match_pvp_queue` (SKIP LOCKED); also invoke claim immediately after successful `join_pvp_queue`. Energy is **not** charged on join.

**Rationale**: FR-003–006; survives bot restart (queue rows in Supabase). Interval matches constitution V (APScheduler).

**Pair scoring (pure)**: longest wait → smallest division gap → smallest LP gap → smallest XI OVR gap, after widening bands by queue age.

**Lock order**: When claiming, acquire match locks by **sorted** `(manager_a, manager_b)` discord IDs to avoid deadlock (Friendly today acquires challenger then opponent — improve for PvP).

**Alternatives considered**:
- In-memory only queue — lost on restart; fails FR recovery stories.
- Separate Redis worker — gated advanced infra; not MVP.

---

## R5 — Same-guild only

**Decision**: Matcher requires identical `guild_id` on both queue rows. Cross-server deferred indefinitely for MVP.

**Rationale**: Spec locked decision 5.1 — one Discord stadium thread both managers can see.

---

## R6 — Anti-win-trading (MVP)

**Decision** (enforced in SQL at claim + finalize):

| Rule | Default |
|------|---------|
| Same-pair ranked cooldown | 30 minutes |
| Same-pair rewarded ranked / UTC day | 2 |
| Per-manager rewarded ranked / UTC day | 5; then **cannot requeue** until reset |
| Bidirectional `pvp_blocks` | exclude from match + Friendly invite |
| No ranked direct challenge | Friendly only for direct invite |
| Immutable squad snapshots at claim | seed server-generated |
| Abandoned pre-kickoff | zero economy/LP |

**Rationale**: Spec §9 / §21; safer MVP avoids “ranked but unrewarded” mode.

---

## R7 — Rivalry model

**Decision**: Canonical pair `(manager_a_id, manager_b_id)` with `a < b`. Status `tracking → active` after 3 ranked meetings within 30 days; `dormant` after 60 days without ranked meeting; history never deleted. Events computed in `packages/pvp/rivalry_math.py` and returned from `finalize_pvp_match` (no separate event table unless proven necessary). Recent five matches queried from `match_history` by pair + `match_type='pvp'`.

**Rationale**: FR-015–016; presentation-only callouts.

**Alternatives considered**:
- Manual Declare Rivalry — out of scope.
- Event table first — YAGNI until analytics need it.

---

## R8 — Badges (spec vs repo)

**Finding**: Spec assumes reuse of badge/achievement architecture. Repo has **league trophy cabinet** (`player_league_history`) only — no general badge table.

**Decision**: Honor “no new badge table” by:

1. Computing rivalry badge eligibility from rivalry stats + finalize events in pure math.
2. Persisting earned personal badge keys on `players.pvp_badge_keys text[]` (or jsonb) updated inside finalize when newly earned.
3. Displaying under Rivalries / profile competitive section — **no gameplay bonuses**.

**Alternatives considered**:
- New `manager_badges` table — cleaner long-term but contradicts proposal “no new badge table”; revisit only if array/json becomes painful.
- Fake reuse of `player_league_history` — wrong domain.

---

## R9 — AI Practice reward policy

**Decision** (config-tunable; SQL + `reward_policy.py`):

| Cohort | Energy | Coins/XP vs legacy bot | Daily rewarded Practice | LP / rivalry / PvP record |
|--------|--------|-------------------------|-------------------------|---------------------------|
| New (below onboarding match count) | 10 | 75% | (onboarding may count) | 0 |
| Established | 10 | 50% | 2 / UTC day | 0 |

Ranked PvP energy default **20**; coin multipliers win/draw/loss **1.25 / 1.10 / 1.00** vs current bot-division rewards.

**Rationale**: Spec §12; must never escalate `practice` → `pvp` from client.

---

## R10 — Scheduler registration

**Decision**: Register `pvp_matchmaker_job` in `apps/discord_bot/main.py` via `scheduler.add_job(..., "interval", seconds=5)` (or config `pvp_matchmaker_interval_seconds`). Use existing job-claim patterns where multi-instance risk exists (`job_claims` / SKIP LOCKED inside RPC).

**Audit**: Jobs today live in `main.py` imports from `core/scheduler_jobs.py` and task modules — follow same pattern with `tasks/pvp_matchmaker_job.py`.

---

## R11 — Match history shape

**Decision**: Extend `match_history` with `opponent_owner_id`, `match_type`, `global_lp_delta`, `rivalry_counted` (defaults safe for legacy rows). PvP writes **two** history rows linked by same `run_id`. Practice/Friendly set `global_lp_delta=0` and `rivalry_counted=false`.

**Rationale**: Spec §17.6; bot path today inserts history without match_type — backfill default `'bot'` for old rows.

---

## R12 — Feature flags

**Decision**: Authoritative DB `game_config.battle_pvp_enabled` (default false). Env alias `BATTLE_PVP_ENABLED` may mirror for ops but gameplay reads DB. Subflags: `pvp_rewards_enabled`, `pvp_rivalries_enabled`, `pvp_rivalry_dms_enabled`, `pvp_server_leaderboard_enabled`, `ai_practice_rewards_enabled`.

**Rationale**: Spec §19 / FR-019 rollback.

---

## R13 — Implementation gate (052)

**Decision**: Plan and tasks docs allowed now; **no** apply of 098 to production, no hub CTA live, no soak Stage 2+ until 052 ACCEPT. Shadow-mode pairing simulations may run against clones after schema lands in a feature branch.

**Rationale**: User-locked gate; YA soak still CONDITIONAL PASS.

---

## Resolved NEEDS CLARIFICATION

None remaining for planning. Product numbers taken from approved `spec.md` assumptions.

---

## Phase 1 live audit (T001–T004) — 2026-08-04

Executed under `/speckit.implement` Phase 1 only. **Phase 2+ not started** — Feature 052 still CONDITIONAL PASS.

### T001 — `battle_cog.py`

| Surface | Finding |
|---------|---------|
| Hub | `ArenaHubView`: **🤖 Bot Battle** → `execute_bot_battle`; **Friendly** tip → `/battle friendly` |
| Commands | `/battle hub`, `/battle bot`, `/battle friendly` (guild_only) |
| Bot path | Lock `bot` → energy check (`get_match_energy_cost(..., "bot")`) → XI gates → V2/V3 stream → `apply_bot_match_rewards` with **`global_lp_delta`** via `increment_match_career_stats` |
| Friendly | `ChallengeView` → `start_friendly_match`: thread from invite, dual locks **challenger then opponent** (unsorted), `run_type="friendly"`, no economy/XP/LP |
| Reuse targets | `StandardMatchHandler`, commentary loop, `create_ephemeral_run`, injury handler, TouchlineView (bot only — PvP MVP watch-only) |
| Size | ~2480 lines; stadium logic still in-cog — extract to `core/pvp_match.py` as planned |

**Drift vs plan**: None blocking. Hub CTA rename + Practice conversion still required for US1/US3.

### T002 — match runs / rewards / economy

| Helper | Contract to preserve |
|--------|----------------------|
| `create_ephemeral_run` | `run_type`, home/away discord ids, seed, guild/thread, optional `squad_snapshot`, engine pins |
| `resolve_engine_version` | Keys today: `match_engine_v3_bot/league/friendly` — add `pvp`/`practice` |
| `mark_completing` / `complete_run` / `abandon_match_run` | Restart + lock release via RPC |
| `fetch_match_reward_row` + xp/fatigue stamps | Idempotent bot rewards |
| `apply_bot_match_rewards` | Economy + career LP + history insert + XP + fitness — **must not** be the live Practice path when flag on |
| `apply_match_economy` / `compute_bot_match_coins` | Extend for `pvp`/`practice` energy keys in `_MATCH_ENERGY_CONFIG_KEY` |

`match_history` today: base cols + `run_id`, `xp_applied_at`, `fatigue_applied_at`, `fixture_id`. **Missing** plan cols: `opponent_owner_id`, `match_type`, `global_lp_delta`, `rivalry_counted`.

### T003 — locks / LP / scheduler

| Area | Finding |
|------|---------|
| Locks | `acquire_match_lock(discord_id, lock_type)` — SQL allows only `friendly\|league\|bot` (011 CHECK + 047 validate). **Must extend for `pvp`/`practice`** |
| Friendly deadlock risk | Unsorted dual acquire — PvP must sort IDs |
| LP | `global_lp_delta` / `clamp_global_lp` flat ±15/5/−10 — extend provisional/relative in US2 |
| Scheduler | All jobs registered in `apps/discord_bot/main.py` via `add_job` — add interval matchmaker the same way; no PvP job yet |
| Badges | Still no general badge table — R8 (`pvp_badge_keys`) stands |

### T004 — migration head + touch list

- Latest migrations: **095, 096, 097** — **098** still correct reservation.
- `packages/pvp/` **does not exist** yet.
- Existing packages with `pyproject.toml`: economy, energy, gacha, leagues, match_engine, player_engine — new `packages/pvp` should mirror that pattern.
- Plan source tree still accurate; no rename required.

### Implement halt

`/speckit.implement` stops after Phase 1. Resume at **T005** only when `specs/052-youth-academy-v2-acceptance/acceptance-record.md` decision is **ACCEPT**.
