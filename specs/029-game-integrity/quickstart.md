# Quickstart: US-42 Epic Adoption & Child Kickoff

**Feature**: `029-game-integrity`  
**Purpose**: Validate that the integrity constitution is usable, then start US-42.1 — **not** to deploy runtime code from this folder.

## Prerequisites

- Repo checkout with Speckit feature active: `.specify/feature.json` → `specs/029-game-integrity`
- Read [spec.md](./spec.md) §§0–3 (framing, principles, invariants)
- Read [plan.md](./plan.md) Summary + Delivery Phases

## Validation A — Constitution comprehension (SC-001)

Without opening cogs, answer:

1. Where do coin mutations go?
2. Where do XP mutations go?
3. Can one Discord user own two clubs?
4. Who wins a concurrent transfer buy?
5. Does Discord embed authorization grant rewards?
6. Which doc wins if `017` and US-42 disagree on a race rule?
7. Does bot downtime invent league forfeits?
8. What child owns exhaustive edge cases?
9. May `029` ship a migration by itself?
10. What is the first child to specify?

**Expected answers** (paraphrase OK):

1. Economy pipeline / `apply_club_economy` (+ approved wrappers)  
2. XP pipeline / `apply_card_xp`  
3. No (INV-01)  
4. Exactly one buyer; loser unchanged (INV-13)  
5. No — presentation only; server mutates  
6. Epic invariants, then Locked child, then `017`  
7. No — fail closed / settle once / pause per league overlay  
8. US-42.10  
9. No — governance only  
10. US-42.1 Identity & Ownership  

**Pass**: ≥9/10 correct without maintainer help.

## Validation B — Review gate dry-run

1. Open [contracts/invariant-checklist.md](./contracts/invariant-checklist.md).
2. Pick any recent mutating PR or feature (e.g. evolution start, transfer buy).
3. Fill the checklist hypothetically.

**Pass**: Checklist is fillable; no INV is ambiguous for that feature.

## Validation C — Child template ready

1. Open [contracts/child-spec-template.md](./contracts/child-spec-template.md).
2. Confirm header + sections A–G are present.

**Pass**: Template can be pasted into the next `/speckit.specify` prompt.

## Validation D — Regression anchors still green (optional smoke)

Epic does not require new tests. Sanity-check existing integrity anchors if env available:

```bash
pytest tests/test_transfer_market_race.py tests/test_economy_flows.py -q
```

**Pass**: No unexpected failures unrelated to local env. Missing `DATABASE_URL` for integration tests is OK — note and continue.

## Validation E — Outage posture quiz (read-only)

Open [contracts/outage-fail-closed.md](./contracts/outage-fail-closed.md) and answer the five operator quiz questions (Top.gg, embed-after-settle, league deadline, restart, edge-catalog owner).

**Pass**: ≥4/5 correct without maintainer help.

## Operator: epic handoff (historical)

Children US-42.1–42.10 are Implemented (`030`–`035`). Kickoff prompt retained at [contracts/us-42.1-kickoff.md](./contracts/us-42.1-kickoff.md). Do **not** implement runtime under `029`.

## Out of scope for this quickstart

- Applying migrations
- Changing Discord cogs
- Filling US-42.10’s exhaustive edge catalog
- Enabling feature flags
