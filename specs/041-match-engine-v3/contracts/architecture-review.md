# Contract: Current Architecture Review & Gap Analysis

**Feature**: `041-match-engine-v3`  
**Deliverables**: 1 (review) + 2 (gap analysis)

---

## 1. Current Architecture Review (NSS v2)

### Strengths

- **Seeded RNG** per match (`sim_seed`) and bot squad xor-seed — recovery-capable.
- **Settle-once / locks / match_runs** (US-42.4) — strong integrity shell around the sim.
- **Highlight Markov phases** produce readable live drama + commentary bank.
- **Immersion fixes** (5% floor, possession ticks, named bot XI) already shipped.
- **Injury interactive path** with auto-resolve for silent/AI.
- **Pure package boundary** largely respected (`match_engine` has no Discord).
- **Parallel interval Dixon-Coles engine** exists for future calibration without blocking live.

### Weaknesses

- **Generator + Discord loop coupling**: sporting control flow interleaved with `asyncio.sleep` and UI mutation (`TouchlineView` writes `MatchState` directly).
- **Live counters as parallel truth**: `MatchLiveStats` updated inside sim; recovery must re-run generator — fine today, but stats ≠ durable event log.
- **No durable ordered event store**: restart relies on full re-sim; mid-match human decisions are not a first-class log.
- **Dual engines mental overhead**: interval engine unwired but exported; v0 `simulator.py` still in facade.
- **Spec/code drift**: plan docs mention `/100`; code uses `/55`.
- **Explainability**: managers see commentary flavor, not structured causal chains.

### Bottlenecks

- Discord presentation latency (intentional) — not CPU.
- League auto-sim volume fine at current CPU cost; risk is **future** event DB write amplification if naïvely one-insert-per-event.
- Injury pause + touchline both mutate shared state — racey under reconnect/spam.

### Technical debt

- `stream_match` owns too much (phases + injuries + stats).
- Touchline not replay-safe.
- Friendly vs competitive paths duplicated in battle_cog size.
- Interval engine / NSS fusion undefined (correctly deferred).

---

## 2. Gap Analysis: NSS v2 → V3

| Area | v2 | v3 target | Change |
|------|----|-----------|--------|
| Control flow | `async for` generator | `step()` / `run_to_completion` | Extract core; adapters wrap |
| State | Mutable `MatchState` shared with Discord | Immutable `MatchContext` per step | Stop UI from mutating sim internals |
| Decisions | Direct field writes | `DecisionIntent` → events at barriers | Replay-safe |
| SoT | Live stats + yielded dicts | Versioned `MatchEvent` stream | Projectors |
| Durability | seed + snapshot; re-sim | + `match_events` (bot/league) | Recovery/analytics |
| Tactics | Stance multipliers only | Transition profiles (Wave 2) | Behaviour not just % |
| AI | Passive squad / auto injury | `BotBrain` intents | Decouple |
| Dixon-Coles | Unwired twin | Offline calibration only | Explicit non-goal for live |
| Migration | N/A | `engine_version` pin + flag | Dual-run |
| Explainability | Commentary prose | Structured projection (Wave 1) | FR-014 |
| Integrity shell | US-42.4 | **Unchanged ownership** | Adapters only |

### What must not change

- Reward RPC ownership and order (economy → history → XP → fatigue/injury).
- Friendly sandbox.
- Lock acquire/release semantics.
- Package/discord import ban.

### Behavioural parity bar (Phase 0)

Golden seeds: v3 Balanced + legacy stance mapping should match v2 event digests for no-decision matches (exact preferred; document any intentional tie-break fixes).
