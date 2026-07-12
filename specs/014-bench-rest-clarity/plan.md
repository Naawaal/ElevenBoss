# Implementation Plan: Bench Rest Clarity

**Branch**: `014-bench-rest-clarity` | **Date**: 2026-07-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/014-bench-rest-clarity/spec.md`  
**Reporter update**: The two matches were **bot** matches (not friendlies). Cards had **fatigue = 0** and were **on the bench** — cap-100 is ruled out; treat as a defect until fitness gate / selection / silent failure is fixed.

## Summary

Investigate and harden **bot/league bench rest** so managers can trust that unused healthy reserves gain up to **+25** fatigue (cap 100) after competitive matches.

**Highest-likelihood code gaps (bot path is wired, but fragile / opaque):**

1. **Crash-window skip** — `apply_bot_match_rewards` / league twin early-return when `xp_applied_at` is set, **before** fitness. XP is marked applied *before* `apply_post_match_fitness`. If fatigue/injury throws once (or a retry races), that match never rests the bench and never drains starters — silent because of a bare `except`.
2. **Opaque top-7** — `fetch_bench_ids` takes unordered non-starters `[:7]`. Deep squads: specific “bench” names the manager watches may never be in the rested set.
3. **No match-end feedback** — success and failure look the same in Discord.

**Live DB check (2026-07-12):** `fatigue_bench_per_match = 25` already on ElevenBoss Supabase — not a config miss.

**Technical approach**: Add `match_history.fatigue_applied_at` (or equivalent gate); gate fitness separately from XP in bot + league reward helpers; order bench candidates deterministically (`overall DESC`); surface a short bench-rest / fitness line on match end; stop swallowing fitness failures without any manager/ops signal; docs + `change_log` clarity. No friendly sandbox change.

## Technical Context

**Language/Version**: Python 3.11+ / Postgres 15+

**Primary Dependencies**: discord.py, Supabase async client, existing `apply_match_fatigue` RPC, `injury_rpc` / `match_rewards` / `league_rewards`

**Storage**: `match_history` new timestamp column; `player_cards.fatigue`; `game_config.fatigue_bench_per_match` (already 25)

**Testing**: pytest for bench selection ordering; reward-helper gate logic (unit with mocks); optional scratch SQL smoke for `apply_match_fatigue`

**Target Platform**: Bisup Discord bot + hosted Supabase

**Project Type**: Monorepo bugfix + UX clarity (no new slash commands)

**Performance Goals**: One extra column update per competitive match; same RPC call count as today when healthy

**Constraints**: AGENTS.md — no Discord in packages; no direct `player_cards` fatigue UPDATE from cogs (keep RPC); new numbered migration; no friendlies fatigue; reconcile SDD + `change_log.md`

**Scale/Scope**: ~8–12 files; 1 migration; bot + league reward paths

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| I. Monorepo | PASS | Selection helper can be pure in packages; Discord/UI in apps |
| II. DB via RPC | PASS | Fatigue writes stay in `apply_match_fatigue`; new column + gate only |
| III. Typing | PASS | Typed helpers / explicit dict contracts |
| IV. Slash + defer | PASS | No new commands; match-end embed/footer only |
| V. APScheduler | PASS | Untouched |
| VI. Friendly errors | PASS | Surface fitness failure briefly instead of silent swallow |
| VII. YAGNI | PASS | Keep max 7 rest (deterministic order); do not rest entire deep squad unless product later asks |

**Post-Phase 1 re-check**: PASS — prefer `fatigue_applied_at` over re-running undrained fatigue (would double-rest). Keep friendlies sandbox.

## Project Structure

### Documentation (this feature)

```text
specs/014-bench-rest-clarity/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── fatigue-applied-gate.md
│   ├── bench-selection-order.md
│   └── match-end-bench-rest-copy.md
└── tasks.md             # /speckit.tasks — NOT created here
```

### Source Code (repository root)

```text
supabase/migrations/059_fatigue_applied_at.sql     # NEW — column + verify guard
scratch/apply_migration_059.py                     # NEW

packages/player_engine/player_engine/bench_rest.py # NEW optional — pick_bench_rest_ids(ordered)
# OR keep ordering only in apps/discord_bot/core/injury_rpc.fetch_bench_ids

apps/discord_bot/core/injury_rpc.py                # ORDER BY overall; return rested meta
apps/discord_bot/core/match_rewards.py             # separate XP vs fatigue gates; less silent except
apps/discord_bot/core/league_rewards.py            # same gates
apps/discord_bot/core/match_runs.py                # mark_match_fatigue_applied helper
apps/discord_bot/cogs/battle_cog.py                # optional: pass rest summary into finalize copy
# match result embed / finalize_match path — one line of bench-rest feedback

tests/test_bench_rest_selection.py                 # NEW — ordering + cap 7 + skip injured
tests/test_match_rewards_fatigue_gate.py           # NEW — xp set does not skip pending fatigue

change_log.md
.specify/specs/v1.0.0/spec.md                      # competitive bench rest + crash-safe note
supabase/scripts/verify_required_schema.sql        # column + optional function guards
```

**Structure Decision**: Fix crash-safe fitness gate first (real silent miss on bot/league), then deterministic top-7 selection, then minimal match-end copy. No new hub buttons.

## Complexity Tracking

> No constitution violations.

## Implementation Notes (for `/speckit.tasks`)

1. **Migration `059`**: `ALTER TABLE match_history ADD COLUMN IF NOT EXISTS fatigue_applied_at TIMESTAMPTZ`; extend verify script.
2. **Reward helpers**: After XP path, if `fatigue_applied_at` is null → `apply_post_match_fitness` → mark timestamp. Early return only when **both** XP and fatigue are applied (or return after applying missing fatigue).
3. **Same pattern** in `league_rewards.py`.
4. **`fetch_bench_ids`**: `.order("overall", desc=True)` (or select overall and sort in Python); keep `[:7]`; skip injured/retired/starters.
5. **UX**: One line on bot match result (e.g. “Bench rest: +25 fitness for N reserves”) or “Bench already fresh”; on fitness exception, ephemeral/footer warning — do not fail the whole match reward.
6. **Grep**: `xp_applied_at`, `apply_post_match_fitness`, `fetch_bench_ids`, bare `post-match fatigue`.
7. **Out of scope**: Friendlies fatigue; changing +25; daily TG passive; resting >7 without a later product decision.
8. **Verify report**: After ship, one bot match with a known mid-fatigue unused high-OVR reserve must show +25 (or to 100) and match-end copy.
