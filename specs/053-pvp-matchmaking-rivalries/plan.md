# Implementation Plan: Ranked PvP Matchmaking and Manager Rivalries

**Branch**: `053-pvp-matchmaking-rivalries` (docs on `main` until implement branch) | **Date**: 2026-08-04 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/053-pvp-matchmaking-rivalries/spec.md`

**US citation**: **US-42.4** (match integrity / dual finalize / locks) · **US-42.7** (economy — coins/energy via `apply_club_economy`) · **US-42.9** (DB invariants — Practice/Friendly cannot write LP or rivalry). Aligns Global LP ladder with human competition only. Extends existing `/battle` Friendly dual-human stadium patterns.

**Implementation gate**: [GATE.md](./GATE.md) — Feature **052** formal **ACCEPT** required before migration apply, bot wiring, or production flag enable. This plan may exist earlier; **coding is blocked**.

## Summary

Replace reward-bearing Bot Battle as the competitive `/battle` pathway with **guild-local Ranked PvP** matchmaking: queue → atomic pair claim → one shared stadium thread → deterministic V3 simulation → dual atomic finalize (coins, XP, fatigue/injuries, Global LP, career PvP stats, rivalry update). Convert Bot Battle into **AI Practice** with capped progression and **forced zero** competitive points. Keep Friendly as the rewardless sandbox. Slice 2 adds rivalry hub, blocks/preferences, and presentation-only callouts.

**Technical approach**: New pure package `packages/pvp/` (widening, pair score, rivalry math, reward policy). Migration **098** adds queue/rivalry/block tables, extends `match_runs.run_type` + `match_locks.lock_type` for `pvp`/`practice`, history columns, `game_config` + flag `battle_pvp_enabled=false`, and atomic RPCs (`join`/`cancel`/`try_match`/`finalize_pvp`/`finalize_ai_practice`). Discord reuses Friendly stadium/playback patterns via extracted `pvp_match` orchestration + APScheduler matchmaker (~5s). No new top-level slash command.

## Technical Context

**Language/Version**: Python 3.11+ / Postgres 15+ (Supabase)

**Primary Dependencies**: `match_engine` V3 streaming, `leagues.match_points` (extend for relative/provisional LP), `economy` RPCs, discord.py hub/views, APScheduler, existing match_runs / match_lock / injury / XP helpers

**Storage**: Supabase — NEW `pvp_matchmaking_queue`, `manager_rivalries`, `pvp_blocks`; EXTEND `match_runs`, `match_locks`, `match_history`, `players` (prefs / badge keys / daily counters as needed); `game_config` keys; migration **098** (head today: **097**)

**Testing**: pytest for matchmaking widening/scoring/exclusions, rivalry activation/dormancy/events, reward-policy (only `pvp` → non-zero LP); SQL concurrency harness for double-pair / duplicate finalize; Discord E2E after 052 gate

**Target Platform**: Discord bot (Render/Linux) + hosted Supabase

**Project Type**: Monorepo gameplay feature (packages + discord_bot + migrations)

**Performance Goals**: Matchmaker interval ~5s; queue join + claim under Discord defer; finalize is one atomic RPC for both managers; no N+1 reward loops

**Constraints**: AGENTS.md monorepo/state/DB; no `discord` in `packages/`; coins via `apply_club_economy`, XP via `apply_card_xp` / `process_match_result`; no silent AI substitution; Friendly contract unchanged; guild-local only; flag-off default; YAGNI — no cross-server, live tactics, ranked direct challenge, presence alerts

**Scale/Scope**: One primary migration (098); one new package; battle hub + queue/rivalry views; one interval scheduler job; Practice conversion of bot path; soak/rollback docs

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| I. Monorepo | PASS | Matchmaking/rivalry/reward-policy math in `packages/pvp/`; hubs/views/tasks/orchestration in `apps/discord_bot/` |
| II. DB via RPC / atomic economy | PASS | Queue claim + dual finalize in SQL RPCs; energy/coins via economy pipe; no cog `players.coins` UPDATE |
| III. Typing / Pydantic | PASS | Pydantic models at package boundaries for queue snapshots, pair scores, rivalry events, reward policy |
| IV. Slash + defer | PASS | No new top-level slash; extend `/battle` group/hub buttons; defer immediately |
| V. APScheduler | PASS | New interval matchmaker job registered like existing jobs; DB claim ownership for multi-instance safety |
| VI. Friendly errors | PASS | Map queue/eligibility/cap/block errors to ephemeral copy via `api_errors` |
| VII. YAGNI | PASS | Reuse stadium/Friendly/run/lock/XP; no new engine; rivalries are presentation + stats, not sim modifiers |

**Post-Phase 1 re-check**: PASS — `packages/pvp` justified (pure widening/events must be unit-tested without Discord). Dual-manager finalize RPC justified (cannot loop two sequential reward paths). Minimal `players` columns / rivalry badge keys preferred over inventing a full achievement platform (repo has trophy cabinet for leagues only — see research R8).

## Project Structure

### Documentation (this feature)

```text
specs/053-pvp-matchmaking-rivalries/
├── plan.md                 # This file
├── GATE.md                 # 052 ACCEPT prerequisite
├── research.md             # Phase 0
├── data-model.md           # Phase 1
├── quickstart.md           # Phase 1
├── contracts/
│   ├── battle-hub-surfaces.md
│   ├── pvp-queue-rpcs.md
│   ├── pvp-finalize.md
│   ├── ai-practice-policy.md
│   └── rivalry-presentation.md
└── tasks.md                # /speckit.tasks — not created here
```

### Source Code (repository root)

```text
# Schema / RPCs
supabase/migrations/098_pvp_matchmaking_rivalries.sql   # NEW
supabase/scripts/verify_required_schema.sql             # extend guards
scratch/apply_migration_098.py                          # NEW

