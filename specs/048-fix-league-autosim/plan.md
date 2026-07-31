# Implementation Plan: Expired League Fixtures Stuck Pending Auto-Sim

**Branch**: `048-fix-league-autosim` | **Date**: 2026-07-31 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/048-fix-league-autosim/spec.md`

**US citation**: **US-42.5** League Integrity — settle-once; absence (illegal XI / missed window) → sporting resolve; infrastructure outage → retry/pause, **not** mass forfeit. Reuses `026` forfeit math already in `packages/leagues/leagues/forfeit_rules.py` and lifecycle `_resolve_fixture`.

## Summary

Legacy auto-sim **skips** expired fixtures when a human fails `human_club_xi_ok` (past-grace / incomplete XI / `squad_invalid`) and never writes a result — hub stays on “Expired (Pending Auto-Sim)” forever. Fix: on **post-window** settle, if a side is ineligible → apply **026 forfeit** (3–0 / double 0–0); if both eligible → existing auto-sim (prefer **silent** when threads missing so Discord UX does not block DB settle). Update Fixtures copy for forfeit vs pending. No new slash command; prefer no migration if fixture columns already hold `result_type` / `resolved_by`.

## Technical Context

**Language/Version**: Python 3.11+ / Postgres 15+ (Supabase)

**Primary Dependencies**: `auto_sim_expired_fixtures`, `run_league_match_simulation`, `human_club_xi_ok`, `single_forfeit` / `double_forfeit`, `apply_fixture_to_row` (standings from fixtures)

**Storage**: **No new tables expected.** May need zero SQL if `league_fixtures.result_type`, `resolved_by`, `status`, `played_at` already exist (they do). Only add a migration if a settle-once RPC is chosen over app-layer update.

**Testing**: Extend/reuse `tests/test_double_forfeit_standings.py`; new unit tests for expired-eligibility → forfeit vs sim decision; Discord/SQL smoke on Season #2 MD5 pending fixtures

**Target Platform**: Discord bot + hosted Supabase

**Project Type**: Hotfix (league auto-sim + fixtures UI)

**Performance Goals**: Same sequential expired loop; forfeit path is one fixture update (no match engine)

**Constraints**: US-42.5 settle-once; no forfeit for guild-unreachable alone; YAGNI — reuse forfeit_rules + lifecycle patterns; no bulk contract auto-renew

**Scale/Scope**: ~1–2 Discord core modules + `league_cog` fixtures copy + tests; optional tiny pure helper in `packages/leagues`

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| I. Monorepo | PASS | Pure forfeit math stays in `packages/leagues`; Discord settle wiring in `apps/discord_bot/` |
| II. DB via RPC | PASS | Prefer settle-once fixture update matching lifecycle; if race risk, optional RPC later |
| III. Typing | PASS | Typed outcomes from existing dataclasses |
| IV. Slash + defer | PASS | Extend `/league` hub paths only |
| V. APScheduler | PASS | Keep 10-min legacy job; ensure it calls new settle helper |
| VI. Friendly errors | PASS | Fixtures copy names forfeit / blocker |
| VII. YAGNI | PASS | Reuse `forfeit_rules` + lifecycle forfeit writes; no new admin command |

**Post-Phase 1 re-check**: PASS — contracts lock forfeit rule to 026; absence≠outage preserved.

## Project Structure

### Documentation (this feature)

```text
specs/048-fix-league-autosim/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── expired-fixture-settle.md
│   └── fixtures-pending-copy.md
└── tasks.md                 # /speckit.tasks — not created here
```

### Source Code (repository root)

```text
apps/discord_bot/core/league_expired_settle.py   # NEW — decide sim vs forfeit; write forfeit; call sim
apps/discord_bot/cogs/league_cog.py              # auto_sim_expired_fixtures + Fixtures status copy
# optionally thin pure decision helper:
packages/leagues/leagues/expired_settle.py       # OPTIONAL — map (home_ok, away_ok) → mode
packages/leagues/leagues/__init__.py             # export if added

tests/test_league_expired_settle.py              # NEW — decision matrix + forfeit field expectations
# reuse tests/test_double_forfeit_standings.py

change_log.md                                    # player-facing: expired matches resolve / forfeit if XI illegal
```

**Structure Decision**: App-layer settle helper first (matches lifecycle forfeit updates). Extract pure decision to `packages/leagues` only if it stays discord-free. Agent-context script absent — skipped.

## Complexity Tracking

> No constitution violations.

| Choice | Why | Simpler alternative rejected |
|--------|-----|------------------------------|
| 026 single/double forfeit after window | Already specified + tested; lifecycle already writes these | Leave skip forever (current bug); invent 1–0 admin score |
| Silent sim when threads missing (eligible XI) | 026: Discord must not block settlement | Return 0 and wait forever |
| Keep pause on guild unreachable | Absence-vs-outage: no mass forfeit | Forfeit all when guild missing |

## Phase 0 / Phase 1 outputs

| Artifact | Path |
|----------|------|
| Research | [research.md](./research.md) |
| Data model | [data-model.md](./data-model.md) |
| Contracts | [contracts/](./contracts/) |
| Quickstart | [quickstart.md](./quickstart.md) |

## Implementation sketch (for tasks handoff)

1. Pure decision: `(home_legal, away_legal)` → `sim` | `forfeit_home` | `forfeit_away` | `double_forfeit` (AI always legal).
2. `settle_expired_fixture(...)`: if not expired or already played → no-op; if forfeit → update fixture like lifecycle (`is_played`, scores, `result_type`, `resolved_by='forfeit_engine'` or `auto_sim_forfeit`); if sim → `run_league_match_simulation` with silent handler when threads absent.
3. Replace body loop in `auto_sim_expired_fixtures` to call settle helper (still skip active match_runs; still pause only on unreachable guild).
4. Fixtures UI: played + `result_type` forfeit → “3–0 (Forfeit)” / “0–0 (Double Forfeit)”; expired unplayed after failed cycle → optional blocker hint from `club_xi_block_reason` (best-effort).
5. Tests + smoke Season #2 MD5 pending pair; `change_log.md`.
