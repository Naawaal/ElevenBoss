# Tasks: In-Discord Help Hub

**Input**: Design documents from `/specs/046-help-hub/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included — plan/quickstart require `tests/test_help_hub.py` for catalog IDs, docs URL fallback, and command-list formatting. No full Discord integration suite (smoke via quickstart).

**Locked decisions** (research.md / plan.md):
- Discord-only under `apps/discord_bot/` — no `packages/`, no migration, no persistent views
- One new slash command `/help` (not `@guild_only`); guild ephemeral / DM non-ephemeral
- Catalog in `help_catalog.py`; docs base `https://www.jotbird.com/app`
- Commands Reference from `bot.tree.walk_commands()` at render time
- Fail-open club check; never `ensure_registered` on `/help`

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: US1–US5 maps to spec user stories
- Exact file paths required

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm touch list and create empty module shells

- [x] T001 Grep existing hub patterns (`safe_defer`, `StoreHubView`, `cogs_list` in `apps/discord_bot/main.py`) and confirm no existing `/help` command; align touch list with `specs/046-help-hub/plan.md`
- [x] T002 [P] Create stub modules `apps/discord_bot/core/help_catalog.py`, `apps/discord_bot/core/help_commands.py`, `apps/discord_bot/embeds/help_embeds.py`, `apps/discord_bot/views/help_hub.py`, `apps/discord_bot/cogs/help_cog.py` with module docstrings / `from __future__ import annotations` only (wire later)

**Checkpoint**: Touch list known; stub files exist

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Catalog schema + docs resolver + catalog unit tests — **MUST land before story UX wiring**

**⚠️ CRITICAL**: No Discord story work until catalog IDs and `resolve_docs_url` are testable

- [x] T003 Implement `HelpTopic` records, `DOCS_BASE`, `resolve_docs_url()`, `get_topic()`, `list_topics()`, and stub bodies for all nine required IDs in `apps/discord_bot/core/help_catalog.py` per `contracts/help-catalog-and-docs.md` and `data-model.md` (`commands` may use `is_commands=True` with empty fields)
- [x] T004 [P] Create `tests/test_help_hub.py` asserting exact topic ID set, unique IDs, and `resolve_docs_url(None/"")` → `https://www.jotbird.com/app` plus a non-empty path joining under the base
- [x] T005 Register `apps.discord_bot.cogs.help_cog` in `apps/discord_bot/main.py` `cogs_list` (cog may still be a no-op until US1)

**Checkpoint**: `pytest tests/test_help_hub.py -q` green for catalog/docs; cog loadable

---

## Phase 3: User Story 1 — Browse help from an interactive hub (Priority: P1) 🎯 MVP

**Goal**: `/help` opens an interactive hub; category buttons show topic embeds; Back returns to hub; Full Documentation link works; guild replies are ephemeral

**Independent Test**: In a guild channel, `/help` → see hub (only invoker) → open two categories → Back each time → Full Documentation opens jotbird `/app`

**Contracts**: [help-command-surface.md](./contracts/help-command-surface.md), [help-navigation-views.md](./contracts/help-navigation-views.md)

### Implementation for User Story 1

- [x] T006 [P] [US1] Implement `build_help_hub_embed()` and `build_help_topic_embed()` in `apps/discord_bot/embeds/help_embeds.py` (color `0x00FF87`, hub blurbs, topic fields, docs footer cue)
- [x] T007 [US1] Implement owner-scoped `HelpHubView` / topic view in `apps/discord_bot/views/help_hub.py`: category buttons (≤5/row), Back, Link Full Documentation + Read More, timeout disable, non-owner soft reject, stale → “run `/help` again”
- [x] T008 [US1] Implement `/help` in `apps/discord_bot/cogs/help_cog.py`: immediate defer via `safe_defer`, `ephemeral=(guild_id is not None)`, **not** `@guild_only`, open hub with view; no topic option yet
- [x] T009 [US1] Wire hub↔topic message edits in `apps/discord_bot/views/help_hub.py` + `help_cog.py` so navigation edits the same help message (no public channel spam)

