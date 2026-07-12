# Research: Bench Rest Clarity

**Feature**: `014-bench-rest-clarity` | **Date**: 2026-07-12

**Reporter**: Bench players did not recover after **2 bot matches** (confirmed — not friendlies). Cards at **fatigue = 0**, on the **bench** — cap-100 ruled out; expect +25 if rest ran for that card.

---

## R1 — Is the bot path missing a call site?

**Decision**: **No** — bot matches do call fitness with bench IDs.

**Evidence**:
- `battle_cog` → `apply_bot_match_rewards(..., bench_ids=await fetch_bench_ids(...))`
- `match_rewards.apply_bot_match_rewards` → `apply_post_match_fitness` → RPC `apply_match_fatigue`
- Live `game_config.fatigue_bench_per_match = 25` (queried 2026-07-12)

**Implication**: “Never wired” is false for current repo. Remaining causes are gate/skip bugs, selection, cap, or silent exceptions.

---

## R2 — Crash window: XP marked before fatigue

**Decision**: Treat as a **real defect** to fix.

**Evidence**:
```text
apply_match_xp_if_needed  →  mark_match_xp_applied
then try apply_post_match_fitness
except: log only
```

On entry:
```text
if existing and xp_applied_at: return  # skips fitness entirely
```

Same pattern in `league_rewards.py`.

**Scenario**: Fitness/injury RPC fails once after XP succeeds → retry (or any second entry) returns early → **no bench rest and no starter drain** for that match, forever. Manager sees rewards/XP but “bench didn’t recover.”

**Alternatives**:
| Option | Rejected because |
|--------|------------------|
| Re-run fitness whenever XP already set | Double +25 / double drain on healthy retries |
| Move fitness before XP mark | XP failure retry would still double-apply fatigue |
| **`fatigue_applied_at` gate** | Chosen — mirrors XP crash-safety |

---

## R3 — Unordered top-7 bench selection

**Decision**: Keep max **7** rested cards (matches touchline bench size); make selection **deterministic** by **overall DESC**.

**Evidence**: `fetch_bench_ids` loads all non-starter healthy cards with no `ORDER BY`, then `[:7]`. PostgREST order is undefined. Managers watching a specific mid-table reserve may never receive rest while seven other unused cards do.

**Alternatives**:
| Option | Rejected for MVP because |
|--------|---------------------------|
| Rest **all** unused | Larger balance change; out of current YAGNI |
| Rest only formal “bench” slots | No separate bench assignment table beyond XI |

---

## R4 — Cap 100 and UX silence

**Decision**: Ship match-end copy + clearer docs; treat “already 100” as expected, not a bug.

**Rationale**: Two bot matches at +25 cannot move cards already at 90–100 beyond the cap in a visible way. Today there is no Discord signal that rest ran.

---

## R5 — Friendlies

**Decision**: Out of scope — sandbox stays. Not this report.

---

## R6 — Silent `except` around fitness

**Decision**: Keep match rewards succeeding (coins/XP already applied) but **surface** a short manager-visible warning and retain exception log. Optionally return fitness result for embed footer.

---
