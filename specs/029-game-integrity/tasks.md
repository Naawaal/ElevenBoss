# Tasks: Game Integrity & State Management (US-42 Epic)

**Input**: Design documents from `/specs/029-game-integrity/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Scope rule (HARD)**: This feature folder is **epic governance only**. Tasks here MUST NOT create migrations, rewrite cogs, or implement US-42.1–42.10 runtime behavior. Child features own code after their own specify → plan → tasks. Violating this rule fails FR-015 / plan Delivery Phases.

**Tests**: Not required for epic docs (spec does not mandate new pytest for `029`). Optional smoke of existing anchors is a polish task only.

**Organization**: Tasks grouped by epic user stories (US1–US5) so each adoption slice is independently verifiable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: `[US1]` … `[US5]` maps to spec user stories
- Include exact file paths in every task description

---

## Phase 1: Setup (Epic inventory)

**Purpose**: Confirm plan artifacts are complete before adoption edits

- [x] T001 Verify all plan artifacts exist under `specs/029-game-integrity/`: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `quickstart.md`, `contracts/invariant-checklist.md`, `contracts/child-spec-template.md`, `contracts/source-of-truth-and-amendments.md`, `contracts/delivery-waves.md`, `checklists/requirements.md`
- [x] T002 [P] Confirm `.specify/feature.json` points at `specs/029-game-integrity` (update only if drifted)
- [x] T003 [P] Skim `specs/029-game-integrity/research.md` R1–R10 and note in `specs/029-game-integrity/checklists/requirements.md` Notes that plan/research are ready for Lock (no content rewrite unless a contradiction is found)

**Checkpoint**: Artifact inventory green; no runtime work started

---

## Phase 2: Foundational — SDD pointers (BLOCKS story adoption)

**Purpose**: Make US-42 discoverable from standing project rules so reviews can cite it

**⚠️ CRITICAL**: User-story adoption tasks assume these pointers exist

- [x] T004 Add a short **US-42 Game Integrity** subsection to `AGENTS.md` (near progression/economy or Section 10): cite `specs/029-game-integrity/spec.md`, require mutation PRs to name US-42 + child ID, link `contracts/invariant-checklist.md`, state that children US-42.1–42.10 own deep rules and `029` ships no migrations alone
- [x] T005 [P] Add a brief **US-42** stub under `.specify/specs/v1.0.0/spec.md` (new section near end): one-paragraph purpose + link to `specs/029-game-integrity/spec.md` + child map pointer to epic §0.3 — do not paste the full constitution
- [x] T006 Set `Status: Locked` (or `Draft → Locked` with date) on `specs/029-game-integrity/spec.md` and `specs/029-game-integrity/plan.md` headers once T004–T005 are done and product owner accepts epic defaults in Assumptions

**Checkpoint**: Engineers can find US-42 from AGENTS.md / v1.0.0 without opening chat history

---

## Phase 3: User Story 1 — Operators trust a single integrity constitution (Priority: P1) 🎯 MVP

**Goal**: One authoritative constitution + review gate; conflict resolution is explicit

**Independent Test**: Complete `specs/029-game-integrity/quickstart.md` Validation A (≥9/10) and Validation B (fill invariant checklist for one sample feature) without asking maintainers

### Implementation for User Story 1

- [x] T007 [US1] Add `specs/029-game-integrity/contracts/review-citation-example.md` with 3 sample PR/plan citation blurbs (economy change, match change, marketplace change) following `contracts/source-of-truth-and-amendments.md` §5
- [x] T008 [P] [US1] Add INV-ID index table of contents near top of `specs/029-game-integrity/spec.md` §2 (or a one-screen summary file `specs/029-game-integrity/contracts/invariant-index.md`) listing INV-01…INV-18 one-liners for quick citation
- [x] T009 [US1] Cross-link `022-v1-stability-blueprint` from `specs/029-game-integrity/spec.md` §10: clarify `022` = historical registry, US-42 = standing law (no content fork of `022`)
- [x] T010 [US1] Run Validation A + B from `specs/029-game-integrity/quickstart.md`; record pass/fail in `specs/029-game-integrity/checklists/requirements.md` Notes

**Checkpoint**: MVP — constitution is citable and reviewable; US1 demoable

---

## Phase 4: User Story 2 — Duplicate-reward resistance as process (Priority: P1)

**Goal**: Double-invoke / replay expectations are enforceable in review before children implement remaining gaps

**Independent Test**: A reviewer can map claim-login, match reward, transfer buy, pack claim, league prize to INV-08 and name the existing test or “owned by child X” gap using only epic docs

### Implementation for User Story 2

- [x] T011 [US2] Create `specs/029-game-integrity/contracts/idempotency-anchor-map.md` mapping Logical Actions → expected key pattern / existing evidence (`economy_ledger`, `match_run_id`, transfer race tests, etc.) → owner child (42.4/42.6/42.7/42.8) when incomplete
- [x] T012 [P] [US2] In `specs/029-game-integrity/contracts/idempotency-anchor-map.md`, add a “Regression anchors” section listing paths `tests/test_transfer_market_race.py`, `tests/test_economy_flows.py`, and any known MoMD/payroll idempotency tests with INV tags
- [x] T013 [US2] Extend `specs/029-game-integrity/contracts/invariant-checklist.md` with a short “Replay / double-invoke” reminder block pointing at the anchor map (no new pytest required in `029`)

**Checkpoint**: Duplicate-grant class is tracked; gaps explicitly deferred to children

---

## Phase 5: User Story 3 — Conflicting actions fail closed (Priority: P1)

**Goal**: Exclusive-state sketches + action matrix expectations are review-ready; deep matrices deferred to US-42.2

**Independent Test**: Using epic §5–§6 and checklist, reviewer can mark Listed/Hospital/Evolving/MatchLocked conflicts as Block for a hypothetical “list while in XI” change

### Implementation for User Story 3

- [x] T014 [US3] Create `specs/029-game-integrity/contracts/exclusive-state-sketch.md` consolidating epic player/club exclusive-state rules + the §6.2 conflict decision matrix (copy/condense from `spec.md`, keep epic as SoT)
- [x] T015 [P] [US3] Add a “Child obligation” callout in `specs/029-game-integrity/contracts/child-spec-template.md` §B requiring the full action×state matrix for US-42.2 / US-42.3
- [x] T016 [US3] Dry-run: annotate one existing hub flow (e.g. transfer list eligibility from `specs/017-player-transfer-market/spec.md`) against `exclusive-state-sketch.md` in a short note under `specs/029-game-integrity/contracts/exclusive-state-sketch.md` Appendix — identify any undocumented overlap for US-42.2

**Checkpoint**: Fail-closed conflicts are document-enforceable; matrix depth owned by children

---

## Phase 6: User Story 4 — Outage & ops survival (Priority: P1)

**Goal**: Fail-closed / settle-once / presentation-retry rules are explicit; deep recovery owned by 42.5/42.8

**Independent Test**: Operator can answer Top.gg down, bot offline across league deadline, Discord embed fail after settle using only epic + this phase’s contract

### Implementation for User Story 4

- [x] T017 [US4] Create `specs/029-game-integrity/contracts/outage-fail-closed.md` covering: Discord API down, Top.gg down, Render restart, guild remove/add, scheduler miss — Expected / Reasoning / Recovery pointers to `026`/`027` and children 42.5/42.8
- [x] T018 [P] [US4] Link `outage-fail-closed.md` from `specs/029-game-integrity/quickstart.md` as Validation E (read-only quiz, 5 questions)
- [x] T019 [US4] Ensure `contracts/delivery-waves.md` W3/W4 explicitly call out that league/market overlays must not invent sporting forfeits from infrastructure failure (one-sentence strengthen if missing)

**Checkpoint**: Live-service outage posture documented without implementing scheduler engine here

---

## Phase 7: User Story 5 — Incremental child delivery (Priority: P2)

**Goal**: US-42.1 can be specified next without re-litigating epic decisions; child template is kickoff-ready

**Independent Test**: Operator runs `/speckit.specify` for US-42.1 using kickoff prompt; new feature folder cites parent `specs/029-game-integrity`

### Implementation for User Story 5

- [x] T020 [US5] Create `specs/029-game-integrity/contracts/us-42.1-kickoff.md` containing the ready-to-paste `/speckit.specify` prompt for **US-42.1 Identity & Ownership** (parent path, child template obligations, INV touch list INV-01/02/09/14 family, non-goals)
- [x] T021 [P] [US5] Create `specs/029-game-integrity/contracts/child-backlog.md` listing US-42.1–42.10 with suggested short-names from `child-spec-template.md`, dependency edges from `delivery-waves.md`, and status column (`Not started` / `Specified` / `Locked` / `Implemented`)
- [x] T022 [US5] Update `specs/029-game-integrity/contracts/delivery-waves.md` W0 exit criteria to checkbox-list referencing T006 Lock + US1–US4 contracts complete
- [x] T023 [US5] Run Validation C from `specs/029-game-integrity/quickstart.md` (child template ready); optionally execute `/speckit.specify` for US-42.1 **only if** product owner requests in-session — otherwise leave kickoff doc as the handoff

**Checkpoint**: Epic can hand off to US-42.1; SC-007 path started

---

## Phase 8: Polish & Cross-Cutting

**Purpose**: Close epic adoption; no runtime polish

- [x] T024 [P] Run full `specs/029-game-integrity/quickstart.md` Validations A–D (D optional if pytest env missing); update checklist Notes with results
- [x] T025 [P] Store/update memory or team note that `029` tasks are governance-complete and next work is US-42.1 specify (optional; skip if no memory tooling) — **skipped** (children already Implemented; backlog notes epic closed)
- [x] T026 Confirm `change_log.md` needs **no** player-facing entry for epic-docs-only; if T004 AGENTS pointer is considered operator-facing only, skip changelog — if any manager-visible rule text was changed in epic Lock, add a one-line ops/dev note only when FR-014 applies
- [x] T027 Final grep under `specs/029-game-integrity/tasks.md` and `plan.md`: ensure zero tasks instruct creating `supabase/migrations/` or editing `apps/discord_bot/cogs/` from this epic — remove/rewrite any that slipped in
- [x] T028 Mark epic W0 complete in `specs/029-game-integrity/contracts/child-backlog.md` and set next action: epic closed (children Implemented; amendments only)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup**: Immediate
- **Phase 2 Foundational**: After Setup — **BLOCKS** US1–US5 adoption value
- **Phase 3 US1 (MVP)**: After Foundational
- **Phase 4 US2**: After Foundational; best after US1 citation examples exist
- **Phase 5 US3**: After Foundational; parallelizable with US2 after T006
- **Phase 6 US4**: After Foundational; parallelizable with US2/US3 after T006
- **Phase 7 US5**: After US1 MVP recommended (needs Locked epic + template); can draft kickoff in parallel once T006 done
- **Phase 8 Polish**: After desired stories complete (minimum: US1 + US5 for handoff)

### User Story Dependencies

| Story | Depends on | Notes |
|-------|------------|-------|
| US1 | Phase 2 | MVP — constitution adoption |
| US2 | Phase 2 | Process map for idempotency |
| US3 | Phase 2 | Exclusive-state review aid |
| US4 | Phase 2 | Outage posture doc |
| US5 | Phase 2 + US1 recommended | Child kickoff |

### Parallel Opportunities

- T002 || T003 after T001
- T004 || T005 in Phase 2
- After T006: T011/T012 || T014/T015 || T017/T018
- T024 || T025 in Polish

### Parallel Example: After Lock (T006)

```text
Task: T011 Create idempotency-anchor-map.md
Task: T014 Create exclusive-state-sketch.md
Task: T017 Create outage-fail-closed.md
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Complete Phase 1–2 (pointers + Lock)
2. Complete Phase 3 (US1 citation + quickstart A/B)
3. **STOP and VALIDATE**: Quickstart A/B pass
4. Demo: “reviews can cite US-42”

### Incremental delivery

1. MVP (US1) → adoption live  
2. US2–US4 contracts → review depth  
3. US5 kickoff → start `/speckit.specify` US-42.1  
4. **Do not** `/speckit.implement` this folder for match/economy/runtime work

### Suggested stop points

| Stop | When |
|------|------|
| MVP | After T010 |
| Review-ready | After T019 |
| Handoff | After T023 / T028 |

---

## Notes

- [P] = different files, no incomplete dependencies
- Story labels map to epic `spec.md` user stories, not US-42.x child IDs
- Child IDs (US-42.1…) appear only as **handoff** targets in US5
- Commit docs after each phase if committing is requested
- Avoid: migrations, cog edits, “implement all state machines,” new packages under `packages/integrity`
- **2026-07-22**: Epic governance complete (T001–T028). Children already Implemented under `030`–`035`. No migrations/cogs from this folder.
