# Implementation Plan: Division-Tier Fatigue & Injury Rebalance

**Branch**: `016-tier-fatigue-rebalance` | **Date**: 2026-07-13 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/016-tier-fatigue-rebalance/spec.md`

## Summary

Scale match fatigue drain, daily natural recovery, injury chance, and hospital recovery days by a club’s **Division Rank intensity tier** (2-2-2: Grassroots/Amateur → Tier 1; Semi-Pro/Professional → Tier 2; Elite/Legendary → Tier 3). Soften tactic modifiers and PHY resistance; remove the old rating-gap “intensity +5” surcharge. Add Hospital / profile / pre-match transparency copy. Ship one-shot fair hospital ETA backfill + uninjured fatigue floor (≥50). Soft-lock fillers stay out of scope.

**Technical approach**: Migration `061` adds `players.intensity_tier`, upserts config mirrors, replaces `process_daily_recovery` / admit / post-match injury recovery CASE math, adds `backfill_tier_fatigue_rebalance()`. Pure helpers in `player_engine.fatigue` + `injury_math` (+ small intensity map helper). Bot passes tier into drain/injury builders; weekly Monday job writes `intensity_tier` from settled `division`. UI embeds only — no new slash commands.

## Technical Context

**Language/Version**: Python 3.11+ (CPython)

**Primary Dependencies**: discord.py ≥2.7, supabase async client, `player_engine`, `economy` (facility multipliers for UI only)

**Storage**: Supabase Postgres — new column `players.intensity_tier`; `game_config` upserts; `CREATE OR REPLACE` on recovery/injury/admit RPCs; new backfill RPC

**Testing**: pytest — tier mapping, drain/recovery/injury/hospital formulas, fair backfill helpers (never-lengthen, early clear, fatigue floor eligibility)

**Target Platform**: Discord bot (Render) + hosted Supabase

**Project Type**: Monorepo — migration + pure math + existing Discord surfaces

**Performance Goals**: Daily recovery remains one set-based RPC; backfill single-pass over open patients (small N)

**Constraints**: AGENTS.md monorepo/DB/UI rules; no Discord in `packages/`; no direct `player_cards.fatigue` UPDATEs outside fatigue RPCs; no new hubs/commands; YAGNI — no soft-lock fillers; no cup system to invent; reconcile SDD + `change_log.md` on ship

**Scale/Scope**: ~15–25 files; 1 migration; Hospital/profile/battle embed touchpoints; weekly reset + match rewards wiring

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| I. Monorepo | PASS | Formulas in `packages/player_engine`; Discord embeds/cogs only in `apps/` |
| II. DB via RPC/migration | PASS | Mutations via `061` RPCs + backfill; bot still sends starter drains JSONB |
| III. Typing | PASS | Typed helpers / optional small dataclasses |
| IV. Slash + defer | PASS | No new commands; existing deferred hubs |
| V. APScheduler | PASS | Extend existing Monday `weekly_league_reset_job` + daily recovery job |
| VI. Friendly errors | PASS | Advisory pre-match warning; migration DMs best-effort if used |
| VII. YAGNI | PASS | Soft-lock deferred; no clubs table; cup = forward note only |

**Post-Phase 1 re-check**: PASS — `intensity_tier` on `players` (club entity); cup FR satisfied by “use human tier when cup appears” with no new cup code; AI parity = shared intensity params in sim/injury rolls for that match, human-only persisted fatigue (existing).

## Project Structure

### Documentation (this feature)

```text
specs/016-tier-fatigue-rebalance/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── intensity-tier-mapping.md
│   ├── fatigue-drain-recovery-math.md
│   ├── injury-hospital-math.md
│   ├── backfill-tier-fatigue-rpc.md
│   ├── hospital-profile-battle-ui.md
│   └── match-ai-parity.md
└── tasks.md             # /speckit.tasks — NOT created here
```

### Source Code (repository root)

```text
supabase/migrations/061_tier_fatigue_rebalance.sql
scratch/apply_migration_061.py
supabase/scripts/verify_required_schema.sql          # extend guards

packages/player_engine/player_engine/fatigue.py       # tier drain, recovery, tactic mods
packages/player_engine/player_engine/injury_math.py    # tier injury + hospital days + fair helpers
packages/player_engine/player_engine/intensity.py      # NEW — division→tier map + labels (or fold into fatigue.py)
packages/player_engine/player_engine/__init__.py

tests/test_tier_fatigue_rebalance.py                 # NEW (or extend test_fatigue_injury_math.py)

apps/discord_bot/core/injury_rpc.py                   # pass intensity_tier into drain/injury
apps/discord_bot/core/match_rewards.py                # drop rating-gap intensity; pass tier
apps/discord_bot/core/league_rewards.py               # pass tier
apps/discord_bot/core/scheduler_jobs.py               # set intensity_tier on Monday reset
apps/discord_bot/embeds/hospital_embeds.py            # intensity header
apps/discord_bot/embeds/profile_embeds.py             # injury math breakdown
apps/discord_bot/cogs/battle_cog.py / match ticket embeds  # pre-match <30% warning
packages/match_engine/match_engine/v2_simulator.py    # optional: pass tier into injury rolls both sides

change_log.md
.specify/specs/v1.0.0/spec.md                         # reconcile AC for tier intensity
.specify/specs/v1.0.0/plan.md                         # brief note if present
```

**Structure Decision**: Club = `players` row (no `clubs` table). Intensity is a persisted SMALLINT on `players`, refreshed only when weekly division settlement runs. Pure math owns formulas; SQL daily recovery / admit / injury RPCs mirror the same numbers; bot computes per-starter drains with tier before `apply_match_fatigue`.

## Complexity Tracking

> No constitution violations.

## Implementation Notes (for `/speckit.tasks`)

1. **Prerequisite**: `056`–`059` (and `057` backfill pattern) understood; `060` may exist (youth academy) — next file is **`061`**.
2. **Column**: `players.intensity_tier SMALLINT NOT NULL DEFAULT 1 CHECK (intensity_tier BETWEEN 1 AND 3)`; backfill from `division` in same migration; weekly job updates after promo/relegation writes.
3. **Drain path**: `match_fatigue_drain(phy, stance, *, tier)` — bases 8/12/16, PHY×0.10, tactics +4/−2/0; **remove** `intensity: bool` surcharge (and stop computing rating-gap intensity in `match_rewards`).
4. **Passive path**: Replace SQL `25 + TG×5` with tier bases 35/25/15 + `TG×2` inside `process_daily_recovery`; mirror in Python.
5. **Injury / hospital**: Tier base chances + fatigue mod 0.03%/pt; recovery days = ceil((moderate_base×sev_mult)/(1+0.2H)); replace 1/4/7 CASE in admit + post-match injury RPCs.
6. **Backfill**: New idempotent RPC (do not overload `backfill_injury_eta_fairness` semantics blindly — new name preferred); never lengthen; fatigue floor only uninjured not in hospital.
7. **UI**: Hospital intensity header; profile injury breakdown; battle pre-match advisory if any starter fatigue &lt; 30.
8. **Cup**: No production cup — document forward-compat only (FR-012).
9. **Soft-lock**: Explicitly do not implement (FR-014).
10. **Grep after**: `FATIGUE_BASE_DRAIN`, `BASE_RECOVERY_DAYS`, `fatigue_passive_base`, `intensity=`, `match_fatigue_drain`, `0.15`, tactic `+8`.
