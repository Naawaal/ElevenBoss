# Feature Specification: Hub Hot-Path Wave 3 (Marketplace / Leaderboard)

**Feature Branch**: `040-hub-hot-path-wave3`

**Created**: 2026-07-22

**Status**: Implemented (2026-07-22)

**Parent**: [`038`](../038-db-scalability-performance/spec.md) (US-43), [`039`](../039-hub-hot-path-wave2/spec.md) (US-44)

**US citation**: **US-45** (extends US-43/44). Marketplace mutations remain US-42.7 / existing RPCs (`process_agent_sale`, transfer buy).

**Input**: Continue remaining hub surfaces called out as out-of-scope in US-44: marketplace hub + sell menu, `/leaderboard`. Same patterns — gather, reuse `division_cache`, `hub_timer`, defer. No Redis, no new commands.

---

## 0. Scope

| ID | Surface | Entry | Approach |
|----|---------|-------|----------|
| HP-7 | Marketplace hub | `show_marketplace_hub` | Gather player ∥ transfer flag; then listing count; `hub_timer` |
| HP-8 | Sell-to-agent menu | `show_sell_menu` (+ `_eligible_listing_cards` if same serial pattern) | Gather roster ∥ XI ∥ evo ∥ training ∥ listed ids |
| HP-9 | Leaderboard | `leaderboard` / embeds | Defer; gather embed ∥ unclaimed tier; `load_global_divisions` on Global tab; season fixtures ∥ participant check ∥ standings |

### Out of scope

- Caching live listings / coins / transfer search results as SoT
- New slash commands or marketplace RPCs
- Redis / multi-instance shared `lb:*` (catalog allows later)

### Non-negotiables

- Agent sale / transfer buy stay on existing atomic RPCs
- Defer before DB work on `/leaderboard`
- No invented balances on hub embeds

---

## User Stories

### US1 — Marketplace hub/sell feel snappier (P1)

**Acceptance**: Hub and Sell menus show same eligible players and balances; fewer serial RTs (source contract).

### US2 — Leaderboard opens promptly (P1)

**Acceptance**: Division/Global/Season tabs render correctly; Global uses cached divisions; claim button state still correct.

---

## Requirements

- **FR-001**: `hub_timer("marketplace")`, `hub_timer("leaderboard")`
- **FR-002**: Parallel independent reads on HP-7…HP-9
- **FR-003**: Reuse `division_cache.load_global_divisions` in Global tab
- **FR-004**: `/leaderboard` defers immediately
- **FR-005**: No new commands/tables; update hot-path catalog + change_log

## Success

- SC-001: Contract tests green; catalog After notes for HP-7…HP-9
- SC-002: Persona — double-open market, claim weekly tier still works

---

## Clarifications

- Q: Cache transfer search pages? → **No** this wave (live inventory).
- Q: New `lb:` process cache for division standings? → **No** unless measured; gather first.
