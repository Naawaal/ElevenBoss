# Acceptance Record: Youth Academy V2 (Features 051 → 052)

**Date**: 2026-08-04  
**Feature under test**: `051-youth-academy-rarity`  
**Acceptance feature**: `052-youth-academy-v2-acceptance`  
**Repo HEAD (parent commit)**: `1737df6e806874fe4449b8357835e5112e018c99`  
**Working tree**: YA V2 + 052 acceptance artifacts **uncommitted** at record time (implement on `main` local)

## Decision

| Gate | Status |
|------|--------|
| Repo + DB + E2E (Phases 1–3, 6 partial) | **CONDITIONAL PASS** |
| Monday soak (Phase 4) | **PENDING** |
| **Formal ACCEPT / archive 051** | **BLOCKED until ≥1 Monday soak** |

Do **not** start new gameplay features until soak clears and decision flips to **ACCEPT**.

---

## Config / DB snapshot (2026-08-04)

Evidence: `evidence/db-snapshot.txt`

| Key | Value |
|-----|-------|
| 095 objects | present |
| `youth_academy_v2_enabled` | `true` |
| `youth_academy_legendary_enabled` | `true` |
| `youth_intake_count` | `2` |
| `academy_weekly_promote_cap` | `2` |
| `academy_slot_cap` L1–L5 | **3 / 3 / 4 / 4 / 5** |
| Illegal academy POT | **0** |
| Academy seats with ranges | **122 / 122** |
| Over-capacity grandfathered clubs | **21** |
| `verify_required_schema.sql` | **PASS** |
| Forward fixes | **096** fog floor, **097** season aging decay — applied |

RPC body markers matched migration 095 for intake/promote/growth/sign/assess/slot_cap.

---

## Test results

| Suite | Result | Evidence |
|-------|--------|----------|
| Academy unit (+ integrity/youth_intake updates) | **31 passed** | `evidence/academy-unit.txt` + re-run after 096 |
| Isolated E2E club `900000000000000052` | **ALL_E2E_CHECKS_PASSED** | `evidence/e2e-acceptance.txt` |
| Full `pytest` | **651 passed, 5 failed** | 2 YA failures fixed; **3 remaining non-YA** (pre-existing): `test_hub_hot_path_wave3`, `test_league_integrity_pause`, `test_leagues` |
| Ruff (YA touch files) | check clean; format applied | |

### Integrity greps

| Check | Result |
|-------|--------|
| Common-only / gem path in `youth_intake.py` | **Absent** |
| `/academy` slash command | **Absent** |
| Academy embeds default exact POT | **Ranges only** (`POT lo–hi`) |
| `dispatch_academy_assessment` caller | `academy_hub.py` |
| `finalize_due_academy_assessments` callers | hub refresh + growth job |
| `ensure_academy_weekly_row` caller | hub load |
| Direct `coins` UPDATE in 095 | **None** (fees via `apply_club_economy`) |

---

## SC-001…SC-010 evidence (Feature 051)

| SC | Evidence | Status |
|----|----------|--------|
| SC-001 ceilings | E2E rarity loop + unit `test_youth_intake_v2` | PASS |
| SC-002 cutover repair | illegal_academy_pot_count=0; ranges 122/122 | PASS |
| SC-003 full academy block | E2E `capacity_blocked` | PASS |
| SC-004 scout fog / Deep | E2E ladder ends width≥2 after 096; embeds use ranges | PASS |
| SC-005 no double charge/dup | double assess rejected; intake idempotent | PASS (retry harness) |
| SC-006 promote ≤2/week | E2E 3rd promote blocked; first fee 0 still counts | PASS |
| SC-007 Legendary rarity | kill switch + L&lt;5 absent in samples; soak will monitor L5 | PARTIAL (soak) |
| SC-008 `/development` entry | wired `hub_youth_academy` | PASS (code); Discord manual smoke recommended |
| SC-009 over-cap grandfather | E2E + 21 live over-cap clubs | PASS |
| SC-010 facility preview / no reroll | preview helper + upgrade path unchanged seated identity | PASS (preview + assess identity); live Store click optional |

---

## Defects found during 052

| Sev | Finding | Resolution |
|-----|---------|------------|
| P1 | Successive scout tiers could collapse to exact POT (`78-78`) | **096** + Python `narrow_range` fog floor for all tiers |
| P1 | Season ≤1 POT decay not wired to `process_season_aging` | **097** applied |
| P1 | Obsolete Common-only unit tests failing full pytest | Updated `test_youth_intake.py`, `test_rarity_potential_integrity.py` |
| P2 | Full pytest still has 3 unrelated league/marketplace failures | Out of YA scope — track separately |
| P2 | Discord UI manual smoke (Development/Squad/Profile) not bot-driven | Recommend 5-min manager walk after deploy |
| P3 | Ruff format drift on new modules | Formatted |

---

## Rollback (dry-run notes)

1. **Flag**: `UPDATE game_config SET value_json='false' WHERE key='youth_academy_v2_enabled';` — generators in bot still V2-only in Python; treat as “stop new product messaging / ops pause”, not full code rollback.  
2. **Code**: revert deploy to pre-051 commit; keep 095–097 applied (columns/ranges safe).  
3. **Do not** DROP 095 columns on production without a forward migration.  
4. **Legendary kill**: `youth_academy_legendary_enabled=false` without deploy.

Dry-run performed: flag was toggled true after 095; kill-switch path exercised in E2E generation.

---

## Balance baseline (pre-soak)

- Over-capacity clubs: **21** (expect elevated capacity_block rate Monday)  
- All academy seats have visible ranges  
- No illegal POT remaining  

Rebalance **only after** soak rarity mix is filled in `soak-report.md`.

---

## Next actions (blocking ACCEPT)

1. Deploy bot build with YA V2 UI.  
2. Run next **Monday 00:00 UTC** intake; fill `soak-report.md`.  
3. If no P0/P1: set decision **ACCEPT**, mark 051 archived in this folder / move to `specs/archive/`, close 052 checklist.  
4. Only then pick the next gameplay feature.