**Checkpoint**: US1 MVP — hub browse works in guild with stub catalog copy

---

## Phase 4: User Story 3 — Learn systems without leaving Discord (Priority: P1)

**Goal**: Every required category has substantive embedded guidance (not link-only); Ranked marked coming soon; Read More uses resolved docs URL

**Independent Test**: Open each category; each has enough text to understand purpose + next hub command; Read More / footer points at jotbird base (or mapped path)

**Contract**: [help-catalog-and-docs.md](./contracts/help-catalog-and-docs.md)

### Implementation for User Story 3

- [x] T010 [P] [US3] Author full embedded fields for `getting-started` (include Core Loop) and `battle` (Ranked coming soon) in `apps/discord_bot/core/help_catalog.py`
- [x] T011 [P] [US3] Author full embedded fields for `squad`, `training`, and `evolutions` in `apps/discord_bot/core/help_catalog.py`
- [x] T012 [P] [US3] Author full embedded fields for `league`, `economy`, and `hospital` in `apps/discord_bot/core/help_catalog.py` (live fidelity only — no invented mechanics)
- [x] T013 [US3] Ensure topic embeds show footer and/or Link Read More via `resolve_docs_url` in `apps/discord_bot/embeds/help_embeds.py` and `apps/discord_bot/views/help_hub.py`; set optional `docs_path` values only when safe (else empty → base)

**Checkpoint**: US3 — all non-commands topics are useful in Discord without the website

---

## Phase 5: User Story 2 — Jump straight to a topic (Priority: P2)

**Goal**: Optional `/help topic:` with autocomplete lands on the topic embed; unknown topic recovers softly

**Independent Test**: Autocomplete suggests topics; `/help topic:league` opens League; invalid topic → hub or clear recovery (no traceback)

**Contract**: [help-command-surface.md](./contracts/help-command-surface.md)

### Implementation for User Story 2

- [x] T014 [US2] Add optional `topic` parameter + autocomplete from catalog IDs/labels in `apps/discord_bot/cogs/help_cog.py`
- [x] T015 [US2] Route valid topic to topic embed+view; invalid/empty → hub with short notice (or listed valid topics) in `apps/discord_bot/cogs/help_cog.py`

**Checkpoint**: US2 — power-user shortcut works alongside hub buttons

---

## Phase 6: User Story 4 — Discover all slash commands (Priority: P2)

**Goal**: Commands Reference lists live slash commands with descriptions; admin/owner commands marked, not hidden

**Independent Test**: Open Commands; list matches registered tree; `/admin` (or equivalent) shows Admin/owner-only note

**Contract**: [commands-reference-harvest.md](./contracts/commands-reference-harvest.md)

### Tests for User Story 4

- [x] T016 [P] [US4] Extend `tests/test_help_hub.py` for command-list formatting: restricted label, empty description placeholder, chunking/empty-list calm copy (pure fixtures — no live Discord client required)

### Implementation for User Story 4

- [x] T017 [US4] Implement `CommandEntry` harvest via `bot.tree.walk_commands()` and format/chunk helpers in `apps/discord_bot/core/help_commands.py` per contract (mark `default_permissions` / custom checks as restricted)
- [x] T018 [US4] When rendering `commands` topic, inject harvested lines into embed in `apps/discord_bot/embeds/help_embeds.py` (and call site in `apps/discord_bot/views/help_hub.py` / `help_cog.py`); empty tree → calm empty state, not crash

**Checkpoint**: US4 — Commands Reference stays aligned with the live tree

---

## Phase 7: User Story 5 — New managers and DM users (Priority: P3)

**Goal**: Unregistered users see Getting Started emphasis; DMs show help non-ephemerally; static help never blocked by DB

**Independent Test**: No-club user → hub emphasizes Getting Started; DM `/help` visible in DM; DB blip still serves static hub

**Contract**: [help-command-surface.md](./contracts/help-command-surface.md)

### Implementation for User Story 5