# Pure logic
packages/pvp/pvp/__init__.py                            # NEW package
packages/pvp/pvp/models.py
packages/pvp/pvp/matchmaking.py                         # widening, score, exclusions
packages/pvp/pvp/rivalry_math.py                        # canonical pair, activation, events
packages/pvp/pvp/reward_policy.py                       # LP/coin multipliers; practice zeros
packages/leagues/leagues/match_points.py                # extend provisional / relative LP helpers if needed

# Discord
apps/discord_bot/cogs/battle_cog.py                     # hub redesign; Practice path; wire PvP
apps/discord_bot/core/pvp_match.py                      # NEW — shared stadium orchestration
apps/discord_bot/core/match_runs.py                     # run_type pvp/practice; engine flags
apps/discord_bot/core/match_rewards.py                  # stop using bot path for competitive LP when Practice
apps/discord_bot/core/economy_rpc.py                    # pvp/practice energy + coin helpers
apps/discord_bot/middleware/match_lock.py               # lock_type pvp/practice (via RPC)
apps/discord_bot/views/pvp_queue_view.py                 # NEW
apps/discord_bot/views/rivalries_view.py                # NEW (slice 2)
apps/discord_bot/embeds/pvp_embeds.py                   # NEW
apps/discord_bot/tasks/pvp_matchmaker_job.py             # NEW
apps/discord_bot/main.py                                # register interval job + persistent views if needed
apps/discord_bot/core/api_errors.py                      # map RPC errors

# Tests / ops / copy
tests/test_pvp_matchmaking.py
tests/test_pvp_rivalry_math.py
tests/test_pvp_reward_policy.py
scratch/check_053_pvp_ready.py
scratch/pvp_soak_report.py
change_log.md                                           # on ship
```

**Structure Decision**: Follow existing monorepo layout. Extract stadium orchestration out of the monolithic `battle_cog.py` Friendly/bot paths into `core/pvp_match.py` (reusable by Practice where sensible) rather than duplicating the ~2.5k-line cog.

## Complexity Tracking

| Violation / stretch | Why Needed | Simpler Alternative Rejected Because |
|---------------------|------------|--------------------------------------|
| New `packages/pvp` | Pure widening + rivalry events need Discord-free tests | Inlining in cog fails package boundary and unit isolation |
| Atomic dual `finalize_pvp_match` | Two managers, one run, one money/LP commit | Sequential cog rewards race and double-finalize under restart |
| Interval matchmaker + join-triggered claim | Live queue UX without always-on worker infra | Pure Discord-only pairwise poll misses expired/stale claims |

## Delivery slices

| Slice | Scope | Flag |
|-------|--------|------|
| **1** | Queue, matchmaker, shared stadium, `finalize_pvp`, AI Practice conversion, hub CTA | `battle_pvp_enabled` (+ `pvp_rewards_enabled`) |
| **2** | Rivalry update/hub/leaderboard, badges-as-keys, blocks, prefs, DMs | `pvp_rivalries_enabled` (+ DM/board subflags) |

## Next command

`/speckit.implement` **after** Feature 052 formal ACCEPT ([GATE.md](./GATE.md)). Task breakdown: [tasks.md](./tasks.md) (T001–T067). Optional: `/speckit.analyze` for consistency.
