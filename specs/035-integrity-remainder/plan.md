# Implementation Plan: Game Integrity Remainder (US-42.6–42.10)

**Branch**: `035-integrity-remainder` | **Date**: 2026-07-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/035-integrity-remainder/spec.md`

**Parent**: `specs/029-game-integrity` (US-42) | **Depends on**: Locked `030`–`034`, `017`, US-25

## Summary

Close remaining integrity children in **one Speckit package** via workstreams **W6–W10**: marketplace race/expiry hardening, **living economy faucet/sink registry** (P0), job catalog + run keys, RPC/schema checklist, threat model + edge catalog. Prefer **docs + grep/pytest guards + Soft gap fixes** over calendar/economy redesigns. No new hubs; no second pipes.

**Technical approach**: (1) W0 freeze audits per domain in `contracts/`. (2) **W7 first (or parallel W6)**: author `economy-source-sink-registry.md` from code grep; lock with `tests/test_economy_registry_guards.py` (no direct coins UPDATE in apps; friendly non-faucet). (3) **W6**: confirm purchase RPC atomicity already OK; add/strengthen race + own-buy + list-busy tests; Soft: tax burn visibility / expiry job key. (4) **W8**: `job-catalog.md` from `main.py` scheduler list + catch-up/idempotency notes. (5) **W9**: `rpc-guarantee-checklist.md` template; enforce on any new migration this feature adds. (6) **W10**: threat model + edge catalog filling epic §8 for remainder domains; stale-interaction greps. (7) Optional migration **078+** only for Critical holes (e.g. explicit tax sink row) — default **no schema** until registry proves a Critical gap.

## Technical Context

**Language/Version**: Python 3.11+ / Postgres 15+ (Supabase)

**Primary Dependencies**: `purchase_transfer_listing` / transfer RPCs (`062`/`075`), `apply_club_economy`, store/payroll/match/prize RPCs, APScheduler jobs in `main.py`, US-42.2 card asserts, US-42.5 league ops keys

**Storage**: Existing tables; next migration number **078** if/when Critical SQL needed

**Testing**: Pytest source/SQL greps; extend `tests/test_transfer_market_race.py` if present; registry completeness tests

**Target Platform**: Discord bot (Render) + Supabase

**Project Type**: Monorepo integrity remainder (docs-heavy + targeted patches)

**Performance Goals**: Unchanged hot paths; registry/catalog are review artifacts

**Constraints**: Constitution + US-42; YAGNI; do not reopen Locked 42.1–42.5

**Scale/Scope**: Multi-wave; Lock when W6–W10 Done or explicitly deferred with note

## Constitution Check

| Gate | Status | Notes |
|------|--------|-------|
| I. Monorepo | PASS | Pure packages stay pure; Discord in apps |
| II. DB via RPC | PASS | Market/economy already RPC-first; checklist reinforces |
| III. Typing | PASS | Helpers typed |
| IV. Slash + defer | PASS | No new commands |
| V. APScheduler | PASS | Catalog documents catch-up |
| VI. Friendly errors | PASS | Stale reject copy in W10 |
| VII. YAGNI | PASS | Registry/docs before new pipes |

**Post-Phase 1 re-check**: PASS — contracts define W6–W10 deliverables; migration optional.

## Project Structure

### Documentation (this feature)

```text
specs/035-integrity-remainder/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── remainder-audit.md
│   ├── economy-source-sink-registry.md    # W7 living registry (filled in implement)
│   ├── marketplace-integrity.md
│   ├── job-catalog.md                    # W8 (filled in implement)
│   ├── rpc-guarantee-checklist.md        # W9
│   ├── threat-model.md                   # W10
│   └── edge-catalog-remainder.md         # W10
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root) — expected touch list

```text
# W6 (only if gaps)
apps/discord_bot/views/marketplace_transfer.py
apps/discord_bot/tasks/transfer_listing_expiry_job.py
supabase/migrations/078_*   # optional tax sink / expiry key
tests/test_transfer_market_*.py
tests/test_marketplace_integrity_guards.py

# W7
packages/economy/...        # optional export of registry constants — prefer markdown first
tests/test_economy_registry_guards.py
apps/discord_bot/core/economy_rpc.py  # only if pipe gap

# W8
apps/discord_bot/main.py     # cite only unless job keys missing
apps/discord_bot/tasks/*.py
tests/test_job_catalog_guards.py

# W9–W10
# mostly contracts + review process; verify_required_schema if 078+
change_log.md               # if managers see market/economy copy changes
```

**Structure Decision**: Living registry + catalogs as **contracts markdown** (single source reviewers open) beats inventing a DB registry table in v1. Code greps enforce pipes.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Five children in one folder | User-requested consolidate | Separate folders = more Speckit overhead now |

## Implementation Waves

| Wave | Scope | Exit |
|------|-------|------|
| **W0** | Freeze `remainder-audit.md` Critical/Soft/OK | Agreed |
| **W7** MVP-B | Economy registry filled + coin-pipe greps | SC-002 |
| **W6** MVP-A | Market race/own-buy/busy-list tests; Soft tax/expiry | SC-001 |
| **W8** | Job catalog for all `main.py` jobs | SC-003 |
| **W9** | RPC checklist; apply to any 078+ | SC-004 |
| **W10** | Threat model + edge catalog + stale UX | SC-005 |
| **Lock** | Changelog if needed; spec Locked; epic pointer | SC-006 |

## Key Artifacts

| Artifact | Purpose |
|----------|---------|
| [research.md](./research.md) | Audit decisions |
| [data-model.md](./data-model.md) | Listing / registry / job / edge entities |
| [contracts/](./contracts/) | Audits, registry, catalogs, checklists |
| [quickstart.md](./quickstart.md) | Validate W0–W10 |
