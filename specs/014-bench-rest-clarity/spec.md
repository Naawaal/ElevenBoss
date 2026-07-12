# Feature Specification: Bench Rest Clarity & Investigation

**Feature Branch**: `014-bench-rest-clarity`

**Created**: 2026-07-12

**Status**: Implemented

**Input**: User description: "Despite staying on the bench, players didn't recover fatigue after I played 2 matches — is this a bug?"

**Reporter update (2026-07-12)**: Those matches were **bot** matches (not friendlies). Friendly sandbox is ruled out. Affected cards had **fatigue = 0** and were **on the bench** — “already at 100” is ruled out.

## Verdict (investigation)

**Treat as a defect until proven otherwise.** Bot path is wired and config is live (+25), but a fatigue-0 bench card not moving after bot matches means fitness did not apply to that card (crash-window skip, silent RPC failure, or card outside the rested top-7).

### What the code does today

| Match type | Starter fatigue drain | Bench rest (+25, cap 100) |
|------------|----------------------|---------------------------|
| **Bot** (`/battle` vs AI) | Yes | Yes |
| **League** | Yes | Yes |
| **Friendly** | **No** (sandbox) | **No** |

Bench rest rules (bot/league only):

- Players **not** in that match’s starting XI, not injured, not retired.
- Only the **first 7** such players from an unordered roster query get rest (`fetch_bench_ids` → `[:7]`).
- Amount: **`fatigue_bench_per_match`** (default **+25**), capped at **100**.
- Injured bench players are skipped.

For this report (**fatigue 0 + bench + bot**), remaining explanations: fitness never committed for the match, card not in the **unordered top-7** rested set, or silent RPC failure. Cap-100 does not apply.

### Confirmed / high-priority gaps (plan)

1. **Crash-window**: XP marked applied before fitness; reward helpers early-return on `xp_applied_at` and can **skip fatigue forever** after one failed fitness call.
2. **Unordered top-7** — which unused cards rest is undefined; manager’s watched reserve may never be in the set.
3. **No player-facing feedback** that bench rest applied or failed.
4. Post-match fitness errors are **logged and swallowed**.
5. Confusion with **daily passive** (+30 at TG1) — separate from match bench rest.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Know When Bench Rest Applies (Priority: P1)

As a manager, I understand that only **bot and league** matches grant bench rest, friendlies do not, and fitness never goes above 100.

**Why this priority**: Answers the reported confusion without assuming a code defect.

**Independent Test**: Play one friendly and one bot match with a mid-fatigue unused reserve; compare fatigue before/after.

**Acceptance Scenarios**:

1. **Given** a friendly match finishes, **When** I check an unused reserve’s fatigue, **Then** it is unchanged by that match (sandbox).
2. **Given** a bot or league match finishes and a healthy unused reserve was among the rested set, **When** I check fatigue, **Then** it increased by up to **+25** (cap 100).
3. **Given** a reserve already at **100** fatigue, **When** they sit a bot/league match, **Then** fatigue stays **100** (no visible “recovery”).

---

### User Story 2 - Confirm Bot/League Rest Actually Ran (Priority: P2)

As a manager, after a competitive match I can tell that bench rest was applied (or why a named player did not get it).

**Why this priority**: Separates “silent success at cap” from true failures.

**Independent Test**: After a bot match, UI or ephemeral summary mentions bench rest count or points; or profile fatigue moved for a known mid-fatigue bench player.

**Acceptance Scenarios**:

1. **Given** a bot/league match with at least one mid-fatigue unused reserve in the rested set, **When** the match completes, **Then** that card’s stored fatigue is higher than before (unless capped).
2. **Given** post-match fitness RPC fails, **When** the match completes, **Then** the failure is not totally silent to the manager **or** is at least reliably alerted to ops (product choice in plan).

---

### User Story 3 - Fair Rest for Larger Squads (Priority: P3)

As a manager with more than 7 reserves, which unused players get bench rest is predictable (e.g. highest OVR, or all unused squad members).

**Why this priority**: Only matters if US1 confirms they played bot/league and mid-fatigue reserves still never move.

**Independent Test**: Squad with 10+ unused healthy reserves; after one bot match, document who gained +25.

**Acceptance Scenarios**:

1. **Given** more than 7 unused healthy reserves, **When** a bot match ends, **Then** the set who receive rest follows a published rule (not an arbitrary DB order).

---

### Edge Cases

- Substitutes who **entered** the match: still identified by starting-XI vs not — a player who began on the bench and subbed on may still be treated as “bench” for the fatigue RPC if only kickoff XI is passed as starters (investigate in plan if reports mention subs).
- Injured reserves: no bench rest.
- Cap 100: two matches cannot add +50 if starting at 90 (only +10 then 0).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Spec/docs/changelog MUST state clearly: bench rest is **bot + league only**; friendlies are sandbox for fatigue.
- **FR-002**: Before treating “no bench recovery” as a defect, verify match type, pre-match fatigue, injury, and whether the card was in the rested set of ≤7.
- **FR-003**: If investigation confirms bot/league mid-fatigue unused reserves do not move when passed in `bench_ids`, that is a **defect** and MUST be fixed (RPC/wiring).
- **FR-004**: Optional UX: surface bench-rest outcome after competitive matches (count rested or “already fresh”).
- **FR-005**: Optional fairness: define deterministic who gets rest when unused pool &gt; 7 (or rest all unused).
- **FR-006**: No new slash commands required for the investigation outcome doc; UX changes reuse existing match end / profile surfaces.

### Key Entities

- **Bench rest**: +25 fatigue (config) for unused competitive reserves.
- **Sandbox friendly**: no fatigue writes.
- **Rested set**: up to 7 healthy non-starters.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A manager can answer “will this match rest my bench?” from published rules (bot/league yes, friendly no).
- **SC-002**: Reproduction on bot match with fatigue ~50 unused reserve shows +25 (or to 100) after one match when wiring is healthy.
- **SC-003**: If a wiring bug is found, it is fixed and covered by a small automated or ops check; if not, the report is closed as expected behavior with clearer copy.

## Assumptions

- Reporter’s two matches were **bot** (confirmed).
- `fatigue_bench_per_match = 25` is live (verified on ElevenBoss Supabase 2026-07-12).
- Silent `except` + XP-before-fatigue gate are in scope to fix; friendlies stay sandbox.

## Out of Scope

- Changing friendly sandbox to apply fatigue (unless explicitly requested later).
- Retuning +25 amount.
- Daily TG passive (separate from match bench rest).
