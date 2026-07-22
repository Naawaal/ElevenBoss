# Contract: Hot-Path Wave 2 Targets

**Parent**: [../spec.md](../spec.md) | Mirrors updates into [`../../038-db-scalability-performance/contracts/hot-path-catalog.md`](../../038-db-scalability-performance/contracts/hot-path-catalog.md)

| ID | Surface | Before (est.) | Target after | Instrumentation |
|----|---------|---------------|--------------|-----------------|
| HP-4 | Profile | 5 sequential | ≤3 remote (warm divisions = 0 for that key) | `hub_timer("profile")` |
| HP-5 | Squad | 5 sequential | 1 gather wave (≤5 parallel) + count | `hub_timer("squad")` |
| HP-6 | League hub open | 8 sequential | guild∥league parallel; join limits 2→1; conditional reg query | `hub_timer("league_hub")` |

## Exit

SC-004 style: ≥50% cut on *serial* RTs or ops p95 ≤2s. Integrity contract: [integrity-guards.md](./integrity-guards.md).
