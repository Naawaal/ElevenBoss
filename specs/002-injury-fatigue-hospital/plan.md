# Implementation Plan: Player Fatigue, Injury & Hospital (Phases 1–2)

**Branch**: `002-injury-fatigue-hospital` | **Date**: 2026-07-11 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-injury-fatigue-hospital/spec.md`  
**Blueprint**: [integration-blueprint.md](./integration-blueprint.md)  
**Decisions**: Q1=A (hospital costs 1.5k–60k), Q2=A (no Tier-4 retire), Q3=A (Phase 3 isolated PR)

**Phase 3 plan**: [plan-phase3.md](./plan-phase3.md) — in-match substitution UI (US4). Phases 1–2 below are **shipped**.

## Summary

Ship **per-card fatigue** (drain, recovery, NSS stat penalties, squad/profile indicators) and **post-match injuries + Hospital facility** (beds, auto-admit, overflow UX, shared weekly facility upgrade). In-match interactive substitution / `async for` pause UI is **Phase 3** — see [plan-phase3.md](./plan-phase3.md).

**Technical approach**: Add `player_cards` fatigue/injury columns + `players.hospital_level` + `hospital_patients`; pure math in `packages/player_engine`; fatigue multiplier in `phase_stats.py` before 70/30 blend; post-match batch RPCs after economy/XP; extend `upgrade_club_facility` with `'hospital'`; UI under `/store` Club Facilities + squad/profile/development gates. No new slash commands. Coins only via `apply_club_economy`.

## Technical Context

**Language/Version**: Python 3.11+ (CPython)

**Primary Dependencies**: discord.py ≥2.7, supabase async ≥2.0, pydantic ≥2.0, APScheduler, local `match_engine` / `player_engine` / `economy`

**Storage**: Supabase PostgreSQL — new columns/table/RPCs in migration `050+`; `game_config` hospital/fatigue keys; extend `verify_required_schema.sql`

**Testing**: pytest — pure formula tests + RPC contract tests where feasible; Discord paths validated via quickstart

**Target Platform**: Discord bot (Render) + hosted Supabase

**Project Type**: Monorepo — `apps/discord_bot` + `packages/*` + `supabase/migrations`

**Performance Goals**: Post-match fatigue/injury = one batch RPC per club (no per-card app loops); match stream unchanged for Phases 1–2 (no pause)

**Constraints**: AGENTS.md — no `discord` in packages; no direct coin/XP updates; fatigue ≠ action_energy; friendlies sandbox; SDD reconcile `.specify/specs/v1.0.0/` on implement; RLS on `hospital_patients`

**Scale/Scope**: Phases 1–2 only (~15–25 files); Phase 3 documented but not implemented

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| I. Monorepo — no `discord` in `packages/` | PASS | Math in `player_engine` / `match_engine`; UI/RPC wrappers in `apps/discord_bot` |
| II. DB mutations via RPC / atomic paths | PASS | Fatigue/injury/hospital via RPCs; upgrades via `upgrade_club_facility` → `apply_club_economy` |
| III. Typing / Pydantic at boundaries | PASS | Extend `MatchPlayerCard`; Pydantic/dataclass results from pure math |
| IV. Slash + defer | PASS | No new slash commands; extend `/store` facilities + existing hubs |
| V. APScheduler | PASS | Add daily `process_daily_recovery` job (or equivalent); does not replace lazy energy sync |
| VI. User-friendly errors | PASS | Overflow / injured-block / upgrade failures → clear embeds; DM fallback to Hospital panel |
| VII. YAGNI | PASS | Phase 3 deferred; no build timers; no career-ending; reuse facility hub |

**Post-Phase 1 re-check**: PASS — design stays within monorepo boundaries; Phase 3 explicitly out of this plan’s implementation scope.

## Project Structure

### Documentation (this feature)

```text
specs/002-injury-fatigue-hospital/
├── plan.md                    # Phases 1–2 (shipped)
├── plan-phase3.md             # Phase 3 in-match sub UI
├── research.md
├── data-model.md
├── quickstart.md
├── integration-blueprint.md
├── contracts/
│   ├── fatigue-match.md
│   ├── post-match-injury-rpc.md
│   ├── hospital-facility.md
│   └── in-match-injury-sub.md # Phase 3
└── tasks.md                   # Phases 1–2 done; Phase 3 via /speckit.tasks next
```

### Source Code (repository root)

```text
packages/player_engine/player_engine/
├── fatigue.py                 # NEW — drain, recovery, penalty tiers
└── injury_math.py             # NEW — chance, tiers (1–3), hospital days/beds
packages/match_engine/match_engine/
├── models.py                  # MatchPlayerCard.fatigue (+ card id if missing)
├── phase_stats.py             # fatigue multiplier on phase attr before 70/30
└── v2_simulator.py            # Phase 1–2: pass fatigue into cards; leave pause UI to Phase 3
packages/economy/economy/
└── facility_effects.py        # hospital costs, beds, label, recovery mult helpers
apps/discord_bot/
├── core/
│   ├── match_cards.py         # hydrate fatigue/injury
│   ├── injury_rpc.py          # NEW — thin RPC wrappers
│   ├── match_rewards.py       # post-match fatigue (+ injury in Phase 2)
│   └── league_rewards.py      # same
├── cogs/
│   ├── battle_cog.py          # ensure card hydration; no stream pause in P1–2
│   ├── squad_cog.py           # indicators + block injured XI
│   ├── player_cog.py          # profile fatigue/injury
│   ├── development_cog.py     # block injured drills
│   └── store_cog.py           # only if hub copy needs touch
├── views/
│   └── store_facilities.py    # Hospital facility card + overflow/discharge views
├── embeds/
│   └── hospital_embeds.py     # NEW
├── main.py / scheduler_jobs.py  # daily recovery job
supabase/migrations/
└── 050_fatigue_injury_hospital.sql   # columns, table, RLS, RPCs, config, guards
supabase/scripts/verify_required_schema.sql
tests/test_fatigue_injury_math.py
change_log.md
.specify/specs/v1.0.0/spec.md + plan.md   # reconcile on implement
```

**Structure Decision**: Existing ElevenBoss monorepo. New pure modules under `player_engine`; Discord stays in cogs/views/core; one forward migration.

## Complexity Tracking

> No constitution violations requiring justification. Phase 3 complexity intentionally deferred.

## Economy Gate (pre-tasks — 2026-07-11)

**Verdict: Hospital coin ladder does not inflate the economy.** It is an optional sink competing for the existing weekly facility slot. **The real risk is indirect deflation** if fatigued squads take injuries too often and win less.

### Anchors (live formulas)

| Archetype | Daily income | Expenses | Net |
|-----------|--------------|----------|-----|
| Casual (5 bot wins + login, 5 drills) | 1,100 | 1,100 | **0** |
| Hardcore (10 wins + drills/fusion/refills) | 4,120 | 6,900 | **−2,780** |
| YA/TG full ladder (one facility) | — | 19,750 | sink |
| Hospital full ladder L0→5 | — | **100,500** | sink (~5× one YA/TG path) |

Hospital step premium vs YA/TG is ~**2×** at each peer step (1.5k vs 750, …). Weekly cap ⇒ max **1** facility upgrade/week across YA+TG+Hospital (13 weeks to max all three if never skipped).

### Direct coin effects — SAFE

| Check | Result |
|-------|--------|
| New faucet? | **No** — upgrade + optional care only |
| Touches `action_energy` / refill shop? | **No** (FR-005) |
| Bypasses `apply_club_economy`? | **No** — extend `upgrade_club_facility` |
| Casual can afford L1? | Yes — ~2 days income-only (~1,100/day) |
| L5 prestige? | ~45–86 days income-only depending on grind; gated by weekly slots anyway |
| Hardcore inflation? | Hardcore already deeply negative; hospital deepens sink if bought (desired) |

### Indirect effects — TUNE BEFORE PHASE 2

Fatigue drain ~11–25/match with only +20/day passive ⇒ managers playing **3+ competitive matches/day** settle in the 25–60 fatigue band.

| Squad state | P(≥1 injury)/match (11 rolls) | @5 matches/day |
|-------------|-------------------------------|----------------|
| Fresh (fatigue 100) | ~4% | ~1.5 injuries/week |
| Mid-fatigue (60) | ~20% | ~**7.7 injuries/week** |
| GDD tired example (30) | ~34% | brutal |

**Risk:** Injury wave → thinner XI → lower win rate → fewer coins → harder to afford Hospital → death spiral. That is deflationary, not inflationary, but can still “break” the feel of the economy.

### Guardrails locked for tasks (unless product overrides)

1. **Keep hospital costs** `1500 / 4000 / 10000 / 25000 / 60000` + shared weekly facility cap.
2. **No per-treatment / admit coin fee** in v1 (upgrade is the sink; don’t double-dip).
3. **Match gates on Hospital** (mirror YA/TG spirit): require **5 career matches** before L2, **20** before L4 — stops brand-new clubs dumping into Hospital before YA.
4. **Phase 1 ships before Phase 2** so win-rate / fatigue can be observed without injury tax.
5. **Injury rate soft-cap for v1 — LOCKED A+C (2026-07-11):**
   - **A:** At most **one** injury applied per club per match (among eligible rolls, apply a single outcome — first success or highest-risk eligible card; document choice in tasks as “first successful eligible roll in starter order”).
   - **C:** Only players with fatigue **&lt; 75** are eligible for injury rolls.
   - Rationale: injuries are a strategic consequence of poor rotation, not a squad wipe; can relax later if community wants more realism.
6. **Ops monitors** after ship: facility upgrade mix (YA vs TG vs Hospital), avg club coins WoW, injury admits / match, bot win rate vs pre-fatigue baseline. If win rate drops &gt;5 pts or injuries/match &gt;0.15, retune via `game_config` before raising hospital costs.

### Explicit non-goals (would break balance)

- GDD 100k–4M hospital ladder  
- Paying coins to skip fatigue (would cannibalize energy refill sink)  
- Friendlies granting fatigue/injury (sandbox)  
- Career-ending card deletion (progression wipe)

## Implementation Approach (for `/speckit.tasks`)

### Phase 1 — Fatigue only

1. Migration: `player_cards.fatigue` DEFAULT 100 + verify guards (injury/hospital columns may land in same migration file but bot wiring can feature-flag Phase 2).
2. Pure: `fatigue.py` — drain formula, penalty tiers, passive/bench recovery constants (mirror `game_config` defaults).
3. Engine: load fatigue on `MatchPlayerCard`; apply penalty in `phase_stats.phase_stat_value`.
4. Post-match: `apply_match_fatigue` RPC from bot/league reward paths (starters drain, bench +15); skip friendlies.
5. UI: squad + profile fatigue indicators.
6. Scheduler or lazy: `process_daily_recovery` fatigue portion (+20/day cap 100).
7. Tests: drain/penalty math; no energy interaction.

### Phase 2 — Injury + Hospital

1. Same or follow-on migration objects: injury columns, `hospital_level`, `hospital_patients` + RLS, RPCs, `hospital_upgrade_costs`.
2. Pure: `injury_math.py` — chance, tier weights (100→Major), recovery days, bed capacity.
3. Post-match: after fatigue, `process_post_match_injuries`; auto-admit / return overflow.
4. Facilities UI: Hospital card; extend `upgrade_club_facility('hospital')`.
5. Gates: injured blocked from XI + drills; profile/hospital embeds; overflow DM + panel fallback.
6. Fusion/sell: block or auto-discharge (grep callers).
7. Cosmetic NSS INJURY: keep as non-authoritative flavor **or** reduce rate; authoritative injuries = post-match only until Phase 3.
8. `change_log.md` + v1.0.0 SDD reconcile.

### Phase 3 — Separate plan (ready for `/speckit.tasks`)

See **[plan-phase3.md](./plan-phase3.md)** and **[contracts/in-match-injury-sub.md](./contracts/in-match-injury-sub.md)**.

- Live stoppage pause via `asyncio.Event` (not `generator.send()`), Select Menu, Play On, 10-men, emergency GK, `MatchState` bench swaps during `async for`.
- Spec US4 / FR-013–014 / SC-008 are in scope for that PR only.
