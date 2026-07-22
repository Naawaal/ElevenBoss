# Contract: AI Decision Interface

**Feature**: `041-match-engine-v3`  
**Deliverable**: 6 (AI)

---

## Rule

AI **never** mutates `MatchContext` or squad lists in place.  
AI only returns `DecisionIntent | None` via a **Policy**.

Phase 0: thin `BotBrain` → `DefaultPolicy` only (returns `None` for tactic changes). Adaptive / difficulty brains = Wave 3+.

---

## Interface

```text
class Policy(Protocol):
    def propose(self, decision_context: DecisionContext) -> DecisionIntent | None: ...

class BotBrain:
    """Thin wrapper holding the active Policy (DefaultPolicy in Phase 0)."""
    def propose(self, decision_context: DecisionContext) -> DecisionIntent | None: ...
```

### DefaultPolicy (Phase 0)

- Returns `None` for tactic changes (away stays Balanced).
- When `awaiting_decision` for injury: engine auto path skips brain (`auto_resolve_injuries=True` silent).

### Future brains (not required to ship)

- `AggressiveBrain` — prefers Attack/High Press at barriers when trailing.
- `DifficultyBrain` — noise on decisions; still deterministic given seed stream from decision_context.rng_view if needed.
- Learning systems — must still emit intents only.

---

## DecisionContext fields (AI-visible)

- minute, score, phase, attacking_side
- own_tactic, opponent_tactic
- legal_actions
- last_events_summary (capped)
- intensity_tier
- trailing/leading/tied flag

No raw mutable card objects — use snapshots or ids + ratings.

---

## Event emission

Accepted AI intents become `TACTICAL_DECISION` / `SUB_RESOLUTION` with `source=ai` via the same apply path as humans.
