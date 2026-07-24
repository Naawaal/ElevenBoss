# Implementation Plan: Marketplace V1.5 — Professional UX & Polish

**Branch**: `045-marketplace-ux-polish` | **Date**: 2026-07-24 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/045-marketplace-ux-polish/spec.md`

**US citation**: Extends Implemented `017` + `043`; preserve **US-42.6 Marketplace Integrity** (atomic purchase/list/agent paths, no parallel coin pipe). Prefer **zero RPC/schema changes**.

## Summary

Polish the existing `/marketplace` into a cohesive, scannable, decision-ready UX **without new market mechanics**. Surface fields already loaded (`expires_at`, rarity, fair value, discovery `recent_sales`/trend), keep market context on Buy confirm, unify naming/Back/error copy, and cut redundant board re-fetches / unbounded eligibility queries.

**Technical approach**: Discord-only + thin pure formatters. Primary edits in `apps/discord_bot/views/marketplace_transfer.py` and `apps/discord_bot/cogs/marketplace_cog.py`. Shared copy/constants in `apps/discord_bot/core/marketplace_copy.py`. Optional pure helpers (relative deadline, trend label) in `packages/economy/economy/market_intelligence.py` for unit tests. **No new migration**, slash command, or analytics-on-hub.

## Technical Context

**Language/Version**: Python 3.11+ / Postgres 15+ (Supabase) — existing stack

**Primary Dependencies**: discord.py, existing economy fair-value / discovery / sort helpers, Supabase RPCs from `086` (read-only use)

**Storage**: **No schema changes.** Reuse listing `expires_at`, `get_price_discovery`, `get_card_ownership_history`, `fair_value_coins`

**Testing**: Unit tests for presentation helpers (time-left, trend, discovery field with `recent_sales`, ask-vs-fair line); extend integrity greps only if query shapes change; Discord smoke via quickstart

**Target Platform**: Discord bot (Render) + hosted Supabase

**Project Type**: Monorepo polish (discord_bot + optional pure economy formatters)

**Performance Goals**: Board select/sort from in-memory listings after one `_board_listings` load; eligibility training queries scoped to owner/card ids; narrow `select` columns on hub/roster/scouting opens

**Constraints**: Constitution / AGENTS — no Discord in packages; no inventing market numbers; no `get_market_analytics` on hub; defer interactions; YAGNI — no favorite filters, pagination product, academy merge, new tables

**Scale/Scope**: ~2 Discord files + 1 copy module + small pure helpers/tests; phases A–F from research

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| I. Monorepo | PASS | Pure formatters in `packages/economy`; Discord copy/views in `apps/discord_bot/` |
| II. DB via RPC | PASS | No new money mutations; reuse existing purchase/list/agent/discovery RPCs |
| III. Typing / Pydantic | PASS | Typed helper inputs/outputs where new pure functions appear |
| IV. Slash + defer | PASS | Extend `/marketplace` only; keep defer |
| V. APScheduler | PASS | Expiry job unchanged |
| VI. Friendly errors | PASS | Shared ownership/session copy; insufficient-data states preserved |
| VII. YAGNI | PASS | Presentation + path + light perf; no new mechanics |

**Post-Phase 1 re-check**: PASS — contracts forbid invented prices and analytics-on-hub; data-model is presentation-only; hot-path contract documents in-memory board rules.

## Project Structure

### Documentation (this feature)

```text
specs/045-marketplace-ux-polish/
├── plan.md
├── research.md              # UX audit + decisions (already from specify)
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── board-preview-and-buy.md
│   ├── discovery-presentation.md
│   ├── marketplace-copy-language.md
│   └── marketplace-hot-path.md
└── tasks.md                 # /speckit.tasks — not created here
```

### Source Code (repository root)

```text
apps/discord_bot/core/marketplace_copy.py          # NEW — names, Back, errors, trend words
apps/discord_bot/views/marketplace_transfer.py     # board preview, time-left, fair, discovery, buy confirm, listings
apps/discord_bot/cogs/marketplace_cog.py           # hub naming, agent POT, scoped training query, scouting columns

packages/economy/economy/market_intelligence.py    # optional: relative deadline + trend label helpers
packages/economy/economy/__init__.py               # export new helpers if added
tests/test_marketplace_ux_polish.py                # NEW — presentation helpers
# or extend tests/test_market_intelligence.py

change_log.md                                      # player-facing polish note when shipping
```

**Structure Decision**: No new apps/packages. Agent-context update script absent — skipped.

## Complexity Tracking

> No constitution violations.

| Choice | Why | Simpler alternative rejected |
|--------|-----|------------------------------|
| Shared `marketplace_copy.py` | One naming/error source across cog + transfer views | Inline string edits (drift returns) |
| In-memory board after load | Matches 043 sort contract intent; fixes re-fetch smell | Keep re-fetch on every select (rejected) |

## Phase 0 / Phase 1 outputs

| Artifact | Path |
|----------|------|
| Research + audit | [research.md](./research.md) |
| Data model | [data-model.md](./data-model.md) |
| Contracts | [contracts/](./contracts/) |
| Quickstart | [quickstart.md](./quickstart.md) |

## Frozen implementation decisions

| ID | Decision |
|----|----------|
| D1 | Polish-only — reuse 017/043 backend; no new migration by default |
| D2 | No new slash commands / tables / ops analytics in Discord |
| D3 | Never invent market numbers |
| D4 | Board: one fetch per Apply (and post-mutate refresh); select/sort use memory |
| D5 | Buy confirm keeps compact fair/discovery cue |
| D6 | Product primary name: **Marketplace**; sub-areas labeled Transfer Board / Scouting / Agent / My Listings |
| D7 | Back label: `Back to Market` (optional single leading emoji policy: none on child Back) |
| D8 | Favorite filters / recently viewed / true pagination: deferred or out of scope |
| D9 | Cite US-42.6 if any purchase/list path is touched; prefer presentation-only diffs |

## Implementation phases (maps to research A–F)

| Phase | Deliverable |
|-------|-------------|
| A | Board preview + time-left + rarity + ask-vs-fair |
| B | Discovery presentation (`recent_sales`, trend) + buy-confirm context |
| C | Hub naming + Back + shared error copy |
| D | My Listings expiry + agent POT + success copy polish |
| E | In-memory board + scoped training query + narrow selects |
| F | Tests, Discord smoke, `change_log.md` |

## Next command

`/speckit.tasks` — break this plan into implementation tasks.
