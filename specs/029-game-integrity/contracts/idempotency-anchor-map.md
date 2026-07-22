# Contract: Idempotency Anchor Map (INV-08)

**Parent**: [../spec.md](../spec.md) | **Checklist**: [invariant-checklist.md](./invariant-checklist.md)

Maps logical reward/mutation actions → expected key pattern / evidence → owning child when incomplete.

| Logical action | Expected key / evidence | Owner child | Status |
|----------------|-------------------------|-------------|--------|
| Daily login claim | `claim_daily_login` + ledger / already-claimed path | 42.7 | Covered (economy pipe) |
| Match reward (bot/league) | `match_run_id` / `process_match_result` settle-once | 42.4 | Covered (`033`, mig `077`) |
| Friendly match | Sandbox — no competitive faucet (INV-11) | 42.4 | Covered |
| Transfer buy | Listing lock + one-winner RPC; race tests | 42.6 | Covered (`035` guards + race tests) |
| Pack / vote claim | `interaction:{id}` via `p_idempotency_key` → `pack_claim_runs`; FR-006a `applied`/`already_applied`; Top.gg fail-closed | 42.7 / US-43 | Covered (`082`) |
| League prize / MoMD | Season transition / prize once; pause ≠ forfeit | 42.5 | Covered (`034`) |
| Level reward claim | Current owner; claim once | 42.1 / progression | Covered (US-24 pipe) |
| Energy refill purchase | Economy ledger idempotency | 42.7 | Covered |
| Evolution start / tick | Cost once; match tick ≤1/card/match (INV-10) | 42.2 / match | Covered |
| Job / sweeper catch-up | Run key terminal status | 42.8 | Catalogued (`035` job catalog) |

## Regression anchors

| Path | INV tags | Notes |
|------|----------|-------|
| `tests/test_transfer_market_race.py` | INV-13, INV-08 | Concurrent buy |
| `tests/test_economy_flows.py` | INV-04, INV-05, INV-08 | Faucet/sink pipe |
| `tests/test_economy_registry_guards.py` | INV-05, INV-08 | Registry completeness |
| `tests/test_marketplace_integrity_guards.py` | INV-03, INV-13 | List/buy gates |
| `tests/test_job_catalog_guards.py` | INV-08 (jobs) | Scheduler run keys |
| `tests/test_match_integrity*.py` / recovery helpers | INV-08, INV-09, INV-17 | Settle-once / abandon |
| League pause / prize paths under `034` | INV-08, INV-12 | No sport forfeit from outage |

Gaps: only soft YAGNI items deferred in `035` (transfer-tax ledger sink naming, gem pipe, per-listing expiry run keys) — not open double-grant holes.
