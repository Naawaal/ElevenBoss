# Contract: Post-Match Explainability UI

**Feature**: `044-match-v3-rollout`

## Source

`match_engine.v3.project_explanation(events, result=...) → Explanation`

- Input: ordered V3 event stream from the completed/recovered match.  
- Output: headline + turning_points (≤5).  
- MUST NOT invent events not in the stream.  
- Thin stream: empty turning_points allowed; headline may still be result-flavored.

## Enrichment (vs Phase-0 stub)

Prefer, when present in stream:

1. GOAL events (keep)  
2. Decisive CHANCE / SAVE patterns if no goals  
3. Decision-window / tactical-change events that materially mark a phase (when typed in stream)

Each tip SHOULD carry a short human-readable `causal_hint` (or equivalent) suitable for Discord.

## Discord presentation

Surfaces: bot and league `finalize_match` press/result embeds (existing “🔍 How it was decided” field).

| Condition | Behavior |
|-----------|----------|
| `engine_version != nss_v3` | No V3-only field required; v2 UX unchanged |
| V3 + tips available | Headline + ≤3 tip lines (`minute' — readable text`) |
| V3 + no tips | Omit field **or** headline-only minimal copy — do not fabricate moments |
| Embed send fails | Settlement already completed; log and continue |

## Auto-sim

League auto-sim that posts/finalizes through the same handler MUST pass explanation when V3 events exist (same contract as live).

## Non-goals

- Full match replay UI  
- Website timeline  
- Pre-match squad Tactics hub
