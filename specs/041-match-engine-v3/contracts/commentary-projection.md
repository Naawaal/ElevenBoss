# Contract: Commentary & Projection Interfaces

**Feature**: `041-match-engine-v3`  
**Deliverable**: 6 (commentary / stats)

---

## Rule

Commentary and statistics are **projections**. They must be reproducible from the event stream (+ kickoff snapshot for names).

---

## Box score projector

```text
project_box_score(events: list[MatchEvent]) -> BoxScore
  possession_home/away
  shots_home/away
  chances_home/away
  goals_home/away
  motm_name (deterministic tie-break: first max by scoring rule, then name sort)
```

Phase 0: scoring rule stays goals×3 + assists×2 from GOAL payloads.

---

## Explainability projector (Wave 1)

```text
project_explanation(events: list[MatchEvent], result: win|draw|loss) -> Explanation
  headline: str
  turning_points: list[{minute, type, causal_hint, text_key}]
  primary_turning_seq: int
```

Text rendering may use commentary bank keys; **selection of which events matter** is deterministic from rules (e.g. last GOAL that changed lead; largest swing in projected momentum; first red/injury that caused ten_men).

---

## Commentary adapter

```text
CommentaryEngine.get_commentary(event_type, tags, variables)
```

Tags derived from projected score/minute/momentum after each event — not from a divergent mutable cache that disagrees with events.

Live UI may keep a rolling projection updated incrementally for speed; on finalize, **reproject once** from full stream for embed + rewards attribution (`key_events` built from events, not parallel ticker-only memory).

---

## Rewards attribution

`build_process_match_result_rpc` inputs (goals/assists/MOTM) must be taken from projected GOAL events for the club side — same as today’s key_events list, but sourced from canonical events.
