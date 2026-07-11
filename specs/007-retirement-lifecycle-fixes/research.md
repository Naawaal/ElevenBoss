# Research: Retirement Lifecycle Fixes

**Feature**: `007-retirement-lifecycle-fixes` | **Date**: 2026-07-11  
**Purpose**: Resolve design unknowns before implementation; freeze decisions that keep aging/retirement atomic and Ponytail-small.

---

## 1. What We Have (Current State)

### 1.1 Aging & retirement

| Piece | Location | Behavior today |
|-------|----------|----------------|
| DOB age | `card_age_from_dob` + `player_engine.age_from_dob` | Source of truth; cached `age` refreshed weekly |
| Decline batch | RPC `process_season_aging` (041) | Mon 00:00 UTC via scheduler; PAC/PHY from 31; PAS/DEF from 33; **no SHO/DRI** |
| Python mirror | `yearly_stat_decline` | Partially out of sync: VETERAN (31–34) never returns PAS/DEF; SQL does at 33–34 |
| Retire | `retire_player_card` | DELETE from `squad_assignments`; set `is_retired` / `retired_at` — **no backfill** |
| Warnings | `retirement_notified_at` at warn age 35 | Unchanged by this feature |

### 1.2 Squad model

| Fact | Implication |
|------|-------------|
| `squad_assignments` = starting XI only (slots 1–11) | “Bench” = owned active cards **not** in assignments |
| `formation_slot_role(formation, slot)` exists in SQL (037) | Auto-promote eligibility = same GK/DEF/MID/FWD as slot role |
| `reserve_fits_formation_slot` in `match_engine` | Python mirror of the same rule |
| Battle already rejects `count != 11` | Hard stop exists; messaging is generic, not retirement-aware |
| `set_formation_and_assignments` | Full replace of XI; natural clear-point for invalid flag |

### 1.3 Regen rarity (inverted)

```text
Current (regen_pool.py):
  if ovr >= 80 and rand < 0.35 → Rare
  elif ovr >= 85 and rand < 0.15 → Epic
  else → Common

For ovr ≥ 85: ~55% Common (product failure for legends)
```

Spawn job: `spawn_regens_from_recent_retirements` after aging; threshold OVR 75; unchanged eligibility.

### 1.4 Latest migration

Repo head: `052_mentor_transfusion.sql` → this feature is **`053_retirement_lifecycle_fixes.sql`**.

---

## 2. Decisions

### R1 — Decline curve (Flaw 1)

**Decision**: Extend the existing per-year loop; do not invent a second aging system.

| Age band (year reached) | Declines |
|-------------------------|----------|
| ≥ 31 | PAC −1, PHY −1 (−2 each if ≥ 35) |
| ≥ 33 | PAS −1, DEF −1, **DRI −1** |
| ≥ 35 | **SHO −1** |

**Rationale**: Spec FR-002–004; ensures every core attr trends down by retirement age.  
**Alternatives**: Decay SHO earlier (rejected — keep finishing sticky until 35 as product asked); percentage-based decay (rejected — YAGNI).

**Also**: Align Python `yearly_stat_decline` with SQL for PAS/DEF at 33–34 (pre-existing mirror drift).

### R2 — Auto-promote eligibility (Flaw 2)

**Decision**: Eligible reserve = same club, `is_retired = FALSE`, not in `squad_assignments`, `position = formation_slot_role(club formation, vacated slot)`. Prefer **highest `overall`, then lowest `id`** for determinism.

**Rationale**: Reuses 037 SQL helper and swap rules; no dual-position matrix (FR-009).  
**Alternatives**: Random pick (worse for tests); require healthy/non-fatigued (spec assumption: temporary status does not block promote).

### R3 — `squad_invalid` vs count-only gate

**Decision**: Add `players.squad_invalid BOOLEAN NOT NULL DEFAULT FALSE`. Set when a starting slot is vacated and no eligible reserve exists. Clear when `set_formation_and_assignments` successfully writes a full XI, or when auto-promote restores 11 starters.

**Rationale**: Spec FR-010–012 require an explicit flag + retirement-aware copy; count≠11 alone cannot distinguish “never set squad” from “retirement hole” for messaging, and flag enables future hub banners.  
**Alternatives**: Message-only without column (rejected — weaker than FR); new table (rejected — FR-015).

### R4 — Battle middleware

**Decision**: Keep hard `assignments == 11` check. If `squad_invalid` **or** count≠11 after retirement context, show retirement repair copy when flag is true; otherwise keep existing incomplete-XI copy. Apply to **bot**, **league kickoff**, and **friendly** start paths that already gate on XI size.

**Rationale**: Belt-and-suspenders; flag may be true with count&lt;11; stale false + hole still blocked by count.  
**Alternatives**: Flag-only (unsafe if flag cleared incorrectly).

### R5 — Regen rarity rewrite (Flaw 3)

**Decision**: Exact FR-014 weights via discrete roll helper:

| Peak OVR | Epic | Rare | Common |
|----------|------|------|--------|
| ≥ 85 | 50% | 50% | 0% |
| 80–84 | 0% | 60% | 40% |
| 75–79 | 0% | 20% | 80% |

Eligibility still ≥ 75 (spawn job / config threshold). Below 75: no regen (unchanged).

**Rationale**: Guarantees legend fantasy; removes Common flood from 85+.  
**Alternatives**: Soft boost of Epic chance only (rejected — still allows Common legends).

### R6 — No new surfaces

**Decision**: No new slash command, hub button, or table. Optional `/squad` embed note if `squad_invalid` is a small copy add in existing hub — allowed as UX clarity, not a new command.

---

## 3. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Python/SQL decline diverge again | Single table in contract; tests assert Python bands; SQL loop comments mirror table |
| Auto-promote picks weak GK | Highest-OVR preference; manager can still swap |
| Multiple Monday retirements leave multiple holes | Loop per card; flag stays true if any starting vacancy remains |
| Bot clubs left invalid | Same rules; auto-sim paths that require XI already skip/fail on count≠11 |
| Migration 052 not applied on some envs | 053 is independent additive; apply order still numeric |

---

## 4. Resolved clarifications

No open NEEDS CLARIFICATION remain from the spec. Defaults locked in R1–R6.

---

## 5. T014 / T014b — Match-path guards (implemented)

| Path | Call site | Guard |
|------|-----------|-------|
| Bot match | `battle_cog` bot start (~XI fetch) | `fetch_xi_state` + `xi_block_message` |
| League human kickoff | `battle_cog` league play handler | same |
| Friendly | `start_friendly_match` **before** thread/locks | both clubs via `fetch_xi_state` / `xi_block_message` |
| League auto-sim | `run_league_match_simulation` after loading human XI | `human_club_xi_ok` → **skip fixture** (fail closed); optional DM if active manager |
| AI clubs | `build_bot_match_squad` | N/A — generated XI, no `squad_invalid` |

Shared helpers: `apps/discord_bot/core/squad_validity.py`.
