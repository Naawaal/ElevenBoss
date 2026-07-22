# Quickstart: Game Integrity Remainder (US-42.6–42.10)

## Validations

### 0 — Audit
- [ ] `contracts/remainder-audit.md` matches research Critical/Soft/OK

### 1 — W7 Economy registry
- [ ] `economy-source-sink-registry.md` has rows for match, store, wages, transfer, prizes, drills/fusion, agent/scout
- [ ] `pytest tests/test_economy_registry_guards.py` passes (no app coins UPDATE; friendly non-faucet)

### 2 — W6 Marketplace
- [ ] Race / own-buy / list-busy guards or tests green
- [ ] Tax documented in registry (implicit or explicit)

### 3 — W8 Jobs
- [ ] `job-catalog.md` lists every job from `main.py` scheduler registration
- [ ] Each row has run-key / catch-up note

### 4 — W9 RPC
- [ ] `rpc-guarantee-checklist.md` present
- [ ] Any new migration this feature adds extends `verify_required_schema.sql`

### 5 — W10 Security
- [ ] `threat-model.md` + `edge-catalog-remainder.md` cover epic §8 remainder categories
- [ ] Stale interaction fail-closed noted for market/store

### 6 — Lock
- [ ] Spec Status → Locked
- [ ] `change_log.md` only if managers see new copy
- [ ] Epic `029` still points at `035`

## Suggested implement order

```text
W7 registry + greps
W6 market test lock (+ Soft tax if cheap)
W8 job catalog
W9 checklist
W10 threat + edges
```
