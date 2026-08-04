# Implementation Plan: Youth Academy V2 Acceptance and Soak

**Branch**: `052-youth-academy-v2-acceptance` | **Date**: 2026-08-04 | **Spec**: [spec.md](./spec.md)

**US citation**: Verification only — no mutating gameplay. Cite **US-42.2 / US-42.7 / US-42.9** when filing defects against 051.

## Summary

Prove Feature 051 on the real target: repo gates → live DB/RPC parity → manager E2E → Monday soak → balance baseline → remediate P0/P1 → formal acceptance + archive 051.

## Technical Context

**Language/Version**: Python 3.11+ / Postgres 15+  
**Primary Dependencies**: pytest, ruff, psycopg/`DATABASE_URL`, existing academy RPCs  
**Storage**: Read/verify target Supabase; fixture mutations only via existing RPCs  
**Testing**: Academy unit suite + full `pytest` + SQL verify + soak report  
**Project Type**: Acceptance gate (docs + scripts under `specs/052-*` and `scratch/`)  
**Constraints**: No new gameplay; no `/academy`; no parallel coin/XP pipes; ponytail — reuse existing scratch/apply patterns  

## Constitution Check

| Gate | Status |
|------|--------|
| I–VII | PASS — verification only; defects fixed in 051 surfaces |

## Artifacts

```text
specs/052-youth-academy-v2-acceptance/
├── spec.md
├── plan.md                 # this file
├── tasks.md
├── acceptance-record.md    # Phase 7 SoT
├── soak-report.md          # Monday intake template + fills
├── evidence/               # test logs, SQL snapshots, SC mapping
└── checklists/acceptance.md
```

## Phases (execute in order)

1. Repository verification  
2. Target database verification  
3. End-to-end acceptance scenarios  
4. Monday intake soak (≥1 cycle)  
5. Balance baseline review (no premature rebalance)  
6. Defect remediation (P0/P1 block ACCEPT)  
7. Formal closure + archive 051  
