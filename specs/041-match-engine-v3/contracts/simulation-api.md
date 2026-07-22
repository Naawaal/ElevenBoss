# Contract: Simulation API

**Feature**: `041-match-engine-v3`  
**Deliverable**: 6 (simulation)

---

## Package boundary

All types below live in `packages/match_engine/match_engine/v3/`.  
**Forbidden**: `import discord`, DB clients, wall clock for sporting outcomes.

---

## Public API (Phase 0)

```text
class SimulationEngine:
    def __init__(self, engine_version: str = "nss_v3"): ...

    def initial_context(
        self,
        *,
        home: list[MatchPlayerCard],
        away: list[MatchPlayerCard],
        home_name: str,
        away_name: str,
        home_rating: float,
        away_rating: float,
        seed: int,
        tactics_home: str = "balanced",
        tactics_away: str = "balanced",
        **injury_flags,
    ) -> MatchContext: ...

    def step(
        self,
        context: MatchContext,
        inbox: DecisionInbox | None = None,
    ) -> StepResult: ...

    def run_to_completion(
        self,
        context: MatchContext,
        *,
        decisions: list[DecisionIntent] | None = None,
        auto_resolve_injuries: bool = True,
    ) -> tuple[MatchContext, list[MatchEvent]]: ...
```

### StepResult

```text
events: list[MatchEvent]
context: MatchContext
elapsed_minutes: int          # clock advance this step
terminal: bool                # FULL_TIME emitted
awaiting_decision: bool       # injury / mandatory choice
legal_actions: list[str]      # when awaiting
replay_meta: ReplayMeta       # schema_version, engine_version, rng_draw_count, seq_start, seq_end
```

### DecisionInbox

Queue of `DecisionIntent`. Phase 0: **immediate apply** on next `step` (v2 Touchline parity).  
Window metadata may be recorded on Decision events; **fixed windows 15/30/45/60/75/85 are Wave 1 only** (`enforce_decision_windows=False` in Phase 0).

`step` returns unused intents still pending on the inbox when Wave 1 barriers apply.

---

## Adapter contracts

### Live Discord adapter

```text
ctx = engine.initial_context(...)
inbox = DecisionInbox()
while not terminal:
    # merge touchline queued intents into inbox
    result = engine.step(ctx, inbox)
    persist_batch(result.events)          # app layer
    for ev in result.events:
        present(ev)                       # commentary + sleep
        if injury interactive: wait UI → inbox.push(resolution)
    ctx = result.context
settle_existing_pipes(...)
```

### Silent / recovery adapter

```text
ctx, events = engine.run_to_completion(ctx, decisions=loaded_decisions, auto_resolve_injuries=True)
assert hash(events) == expected OR persist and settle
```

### Legacy bridge (dual-run)

`nss_v2` path keeps `stream_match`. Facade may expose `stream_match_v3` async generator that wraps `step` + sleep for drop-in experimentation — optional.

---

## Compatibility with today’s yielded dicts

Phase 0 adapter maps `MatchEvent` → battle_cog dict shape (`minute`, `type`, `score_update`, `actor`, `team`, …) so commentary/handlers change minimally.

---

## Non-goals for this API

- No HTTP server.
- No SQL inside engine.
- No Dixon-Coles calls.
