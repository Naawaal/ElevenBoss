# Research: Game Integrity Remainder (US-42.6–42.10)

**Date**: 2026-07-22 | **Feature**: `035-integrity-remainder`

## R1 — Delivery shape

**Decision**: Keep one Speckit folder; ship **W7 ∥ W6 → W8 → W9 → W10**. Registry and catalogs are markdown contracts + pytest greps.

**Rationale**: User consolidate request; epic obligations preserved as workstreams.

## R2 — Marketplace (W6) mostly OK

**Decision**: Do **not** rewrite `purchase_transfer_listing`. Lock with tests: race, own-buy, list via `assert_card_action_allowed`. Soft: dedicated tax ledger sink row; per-listing expiry run key — defer unless cheap.

**Rationale**: Audit — FOR UPDATE + status + own-buy + economy keys already present (`062`/`075`).

**Alternatives considered**: Mega market migration — rejected (YAGNI).

## R3 — Economy registry (W7) is the Critical doc gap

**Decision**: Author living `contracts/economy-source-sink-registry.md` covering match, store, wages, transfer buy/sale/tax, prizes, drills/fusion, agent/scout, packs, refills, etc. Each row: id, direction, pipeline, key pattern, owner. Grep: zero `players.coins` UPDATEs in `apps/`. Friendly non-faucet assert.

**Rationale**: Spec FR-E01; no registry exists today.

## R4 — Gems / tokens

**Decision**: Registry marks `players.tokens` as **display / non-piped** until product defines gem mutations; FR-E06 = document N/A or “no mutations” rather than invent a gem pipe.

**Rationale**: `apply_club_economy` is coins+energy only; inventing gems mid-remainder is scope creep.

## R5 — Tax sink

**Decision**: Soft — registry entry `transfer_tax_burn` documents implicit burn (buyer debit − seller credit). Optional later: explicit `apply_club_economy` to system sink or ledger reason-only row in **078**.

**Rationale**: Tax already removed from circulation via netting; observability Soft.

## R6 — Job catalog (W8)

**Decision**: Catalog every job registered in `apps/discord_bot/main.py` (aging, youth, regen, league reset, auto-sim, reminders, daily recovery, league state/lifecycle, payroll, academy, transfer expiry). Document run-key / catch-up / “idempotent how” pointing at existing RPCs/`_run_once` where present. Do not rebuild scheduler platform.

**Rationale**: Spec FR-J01; ephemeral APScheduler stays; keys in durable RPCs/ops tables.

## R7 — RPC checklist (W9)

**Decision**: Markdown checklist (migration, guards, RLS, no Python multi-step money, DROP old overloads, caller grep). Apply to any migration this feature adds; sample-audit existing transfer/economy RPCs as “already compliant” notes.

**Rationale**: INV-16; process artifact > new tooling.

## R8 — Security / edges (W10)

**Decision**: Soft threat model + edge catalog for remainder domains; stale custom_id fail-closed already common — grep/assert marketplace/store. No hard ban system.

**Rationale**: Epic §4.12 / FR-S*.

## R9 — Migration policy

**Decision**: Default **no 078**. Add only for Critical SQL (e.g. mandatory tax sink row). Next number after `077`.

## R10 — Soft deferred

| Item | Notes |
|------|-------|
| Explicit tax sink ledger | Soft observability |
| Per-listing expiry job key | Batch UPDATE already idempotent |
| Gem mutation pipe | Product undecided |
| Full dashboards | Signals as SQL/log queries enough |
| Split 035 back into 5 folders | Optional later |