- [x] T019 [US5] Add best-effort `players` existence check (fail-open) in `apps/discord_bot/cogs/help_cog.py`; pass `emphasize_getting_started` into hub embed builder in `apps/discord_bot/embeds/help_embeds.py` — do **not** use `ensure_registered`
- [x] T020 [US5] Verify DM path: non-ephemeral send/edit in `apps/discord_bot/cogs/help_cog.py` / `apps/discord_bot/views/help_hub.py`; confirm `/help` remains without `@guild_only`

**Checkpoint**: US5 — onboarding emphasis + DM support complete

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Ship hygiene and validation

- [x] T021 [P] Add player-facing `/help` note to `change_log.md`
- [x] T022 Run `pytest tests/test_help_hub.py -q` and complete Discord smoke A–E from `specs/046-help-hub/quickstart.md`
- [x] T023 Confirm no schema/migration files added and no economy/XP mutations from help paths (grep `help_cog` / `help_hub` for RPC writes)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Start immediately
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS** all user stories
- **US1 (Phase 3)**: After Foundational — MVP hub
- **US3 (Phase 4)**: After US1 (needs hub to read content); catalog prose tasks T010–T012 can draft in parallel
- **US2 (Phase 5)**: After US1 (extends same cog)
- **US4 (Phase 6)**: After US1 (Commands is a hub category); ideally after US3 so other topics are already solid
- **US5 (Phase 7)**: After US1 (hub exists); can follow US2/US4
- **Polish (Phase 8)**: After desired stories complete

### User Story Dependencies

| Story | Depends on | Notes |
|-------|------------|-------|
| US1 Hub browse | Phase 2 | MVP — no dependency on US2–US5 |
| US3 Content | US1 | Same catalog; fills stub bodies |
| US2 Topic shortcut | US1 | Same `/help` command |
| US4 Commands harvest | US1 | Commands category already on hub |
| US5 Onboarding/DM | US1 | Ephemeral branching should already exist from US1 |

### Parallel Opportunities

- T002 stub files in parallel after T001
- T004 tests alongside T003 (write failing then pass)
- T006 embeds can start once T003 catalog API exists
- T010 / T011 / T012 content authoring in parallel (different topic groups, same file — coordinate or sequential edits to `help_catalog.py`)
- T016 tests parallel before/with T017
- T021 changelog parallel with T022 smoke prep

---

## Parallel Example: User Story 3

```text
# Content batches (coordinate if same file):
Task: "Author getting-started + battle in apps/discord_bot/core/help_catalog.py"
Task: "Author squad + training + evolutions in apps/discord_bot/core/help_catalog.py"
Task: "Author league + economy + hospital in apps/discord_bot/core/help_catalog.py"
```

---

## Parallel Example: Foundational

```text
Task: "Implement catalog + resolve_docs_url in apps/discord_bot/core/help_catalog.py"
Task: "Create tests/test_help_hub.py for IDs and docs URL fallback"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 Setup  
2. Phase 2 Foundational (catalog stubs + tests + cog register)  
3. Phase 3 US1 hub navigation  
4. **STOP and VALIDATE**: Guild `/help` hub → category → Back → Full Documentation  
5. Demo if ready (stub copy OK)

### Incremental Delivery

1. Setup + Foundational → foundation ready  
2. US1 → hub MVP  
3. US3 → real documentation value  
4. US2 → autocomplete shortcut  
5. US4 → live Commands Reference  
6. US5 → unregistered + DM polish  
7. Polish → changelog + quickstart smoke  

### Suggested MVP scope

**US1 only** (Phases 1–3): interactive hub with stub topic text is enough to prove navigation, ephemeral behavior, and docs link before investing in full copy/harvest.

---

## Notes

- [P] = different files or safely parallel; same-file catalog content tasks marked [P] only as authoring batches — merge carefully
- Do not add migrations, packages, or persistent `bot.add_view` for help
- Commit after each phase checkpoint when implementing
- Stop at any checkpoint to validate the story independently via quickstart scenarios
