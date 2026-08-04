# Feature Specification: Youth Academy V2 Final Acceptance and Production Soak

**Feature Branch**: `052-youth-academy-v2-acceptance`  
**Created**: 2026-08-04  
**Status**: In progress  
**Type**: Acceptance / verification (no new gameplay)  
**Depends on**: Feature 051 ([`051-youth-academy-rarity`](../051-youth-academy-rarity/spec.md)) shipped (migration 095 + bot wiring)

## Problem Statement

Feature 051 tasks are marked complete, but checklist completion ≠ independently verified production acceptance. Before any further academy expansion or unrelated gameplay, ElevenBoss must prove V2 works on the **real target environment**: repo gates, live schema/RPCs, manager scenarios, and at least one Monday intake soak.

## Scope

**In scope**: verification suites, live DB/RPC parity, E2E acceptance scenarios, Monday soak evidence, balance baseline capture, P0/P1 defect remediation, formal acceptance record, archive of 051.

**Out of scope**: new academy mechanics, market features, rebalance of rarity weights without soak evidence, new slash commands.

## User Scenarios (acceptance personas)

### US-A1 — Verifier confirms repo + DB integrity (P0)

**Independent Test**: Clean-checkout pytest + ruff; live `verify_required_schema.sql`; RPC defs match migration 095; config snapshot matches intended V2 values.

### US-A2 — Manager walks the academy loop (P0)

**Independent Test**: Intake / rarity / scout / promote / facilities / aging scenarios from Feature 051 SC-001…SC-010 produce concrete pass/fail evidence on target DB + bot.

### US-A3 — Ops observes Monday soak (P0)

**Independent Test**: ≥1 Monday V2 intake completes with telemetry; no P0/P1; Legendary count triggers kill-switch review if anomalously high.

### US-A4 — Product formally closes 051 (P1)

**Independent Test**: Acceptance record filed; 051 archived; SDD canonical specs synchronized; Feature 052 closed.

## Success Criteria

- **SC-A01**: Academy-specific tests + full project pytest/ruff pass (or documented waivers).
- **SC-A02**: Target DB has 095 applied; flag/config snapshot matches acceptance checklist.
- **SC-A03**: Live RPC definitions match repo migration 095 for the YA V2 surface.
- **SC-A04**: SC-001…SC-010 from 051 each have concrete evidence in the acceptance record.
- **SC-A05**: ≥1 Monday V2 intake soak without P0/P1.
- **SC-A06**: Rollback procedure dry-run documented.
- **SC-A07**: 051 archived only after acceptance decision = **ACCEPT**.

## Non-goals

Do not start Feature 053+ gameplay until SC-A07.
