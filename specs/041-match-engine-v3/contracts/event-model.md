# Contract: Event Model

**Feature**: `041-match-engine-v3`  
**Deliverable**: 4

---

## Categories (Phase 0)

Every event has `category ∈ {sporting, decision, administrative, projection}`.

| Category | Digests | Role |
|----------|---------|------|
| Sporting | Sporting + Replay | Goals, chances, cards, injuries… |
| Decision | Sporting + Replay | `TACTICAL_DECISION`, `SUB_RESOLUTION` |
| Administrative | Sporting (selected) + Replay | KICKOFF/HT/FT + scaffolding types |
| Projection | **Neither** Sporting nor Replay | Commentary-only / UI overlays |

### Three formal digests (FR-021)

1. **Sporting** — cross-version gameplay compare (excludes scaffolding + Projection).
2. **Deterministic Replay** — v3↔v3 full stream excluding Projection.
3. **Settlement** — integrity over coins/XP/fatigue/injuries/LP/history keys (caller-supplied).

Parity classes: default `exact_parity`; `stats_parity` only with documented architectural reason + drift caps.

---

## Principles

- Append-only; never edit historical events (corrections = compensating events if ever needed — YAGNI for Phase 0).
- Total order per run via `seq`.
- Schema versioned; consumers switch on `schema_version`.
- Idempotency: durable insert key `(run_id, seq)`; flush retries safe.

---

## Envelope (all events)

| Field | Type | Notes |
|-------|------|-------|
| run_id | uuid | Durable run (nullable only for pure offline tests) |
| seq | int | 1..N |
| schema_version | int | start = 1 |
| engine_version | text | `nss_v3` |
| minute | int | match clock after event |
| type | enum string | see catalog |
| side | home\|away\|neutral | when applicable |
| payload | object | type-specific |
| causal_hint | string\|null | short machine key for explainability e.g. `turnover_build_up` |

---

## Event catalog (Phase 0 minimum)

| type | payload (core) | Notes |
|------|----------------|-------|
| KICKOFF | home_name, away_name | once |
| PHASE_TRANSITION | from, to, attacking_side | optional verbosity; may be omitted if derived — **Phase 0: emit for possession-significant transitions only** |
| POSSESSION | side, reason | midfield win, counter steal, etc. |
| FOUL | actor_name, card_id? | |
| YELLOW_CARD | actor_name, card_id? | |
| CHANCE | actor_name, team, zone? | |
| SHOT | actor_name, on_target bool | optional split from SAVE/MISS/GOAL |
| SAVE | actor_name (GK) | |
| MISS | actor_name | |
| GOAL | actor_name, assister_name?, card_ids? | score implied by projection |
| HALF_TIME | score | |
| FULL_TIME | score | terminal |
| INJURY | card_id, name, tier, interactive, options | |
| SUB_RESOLUTION | kind, injured_id, replacement_id?, play_on | |
| TACTICAL_DECISION | style, stance_modifier, source | human/ai |
| MOMENTUM_DECAY | — | optional; or fold into phase | 

Phase 0 may keep yielding Discord-compat dicts **and** canonical `MatchEvent` models (adapter maps both) to reduce blast radius.

Wave 2+ may add: `INTERCEPTION`, `PRESS_TRIGGER`, `LONG_BALL`, etc., as first-class types for distinguishability.

---

## Ordering rules

1. Monotonic `seq`.
2. `minute` non-decreasing (equal minutes allowed for simultaneous logical events).
3. `FULL_TIME` last sporting event; no sporting events after.
4. Decision events that alter tactics appear **before** subsequent phase rolls that must observe them.

---

## Replay strategy

1. Load kickoff snapshot + `sim_seed` + `engine_version` + ordered decisions (or full events).
2. **Preferred recovery**: `run_to_completion` with decision inbox rebuilt from `TACTICAL_DECISION` / `SUB_RESOLUTION` events already accepted **or** from parallel decision log table/fields — regenerate events and verify hash against stored (detect drift).
3. **Presentation recovery**: if events stored complete through FT, project box score without re-sim; still allow re-sim for integrity audit.
4. Hash: canonical JSON serialize events `(seq,type,minute,payload_canonical)` → sha256.

---

## Idempotency

- Insert `ON CONFLICT (run_id, seq) DO NOTHING`.
- Settlement remains keyed by `run_id` / history — independent of event flush retries.
- Re-flush overlapping batches must not fork seq allocation — allocator is engine-side counter flushed transactionally with rows.

---

## Versioning

- Additive payload fields: minor, same schema_version OK if consumers ignore unknowns.
- Renames/removals/semantic changes: bump `schema_version`; add projector branch or migrator.
- Engine logic changes that alter outcomes: bump `engine_version` (`nss_v3.1`) even if schema same — pin on run.
