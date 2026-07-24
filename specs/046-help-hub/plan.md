# Implementation Plan: In-Discord Help Hub

**Branch**: `046-help-hub` | **Date**: 2026-07-24 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/046-help-hub/spec.md`

**US citation**: New documentation surface only — **no** economy/XP mutations, **no** schema. Approves **one** new slash command `/help` per FR-001 / AGENTS §6 (spec-gated). Does not reopen marketplace (`045`), match V3 (`044`), or website authorship (`008`).

## Summary

Ship `/help` as the single in-Discord documentation hub: button-driven categories with Back, optional topic autocomplete, embedded topic copy from one in-memory catalog, jotbird Read More / Full Documentation link buttons, and a Commands Reference harvested from the live `app_commands` tree. Guild replies are ephemeral; DM replies are not. Optional best-effort club lookup emphasizes Getting Started for unregistered users without blocking static help.

**Technical approach (Ponytail)**: Discord-only feature under `apps/discord_bot/`. One catalog module (topic prose + docs URLs), one embed builder, one ephemeral View, one thin `HelpCog`. No packages/, no migrations, no persistent views. Command harvest = `bot.tree.walk_commands()` at render time.

## Technical Context

**Language/Version**: Python 3.11+ — existing monorepo

**Primary Dependencies**: discord.py `app_commands` + `discord.ui` (Button / Link style); existing `safe_defer` / `error_embed` helpers

**Storage**: **N/A** — static catalog in process memory; optional read-only `players` existence check (fail-open)

**Testing**: pytest for catalog invariants (topic IDs, docs URL fallback, command-list chunking); Discord smoke via [quickstart.md](./quickstart.md)

**Target Platform**: Discord bot (guild + DM); Render deploy unchanged

**Project Type**: Discord bot documentation UX (new cog + catalog)

**Performance Goals**: Hub/topic first paint without waiting on DB; club check ≤ one cheap `maybe_single` and must not gate the reply if slow/failing

**Constraints**: Constitution I (no `discord` in `packages/`); AGENTS §4 defer; YAGNI — no AI help, no per-guild copy, no website page builds, no new tables; Discord limits (5 buttons/row, embed field/length caps)

**Scale/Scope**: ~4–5 Discord modules + 1 unit test file + `change_log.md` note; 9 topics + commands harvest

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| I. Monorepo | PASS | All Discord UI in `apps/discord_bot/`; no help logic in `packages/` |
| II. DB via RPC | PASS | No mutations; optional read-only club existence check |
| III. Typing / Pydantic | PASS | Typed catalog dataclasses / TypedDicts; harvest returns typed records |
| IV. Slash + defer | PASS | New `/help` only; defer immediately; ephemeral guild / non-ephemeral DM |
| V. APScheduler | PASS | Untouched |
| VI. Friendly errors | PASS | Unknown topic → hub/suggestions; expired view → “run `/help` again” |
| VII. YAGNI | PASS | Catalog + cog + view; no CMS, no Redis, no persistent help sessions |

**Post-Phase 1 re-check**: PASS — contracts forbid schema/mutations and over-built pagination; data-model is in-memory only; harvest contract keeps Commands Reference aligned with the live tree.

## Project Structure

### Documentation (this feature)

```text
specs/046-help-hub/
├── plan.md                 # This file
├── research.md             # Phase 0
├── data-model.md           # Phase 1
├── quickstart.md           # Phase 1
├── contracts/
│   ├── help-command-surface.md
│   ├── help-navigation-views.md
│   ├── help-catalog-and-docs.md
│   └── commands-reference-harvest.md
└── tasks.md                # /speckit.tasks — NOT created here
```

### Source Code (repository root)

```text
apps/discord_bot/cogs/help_cog.py              # NEW — /help + topic autocomplete + reply routing
apps/discord_bot/core/help_catalog.py          # NEW — topic catalog, docs base/fallback, format helpers
apps/discord_bot/embeds/help_embeds.py         # NEW — hub + topic embeds (color 0x00FF87)
apps/discord_bot/views/help_hub.py             # NEW — category buttons, Back, Link buttons
apps/discord_bot/core/help_commands.py         # NEW — walk tree → CommandEntry list + chunk for embeds
apps/discord_bot/main.py                       # register help_cog in cogs_list

tests/test_help_hub.py                         # NEW — catalog IDs, docs URL resolve, harvest formatting

change_log.md                                  # player-facing “/help guide” note when shipping
```

**Structure Decision**: Stay inside `apps/discord_bot/` mirroring store/marketplace patterns (`core` + `embeds` + `views` + `cogs`). No new package — help is presentation, not game math. Agent-context update script absent — skipped.

## Complexity Tracking

> No constitution violations.

| Choice | Why | Simpler alternative rejected |
|--------|-----|------------------------------|
| Central `help_catalog.py` | One place to edit prose/URLs (SC-007) | Inline strings in cog (drifts across handlers) |
| Link-style buttons for docs | Native Discord URL open; no fake “open link” copy | Footer URL only (harder to tap on mobile) |
| Harvest at Commands render | Always matches live tree (FR-011) | Hand-maintained command list (rots) |
| Non-persistent View | Help is ephemeral/session; no `add_view` needed | Persistent custom_ids (unused complexity) |

## Phase 0 / Phase 1 outputs

| Artifact | Path |
|----------|------|
| Research | [research.md](./research.md) |
| Data model | [data-model.md](./data-model.md) |
| Contracts | [contracts/](./contracts/) |
| Quickstart | [quickstart.md](./quickstart.md) |

## Implementation sketch (for tasks handoff)

1. Add `help_catalog.py` with 9 topic IDs, hub blurbs, field bodies, emoji, `docs_path` (optional), `DOCS_BASE = "https://www.jotbird.com/app"`, `resolve_docs_url(path) -> str`.
2. Add embed builders + `HelpHubView` (owner-scoped, timeout ~3–5 min).
3. Add `help_commands.py` harvest + chunk; Commands topic embed uses harvest output.
4. Add `HelpCog`: defer → optional club check → hub or topic; autocomplete from catalog IDs/labels; **not** `@guild_only` (DM support).
5. Register cog; unit tests; Discord smoke; `change_log.md`.
