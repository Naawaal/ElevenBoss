# Quickstart & Validation Guide: Match Concurrency & Squad Locking Integrity

**Feature**: [`spec.md`](file:///d:/Python/Discord%20Bots/ElevenBoss/specs/056-match-concurrency-integrity/spec.md) | [`plan.md`](file:///d:/Python/Discord%20Bots/ElevenBoss/specs/056-match-concurrency-integrity/plan.md)

---

## 1. Schema Verification

Run the full schema validation script:
```bash
python scratch/verify_schema_full.py
```

Expected Output:
```text
=== Full Schema Guard Verification ===
All required tables, policies, and RPC function signatures verified!
```

---

## 2. Concurrency & Locking Unit Tests

Run the dedicated test suite for Match Concurrency Integrity:
```bash
pytest tests/test_match_concurrency_integrity.py -v
```

Expected Scenarios Verified:
1. `start_friendly_match` locks both home and away managers atomically.
2. Locked manager is rejected when trying to start a Bot Battle or Ranked match.
3. SQL procedures `set_formation_and_assignments` and `swap_squad_players` fail with `manager_in_active_match` when locked.
4. `SquadHubView` revalidates lock status and disables formation/swap buttons.
5. Ghost Manager backfills lock ONLY the active human challenger; offline ghost owner remains unlocked.
6. Terminal match settlement (`completed` / `abandoned`) releases locks cleanly.
