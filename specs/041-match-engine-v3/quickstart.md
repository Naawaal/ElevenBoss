# Quickstart: Match Engine V3 Validation

**Feature**: `041-match-engine-v3`  
**Purpose**: Prove Phase 0 readiness before enabling prod flags.  
**Not**: full implementation guide (see `tasks.md` after `/speckit.tasks`).

---

## Prerequisites

- Repo checkout with `packages/match_engine` editable install  
- Pytest available  
- For DB checks: `DATABASE_URL` + migration `NNN_match_engine_v3_events` applied  
- Spec/plan/contracts read: [spec.md](./spec.md), [plan.md](./plan.md), [contracts/](./contracts/)

---

## 1. Determinism (no Discord)

```bash
pytest tests/test_nss_v3_determinism.py -q
```

**Expect**: Same seed+squads → identical event hash twice; `rng_draw_count` stable.

---

## 2. Parity vs v2 golden seeds (Phase 0 gate)

```bash
pytest tests/test_nss_v3_golden_corpus.py -q
```

**Expect**: ≥50 fixtures; `exact_parity` sporting digests match v2 baselines.

---

## 3. Win-rate / immersion regression

```bash
pytest tests/test_nss_win_rates.py -q
# optional heavier:
python -m tests.benchmark_nss
```

**Expect**: Within SC-008 tolerance for Balanced/stance mapping.

---

## 4. Projector integrity

```bash
pytest tests/test_nss_v3_projectors.py -q
```

**Expect**: Goals/shots/possession from events agree; MOTM deterministic.

---

## 5. Recovery parity

```bash
pytest tests/test_nss_v3_recovery_parity.py -q
```

**Expect**: Interrupted run completed via `run_to_completion` matches clean full run when decisions replayed.

---

## 6. Integrity non-regression

```bash
pytest tests/test_match_integrity_recovery.py tests/test_match_reward_wiring.py -q
```

**Expect**: Settle-once + friendly sandbox still hold with v3 adapter fakes.

---

## 7. Schema guard (after migration)

```bash
python scratch/verify_schema_full.py
# or:
# psql $DATABASE_URL -f supabase/scripts/verify_required_schema.sql
```

**Expect**: `match_events` + `match_runs.engine_version` guards pass.

---

## 8. Manual Discord smoke (staging)

1. Flag `match_engine_v3_bot=true` on staging only.  
2. `/battle bot` — live ticker works; touchline queues decisions.  
3. Kill bot mid-match → restart → recovery completes; **one** reward.  
4. Compare score to a silent re-sim of same `run_id` seed (ops script).  
5. Flip flag off — new matches v2.

---

## 9. Dixon-Coles calibration (optional offline)

```bash
python scripts/compare_v2_v3_seeds.py  # when added
# never import from battle_cog
```

**Expect**: Report only; no Discord path.

---

## Phase 0 exit checklist

- [x] SC-001 determinism CI green (`tests/test_nss_v3_determinism.py`)
- [x] SC-002 recovery parity green (`tests/test_nss_v3_recovery_parity.py`)
- [x] SC-003 integrity matrix green (v3 extensions in `test_match_integrity_recovery.py` + `test_match_reward_wiring.py`)
- [x] SC-004 silent match under budget (`tests/test_nss_v3_perf.py`)
- [x] SC-008 win-rate band accepted (`tests/test_nss_win_rates.py` v3 Balanced + seed-aligned exact_parity)
- [x] Migration + verify guards applied on staging (`scratch/apply_migration_083.py`)
- [x] Dual-run pin verified (`tests/test_nss_v3_dual_run_pin.py`)
- [x] Architecture pack reviewed (this folder)
- [x] Golden Corpus ≥50 exact_parity (`tests/test_nss_v3_golden_corpus.py`)

Waves 1–3 are implemented in-tree. Remaining: staging bot flag soak (`match_engine_v3_bot=1`), then league, then friendly. Prod flags stay off until a deliberate enable.
