# Implementation Plan: Marketplace Intelligence & Market Analytics

**Branch**: `043-marketplace-intelligence` | **Date**: 2026-07-24 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/043-marketplace-intelligence/spec.md`

**US citation**: Extends Locked `017` P2P market; mutating work cites **US-42.6 Marketplace Integrity** (append-only sale facts, atomic purchase path, no parallel coin pipe).

## Summary

Make the existing `/marketplace` **observable and data-driven** without new market mechanics: enrich completed-sale history with fair value + attribute snapshots, add append-only ownership career trails, expose real-data price discovery and Transfer Board sorts to managers, and give operators queryable market analytics — all by extending `transfer_sales_log` / purchase RPCs and pure helpers in `packages/economy`.

**Technical approach**: Migration **`086_marketplace_intelligence.sql`** — ALTER `transfer_sales_log` (snapshot columns + indexes); new `card_ownership_history` (no cascade-delete with cards); helpers to open/close ownership segments; REPLACE `purchase_transfer_listing` (+ agent-sale close, optional scouting/youth open); RPCs `get_price_discovery` + `get_market_analytics`; `game_config` knobs for cohort minimum/window. Pure cohort/sort/value math in `packages/economy`. Discord: extend `marketplace_transfer.py` / cog only (sort select, listing detail discovery + career, list-flow discovery). Ops analytics via RPC + documented SQL — no admin Discord dashboard. No new slash command.

## Technical Context

**Language/Version**: Python 3.11+ / Postgres 15+ (Supabase)

**Primary Dependencies**: discord.py, supabase async client, pydantic, existing `economy` + `transfer_market` helpers, APScheduler (unchanged expiry job)

**Storage**: Supabase — ALTER `transfer_sales_log`; new `card_ownership_history`; RLS + verify guards; `game_config` keys; RPCs in migration `086`

**Testing**: pytest for cohort/median/trend/sort/Best Value pure helpers; RPC write invariants via unit/smoke patterns already used for transfer market; Discord smoke via quickstart

**Target Platform**: Discord bot (Render/Linux) + hosted Supabase

**Project Type**: Monorepo feature (packages + discord_bot + migrations)

**Performance Goals**: Board browse stays on existing ≤50 fetch / ≤25 select bound; price discovery one RPC (or one indexed query) per open; purchase path remains single transaction under Discord defer; analytics ops-only (not on every hub open)

**Constraints**: Constitution / AGENTS.md — no `discord` in `packages/`; coins only via `apply_club_economy`; new columns/RPCs only in new migration; defer interactions; no new slash command; no parallel sale log; YAGNI — no auctions, featured listings, weekly Discord reports, player analytics dashboard

**Scale/Scope**: 1 migration; ~1 new pure module (or extend `transfer_market.py`); marketplace views/cog extension; optional thin ops SQL doc; feature reuses P2P flag (no second flag)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| I. Monorepo | PASS | Cohort/sort/median/trend pure logic in `packages/economy`; Discord only in `apps/discord_bot/` |
| II. DB via RPC | PASS | History + ownership writes inside `purchase_transfer_listing` (and agent close / acquisition helpers); analytics/discovery read RPCs; no app-loop multi-row money mutations |
| III. Typing / Pydantic | PASS | Typed discovery/analytics result models at package boundary |
| IV. Slash + defer | PASS | Extend `/marketplace` only; defer before RPC/DB |
| V. APScheduler | PASS | No new required job for MVP; expiry job unchanged; daily rollup table deferred (on-read analytics) |
| VI. Friendly errors | PASS | Insufficient-data and empty career states as embeds, not tracebacks |
| VII. YAGNI | PASS | Enrich existing sales log; no second marketplace; ops analytics not a Discord admin hub; pack acquisition wiring deferred to lazy ensure |

**Post-Phase 1 re-check**: PASS — contracts keep purchase atomicity and tax burn; ownership history uses non-cascading `card_id`; discovery invents nothing below min sales; sorts operate on already-loaded board set.

## Project Structure

### Documentation (this feature)

```text
specs/043-marketplace-intelligence/
├── plan.md                 # This file
├── research.md             # Phase 0
├── data-model.md           # Phase 1
├── quickstart.md           # Phase 1
├── contracts/
│   ├── transfer-history-enrichment.md
│   ├── ownership-history.md
│   ├── price-discovery.md
│   ├── transfer-board-sort.md
│   ├── market-analytics.md
│   └── marketplace-intelligence-ui.md
└── tasks.md                # /speckit.tasks — not created here
```

### Source Code (repository root)

```text
supabase/migrations/086_marketplace_intelligence.sql
supabase/scripts/verify_required_schema.sql          # extend guards
scratch/apply_migration_086.py                       # follow existing apply pattern

