# Contract: Wave 0 Verify Greps

**Feature**: `022-v1-stability-blueprint`  
**Maps to**: Spec Wave 0, IDs C1–C5, H2, H4, H5, H7, H9, L1, L4, E8

## Purpose

Executable checklist that reclassifies **Verify** registry items. Run from repo root. Fail ⇒ set status **Open** and assign bundle; Pass ⇒ **Closed** (note test name / date).

## Greps (must be clean or explained)

| Check | Command / procedure | Fail if |
|-------|---------------------|---------|
| C5 coins bypass | Search `apps/discord_bot` for `.update(` / SQL updating `coins` outside `apply_club_economy` wrappers | Direct coin mutation in cogs/tasks |
| C5 flat XP | Search for `p_xp_amount` hardcoded `15` or similar flat XP in battle paths | Flat XP on bot/league live path |
| H2 evo double-tick | Search `apps/` for `tick_evolution_match_progress` | Any Python caller (RPC-only is OK) |
| H2 friendly sandbox | Trace friendly conclude in `battle_cog` | Economy/XP/evo applied on friendly |
| C4 / E8 scheduler | Read `main.py` job list; confirm one `league_state_machine_job` cron @ 00:05; no separate dynamics cron; interval auto-sim skips dynamics | Double cron or dynamics processed by interval |
| H7 schema | Run verify script against env with applied migrations | Missing function/column/policy |
| L1 debug files | Search for `debug-` log file writers in cogs/core | Active debug file instrumentation |
| L4 formation | `pytest tests/test_audit_fixes.py` | Wingback / role asserts fail |

## pytest batch (Pass = green)

```text
pytest tests/test_transfer_market_race.py \
       tests/test_transfer_market_math.py \
       tests/test_wage_payroll_math.py \
       tests/test_league_automation_rules.py \
       tests/test_momd_selection.py \
       tests/test_league_dynamics_windows.py \
       tests/test_seasonal_promo_relegation.py \
       tests/test_audit_fixes.py \
       tests/test_economy_flows.py -q
```

(Adapt if a file is missing locally; record skips.)

## Smoke (optional with DATABASE_URL)

| ID | Smoke |
|----|-------|
| C1 | Existing transfer race test / scratch double-buy |
| C2 | Re-invoke weekly payroll same `week_key` → no second debit |
| C3 | Re-settle completed MD → MoMD coins unchanged |
| H4/H9 | Purchase with wrong expected price / listed XI card → reject |
| H5 | Claim pending after owner change → current owner only |

## Output artifact

Update Issue Registry rows in `spec.md` (status + Notes). No code required when all Pass.
