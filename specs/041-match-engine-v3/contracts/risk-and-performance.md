# Contract: Risk & Performance Analysis

**Feature**: `041-match-engine-v3`  
**Deliverables**: 9 + 10

---

## Risk register

| ID | Subsystem | Risk | Failure mode | Exploit / edge | Mitigation | Rollback |
|----|-----------|------|--------------|----------------|------------|----------|
| K1 | Phase 0 port | Feel drift / win-rate shift | Managers sense rebalance | Seed farm for rewards | Golden corpus + SC-008 gates before flag on | Flag off |
| K2 | Touchline | Decision not logged | Recovery diverges | Spam desync | Barriers + cooldown + events | Disable tactic UI changes; force Balanced |
| K3 | Event flush | Partial write | Gap in seq / stuck thru | Crash between insert and thru update | Atomic RPC batch; idempotent conflict | Re-sim from seed+decisions; repair thru |
| K4 | Dual-run | Wrong engine on recovery | Divergent score vs partial Discord | — | Immutable engine_version | Manual abandon + integrity rules |
| K5 | Projectors | MOTM/scorer mismatch vs XP | Wrong XP attribution | Name collisions | Prefer card_id in GOAL payload Phase 0.1 | Fix projector; settle-once prevents double |
| K6 | Event growth | DB bloat / cost | Slow analytics | — | Retention + batch insert | Stop durable events; keep re-sim |
| K7 | Injury pause | Double resolution | Two subs | Double-click UI | Single awaiting_decision; idempotent apply | auto_resolve on timeout (existing) |
| K8 | AI future | AI mutates state | Hidden non-determinism | Code review gate | Protocol + lint/grep for context mutation | Remove brain |
| K9 | Dixon-Coles | Accidental live wire | Dual scoring | — | No import from battle_cog; CI grep | Revert import |
| K10 | Concurrency | Two steppers one run | Forked events | — | Match lock + single active worker | abandon_match_run |

### Loopholes challenged

- **Re-sim vs stored events disagree**: treat stored decisions+seed as authority; events are cache — on mismatch, prefer re-sim for settlement if not yet settled; if settled, flag ops alert, do not re-pay.
- **Friendly without events**: OK — no rewards; recovery re-sims from seed only (no mid-match durable tactics required until Wave 1 if friendlies gain decisions).

---

## Performance analysis

### CPU

- v2 already sub-10–20 ms typical for full silent match.  
- v3 target **&lt; 50 ms** (SC-004) includes event object allocation.  
- Optimization: reuse list buffers; avoid deep copy of full squad each step — copy-on-write only on sub/injury.

### Memory

- Context + 200 events in RAM ≈ low hundreds of KB per live match.  
- Fine for Discord process concurrency (locks already limit per club).

### Database writes

| Pattern | Round trips |
|---------|-------------|
| Naïve per-event insert | ~150–200 / match — **rejected** |
| Batch every 25 + HT/FT | ~8–12 / match |
| Single flush at FT only | 1 — weak mid-crash UX for analytics; acceptable if decisions+seed allow full re-sim |

**Phase 0 choice**: flush on **possession boundaries** plus **forced** flush on HT, FT, injury await, and `mark_completing` (clarification + research R2). Do not use naïve per-event inserts.

### Replay cost

- Re-sim from seed ≈ original CPU.  
- Project-from-events ≈ scan 200 JSON rows — cheaper for present-only.

### Indexing

- `(run_id, seq)` unique sufficient for recovery.  
- Avoid indexing entire payload.

### Optimizations (ordered)

1. Batch append RPC  
2. Don’t durable-store PHASE_TRANSITION spam if POSSESSION covers analytics needs  
3. Friendly skip table  
4. Retention sweeper  
5. Only then consider compression / partitioning by month

---

## Scalability

Years-long evolution: event types extend via schema_version; brains plug in; tactics are data (TransitionProfile) not hardcoded Discord buttons alone. Avoid rewriting settlement when adding event types.
