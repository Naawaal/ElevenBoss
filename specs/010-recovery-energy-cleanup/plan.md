# Implementation Plan: Recovery Energy, Hub Cleanup & Energy Cap

**Branch**: `010-recovery-energy-cleanup` | **Date**: 2026-07-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/010-recovery-energy-cleanup/spec.md`

## Summary

Four product tweaks: Recovery Session energy **5**, action energy max **120**, remove Hospital from **Store → Club Facilities** (keep `/profile` Hospital), delete **`/club-finances`** (keep Profile Finances), and scrub stale pointers.

**Technical approach**: Migration `055` updates config, relaxes `energy`/`training_energy` CHECKs to 120, backfills `max_energy`, refreshes RPC fallbacks + `register_new_player`; bot UI strips Store Hospital buttons; remove slash method; fix hardcoded `/100` and Hospital/finance copy.

## Technical Context

**Language/Version**: Python 3.11+ (CPython)

**Primary Dependencies**: discord.py ≥2.7, supabase async client, existing `player_engine` / `energy` packages

**Storage**: Supabase Postgres — `game_config` upserts; `players` constraint + `max_energy` backfill; REPLACE RPC fallbacks (`process_recovery_session`, `sync_action_energy`, `apply_club_economy`, `register_new_player`)

**Testing**: pytest — fatigue math unchanged; update energy default/time-to-full tests if they encode max=100 as a *default* assumption

**Target Platform**: Discord bot (Render) + hosted Supabase

**Project Type**: Monorepo — SQL + Discord UI cleanup

**Performance Goals**: N/A (config/UI)

**Constraints**: AGENTS.md — no Discord in packages; economy via RPCs; new numbered migration only; Hospital RPCs stay; no new slash commands; `change_log.md` on ship; reconcile `.specify/specs/v1.0.0/`

**Scale/Scope**: ~10–15 files; 1 migration; no new tables

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| I. Monorepo | PASS | UI in apps; energy default tweak in packages/energy OK |
| II. DB via RPC/migration | PASS | Cap/config via `055`; no cog loops |
| III. Typing | PASS | Trivial default int changes |
| IV. Slash + defer | PASS | Removing a slash command; remaining flows keep defer |
| V. APScheduler | PASS | No new jobs |
| VI. Friendly errors | PASS | Update Hospital pointers |
| VII. YAGNI | PASS | No new hubs; keep Profile Hospital panel |

**Post-Phase 1 re-check**: PASS — CHECK constraint raise is required for dual-write; documented in research R2.

## Project Structure

### Documentation (this feature)

```text
specs/010-recovery-energy-cleanup/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── migration-055.md
│   ├── store-facilities-no-hospital.md
│   ├── remove-club-finances-command.md
│   └── copy-cleanup.md
└── tasks.md             # /speckit.tasks
```

### Source Code (repository root)

```text
supabase/migrations/055_recovery_energy_cap_cleanup.sql   # NEW
scratch/apply_migration_055.py                            # NEW
supabase/scripts/verify_required_schema.sql               # only if needed

packages/energy/energy/models.py                          # max default 120
apps/discord_bot/core/economy_rpc.py                      # defaults 120
apps/discord_bot/cogs/development_cog.py                   # /120 + recovery fallback 5 + copy
apps/discord_bot/cogs/store_cog.py                         # max fallback 120
apps/discord_bot/cogs/profile_cog.py                       # max fallback 120
apps/discord_bot/cogs/economy_cog.py                       # delete club-finances slash
apps/discord_bot/views/store_facilities.py                 # strip Hospital from facilities hub
apps/discord_bot/embeds/profile_embeds.py                  # L0_EMPTY
apps/discord_bot/core/api_errors.py                        # Hospital pointer
apps/discord_bot/core/injury_rpc.py                        # overflow DM pointer
change_log.md
AGENTS.md / .agents/AGENTS.md                             # brief note if energy max documented
.specify/specs/v1.0.0/spec.md + plan.md                   # reconcile
tests/test_match_loop_hardening.py                        # if defaults asserted
tests/test_profile_hospital_summary.py                    # if L0_EMPTY asserted
```

**Structure Decision**: One forward migration for all DB/config; Discord cleanup is delete/edit only on existing hubs.

## Complexity Tracking

> No constitution violations. CHECK-constraint raise is mandatory complexity for the 120 cap (dual-write), not optional abstraction.

## Implementation Notes (for `/speckit.tasks`)

1. **Order**: Apply `055` + verify before relying on energy >100 in prod.
2. **Recovery**: Config UPDATE must `DO UPDATE` — `054` already inserted 10 with `DO NOTHING`.
3. **Store Hospital**: Delete hub chrome only; keep `HospitalPanelView`.
4. **Finances**: Delete slash method only; keep helpers.
5. **Grep**: `fatigue_recovery_energy`, `energy_max`, `/100`, `club-finances`, `Hospital Panel`, `build one in the Store`.
6. **Out of scope**: Hospital RPC deletion, drill energy changes, regen interval.