packages/economy/economy/transfer_market.py          # extend — sort keys, best-value ratio
packages/economy/economy/market_intelligence.py      # NEW — cohort match, avg/median/trend, insufficient-data gate
packages/economy/economy/__init__.py                 # exports

apps/discord_bot/cogs/marketplace_cog.py             # optional hub copy / entry wiring
apps/discord_bot/views/marketplace_transfer.py       # sort UI, price discovery, career trail embeds
apps/discord_bot/embeds/…                           # only if existing embed helpers need a thin addition

tests/test_market_intelligence.py                   # NEW — cohort, median, trend, sort, best-value
tests/test_transfer_market_math.py                   # extend if tax/bounds helpers touched
tests/test_marketplace_integrity_guards.py           # extend greps for purchase history write if pattern fits

change_log.md                                        # on implement ship (player-facing discovery/history/sort)
```

**Structure Decision**: Extend existing marketplace + economy layout; do not add apps, packages, or slash commands. Agent-context update script is not present in this repo — skipped.

## Complexity Tracking

> No constitution violations requiring justification.

| Choice | Why | Simpler alternative rejected |
|--------|-----|------------------------------|
| New `card_ownership_history` table | Sales log is sale-centric (buyer/seller pairs); career trail needs open segments + non-sale acquisitions | Deriving trail only from `transfer_sales_log` loses first owner and agent-sale end |
| On-read analytics RPC (no daily table in MVP) | Spec needs queryable facts; materialization can wait until volume hurts | Nightly rollup job adds scheduler surface without proven need |

## Phase 0 / Phase 1 outputs

| Artifact | Path |
|----------|------|
| Research + decisions | [research.md](./research.md) |
| Data model | [data-model.md](./data-model.md) |
| Contracts | [contracts/](./contracts/) |
| Quickstart | [quickstart.md](./quickstart.md) |

## Frozen implementation decisions (from research)

| ID | Decision |
|----|----------|
| D1 | Enrich `transfer_sales_log` in place (ALTER + purchase INSERT); do **not** create a parallel sale history table |
| D2 | Snapshot at sale: `fair_value_coins`, `rarity`, `role` (position), `overall`, `potential`, `age_at_sale`, `player_name` |
| D3 | New `card_ownership_history` with `card_id` **without** FK CASCADE to `player_cards` (survives agent DELETE) |
| D4 | Ownership: close seller open segment + open buyer segment inside `purchase_transfer_listing`; close on `process_agent_sale` before DELETE |
| D5 | Lazy `ensure_ownership_open` for cards with no rows when career UI opens (via=`legacy_bootstrap`); wire scouting/youth sign opens in migration if REPLACE cost is small; **defer** every pack INSERT path |
| D6 | Cohort: same `role` + `rarity`, `overall` within ±`price_discovery_ovr_window` (default 3); min sales = `price_discovery_min_sales` (default 5) |
| D7 | Trend: median last 7d vs prior 7d → up / down / flat; hide if either window empty |
| D8 | Board sorts applied in-app to already-fetched filtered list (7 modes); Best Value = `price / fair_value` ascending |
| D9 | Ops analytics via `get_market_analytics(from,to)` RPC (+ quickstart SQL); no Discord admin dashboard in this feature |
| D10 | Migration **086**; extend `verify_required_schema.sql`; no change to tax %, bounds, TTL, or P2P flag semantics |
| D11 | Forward-only snapshots: pre-086 sales log rows keep NULL snapshot columns; discovery ignores incomplete rows for cohort stats |

## Next command

`/speckit.tasks` — break this plan into implementation tasks.
