# Implementation Plan: v1 Stability Blueprint

**Branch**: `022-v1-stability-blueprint` | **Date**: 2026-07-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/022-v1-stability-blueprint/spec.md`

## Summary

Stabilize ElevenBoss for v1.0.0 by executing a **verify-first, then fix** program against the Issue Registry in the spec: money/ownership races, Select empty-state UX, OVR truth, match/evolution parity, and recent-feature loopholes (mentor, hospital, transfer, wages, league dynamics/automation) — without new gameplay systems or slash commands.

**Technical approach**: Wave 0 greps + existing pytest/smoke reclassify **Verify** items; Waves 1–3 ship root-cause fixes only where Open/Suspect fails (prefer shared helpers / single RPC guards over per-hub patches); Wave 4 timeboxed polish. New migrations **only** if a Critical/High reopen requires a forward schema/RPC fix (next number after `065`). Registry status updates live in this feature folder; reconcile behavioral contracts into `.specify/specs/v1.0.0/` when implement diverges.

## Technical Context

**Language/Version**: Python 3.11+ (CPython) / Postgres 15+ (Supabase)

**Primary Dependencies**: discord.py ≥2.7, supabase async ≥2.0, pydantic ≥2.0, APScheduler; local packages `economy`, `player_engine`, `match_engine`, `leagues`

**Storage**: Existing Supabase schema/RPCs (062–065 and peers). No new tables planned; forward migration only if Critical reopen requires it. Registry is documentation, not a DB table.

**Testing**: pytest under `tests/` (extend race/math/parity); Discord Persona + pilot checklists in [quickstart.md](./quickstart.md); schema via `supabase/scripts/verify_required_schema.sql`

**Target Platform**: Discord bot (Render/Linux) + hosted Supabase

**Project Type**: Monorepo stability program — mostly `apps/discord_bot` + `tests/` + optional `supabase/migrations/066_*` + thin pure helpers if formulas need shared asserts

**Performance Goals**: No new N+1 hubs; race fixes stay inside existing RPC transactions; Wave 0 greps finish in minutes, not hours

**Constraints**: AGENTS.md / constitution — no `discord` in `packages/`; single coin pipe `apply_club_economy`; single XP pipe `apply_card_xp`; no new slash commands/hubs/tables beyond Critical necessity; flags stay default-off until pilot gates pass; YAGNI / ponytail

**Scale/Scope**: Defect registry ~30+ IDs across 5 waves; expected Open fixes concentrated on Select UX (H1), OVR disposition (H3), evo copy/config truth (H8), and any Wave 0 reopen failures; Verify majority should stay Closed after regression

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| I. Monorepo — no `discord` in `packages/` | PASS | UI/Select fixes in `apps/discord_bot`; pure OVR/assert helpers may extend `packages/player_engine` without Discord |
| II. DB mutations via RPC / atomic paths | PASS | Money/races already on RPCs; any reopen fix is forward migration + RPC body — no cog coin UPDATE |
| III. Typing / Pydantic at boundaries | PASS | Keep hints on touched helpers; no speculative model layer |
| IV. Slash + defer | PASS | No new commands; preserve defer on existing hubs |
| V. APScheduler | PASS | Verify single 00:05 ownership + interval auto-sim skip for dynamics; no third tick job |
| VI. User-friendly errors | PASS | Race losers and empty Select must get clear ephemerals / empty-state copy |
| VII. YAGNI | PASS | Fix/verify only; no bidding, auto-sell, PlayStyle evo phase, or new hubs |

**Post-Phase 1 re-check**: PASS — design adds shared Select empty-state pattern + verification contracts; no unjustified new packages or surface area. Migration reserved only as Conditional Path if Wave 0 fails Critical Verify.

## Project Structure

### Documentation (this feature)

```text
specs/022-v1-stability-blueprint/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── wave0-verify-greps.md
│   ├── select-empty-state.md
│   ├── money-idempotency.md
│   ├── ovr-truth.md
│   └── edge-case-matrix.md
└── tasks.md             # /speckit.tasks (not this command)
```

### Source Code (repository root)

```text
apps/discord_bot/
├── core/
│   ├── view_helpers.py          # extend: select-only-if-options + empty-state helpers
│   ├── squad_validity.py        # contract-grace / strike gate parity checks
│   ├── match_rewards.py         # bot reward path (Wave 0 verify)
│   ├── league_rewards.py        # league + MoMD wiring (Wave 0 verify)
│   ├── league_automation.py     # state machine (C4 / E8–E10)
│   ├── scheduler_jobs.py        # job registration parity
│   └── economy_rpc.py           # flag helpers
├── views/
│   ├── store_facilities.py      # hospital Select rebuild (H1)
│   ├── academy_hub.py           # academy empty Select (H1)
│   ├── marketplace_transfer.py  # transfer empty/filter (H1/H4)
│   └── … development / squad selects as Wave 3 audit finds
├── cogs/
│   ├── battle_cog.py            # match parity / stale XI (H2/H6)
│   ├── admin_cog.py             # pilot Run Cycle remove (M7) when trusted
│   └── … economy / development for wages + mentor edges
├── tasks/
│   ├── weekly_payroll_job.py
│   └── transfer_listing_expiry_job.py
├── main.py                      # confirm: only league_state_machine_job @ 00:05 (not double dynamics)
packages/
├── player_engine/…              # True OVR / inflation detect; allocate/mentor math
├── economy/…                    # transfer/wage pure helpers (tests already exist)
├── leagues/…                    # MoMD / automation pure rules
├── match_engine/…               # formation roles (L4 verify)
supabase/
├── migrations/                  # CONDITIONAL: 066_* only if Critical reopen needs RPC fix
└── scripts/verify_required_schema.sql
tests/
├── test_transfer_market_race.py
├── test_transfer_market_math.py
├── test_wage_payroll_math.py
├── test_league_automation_rules.py
├── test_momd_selection.py
├── test_audit_fixes.py
└── (extend) select / ovr / evo-tick asserts as needed
scripts/
└── fix_inflated_player_stats.py # H3 disposition (dry-run → decide apply)
scratch/                         # optional smoke only; never imported by prod
change_log.md                    # when manager-visible fixes ship
.specify/specs/v1.0.0/           # reconcile if contracts drift on implement
```

**Structure Decision**: Stay inside existing ElevenBoss layout. Prefer one shared Select helper over five one-off rebuilds. Prefer proving existing RPCs over new tables.

## Complexity Tracking

> No constitution violations requiring justification.

## Implementation Approach (for `/speckit.tasks`)

### Wave 0 — Verify (no product change unless red)

1. Run [contracts/wave0-verify-greps.md](./contracts/wave0-verify-greps.md) checklist; update Issue Registry statuses in `spec.md`.
2. Re-run existing tests: transfer race/math, wage math, league automation, MoMD, audit formation, economy flows.
3. Confirm scheduler: `main.py` registers `league_state_machine_job` once; `auto_sim_expired_fixtures_job` skips dynamics pacing (E8).
4. Confirm apps never call `tick_evolution_match_progress` outside `process_match_result` SQL path (H2).
5. Confirm no live `players.coins` UPDATE / flat XP `15` in cogs (C5).

**Exit**: Registry accurate; any failed Verify → Open + assigned Wave 1–2 bundle.

### Wave 1 — Money & races

Bundle **B-Transfer / B-Wages / B-League-Tick / B-Automation** for any Open Critical/High from Wave 0. Follow [contracts/money-idempotency.md](./contracts/money-idempotency.md). Prefer SQL uniqueness + ledger keys already present; wire gaps only.

### Wave 2 — Truth & match parity

- **H3 / B-OVR**: factory assert tests; dry-run `scripts/fix_inflated_player_stats.py`; ops disposition recorded in registry (apply count or defer count). See [contracts/ovr-truth.md](./contracts/ovr-truth.md).
- **H2 / H6 / B-Match-***: match-type matrix in quickstart; re-validate XI at lock if Suspect proven.
- **H8 / B-Evo-Truth**: align hub copy + config reads with RPC (no false PlayStyle promise) — may overlap unfinished `018`; stability takes **truthfulness** (copy/config), not full evo redesign.
- **H5 / B-Retro**: claim path owner_id regression smoke.

### Wave 3 — UX & recent edges

- **H1 / B-UI-Select**: implement [contracts/select-empty-state.md](./contracts/select-empty-state.md) helper; apply hospital → academy → marketplace → other Select hubs found by audit.
- Prove/disprove **E1–E12** via [contracts/edge-case-matrix.md](./contracts/edge-case-matrix.md); fix only Proven High+.

### Wave 4 — Polish & hygiene

B-Copy (dual ladder wording), B-Hygiene (dead debug/tests), M7 remove pilot controls when cron trusted. Timeboxed; leftover Low → backlog IDs.

### Conditional Path — Migration

Only if Wave 0–1 proves RPC/schema bug needing forward fix:

1. Author `supabase/migrations/066_<name>.sql` (DROP old overload if signature change).
2. Extend `verify_required_schema.sql`.
3. Apply via scratch pattern; verify before bot deploy.
4. Document in registry + change_log if player-visible.

## Frozen Decisions (from research)

See [research.md](./research.md). Highlights: verify-first; Select empty = omit Select + copy; legacy OVR = dry-run then decide; evo PlayStyle = copy fix in-scope; flags stay off; registry in-spec not DB.
