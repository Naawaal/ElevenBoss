# Research: Division-Tier Fatigue & Injury Rebalance

**Feature**: `016-tier-fatigue-rebalance` | **Date**: 2026-07-13  
**Purpose**: Resolve technical unknowns for plan/contracts; freeze decisions before tasks.

---

## 1. Current state (what already ships)

| Piece | Location | Behavior today |
|-------|----------|----------------|
| Match drain | `fatigue.match_fatigue_drain` + `injury_rpc.build_starter_drains` | Base **18**, PHY×**0.15**, tactics **+8/−4**, optional **+5** if opponent rating ≥ team+8 |
| Daily passive | `process_daily_recovery` (054/056) | **25 + TG×5**; hospital fatigue +45 |
| Injury chance | `injury_math.injury_chance` | Base **0.4%** + fat×0.0004 + age/PHY mods; soft-cap fatigue &lt;75; ≤1 injury/club |
| Hospital days | `BASE_RECOVERY_DAYS` 1/4/7 + `/(1+0.2H)` | Admit + post-match injury RPCs (056) |
| Fair backfill | `057` `backfill_injury_eta_fairness` | Never lengthen; early discharge |
| Division | `players.division` | Written by Monday `weekly_league_reset_job` (promo/relegation) |
| Club entity | `players` row | **No `clubs` table** |
| Bot fatigue persist | match/league rewards | **Human clubs only**; AI skips `apply_match_fatigue` |
| Cup matches | — | **None in production** |

---

## 2. Decisions

### D1 — Persist `players.intensity_tier` (not a clubs table)

- **Decision**: Add `players.intensity_tier SMALLINT NOT NULL DEFAULT 1 CHECK (1..3)`. Backfill from current `division` in migration `061`. Update in `weekly_league_reset_job` whenever division is written after promo/relegation (and for non-movers, refresh from their settled division so the column never drifts).
- **Rationale**: Spec FR-002 wants Monday-only effective intensity. `players.division` is already Monday-settled today, but a dedicated column makes UI/RPC reads cheap, survives accidental mid-week division writes later, and matches the proposal’s “cached multiplier” intent without inventing a `clubs` table.
- **Alternatives considered**:
  - Derive tier from `division` at every call — fewer columns, but FR-002 is implicit and easy to break if something writes `division` mid-week.
  - `clubs.current_tier_multiplier` — rejected; clubs table does not exist.

### D2 — Division → tier map (locked Q1)

| Intensity | Divisions | Drain | Passive base | Injury base | Moderate hospital base |
|-----------|-----------|-------|------------|-------------|------------------------|
| 1 | Grassroots, Amateur | 8 | 35 | 0.25% | 3 |
| 2 | Semi-Pro, Professional | 12 | 25 | 0.40% | 5 |
| 3 | Elite, Legendary | 16 | 15 | 0.60% | 8 |

Unknown/null division → **Tier 1**.

### D3 — Drain formula replaces global base + rating-gap intensity

- **Decision**:  
  `Drain = max(0, round_half_up((tier_base − PHY×0.10) + tactic_mod))`  
  tactic_mod: Attack **+4**, Defend **−2**, Neutral **0**.  
  Remove `intensity: bool` (+5) from `match_fatigue_drain` and stop computing rating-gap intensity in `match_rewards.py`.
- **Rationale**: Spec assumptions; tier bases absorb “harder match” feel; rating-gap double-dips with Tier 3.
- **Alternatives**: Keep +5 for “upset” matches — rejected (spec absorbed/removed).

### D4 — Daily recovery becomes tier + TG×2

- **Decision**: Non-hospital `Recovery = tier_base + (TG_level × 2)` with bases 35/25/15. Hospital daily fatigue bump **unchanged** (+45). Bench rest **unchanged** (+25). Recovery Session **unchanged** (+40 / energy 5).
- **Rationale**: Spec FR-004; YAGNI on other levers.
- **SQL**: `process_daily_recovery` must read `players.intensity_tier` (or map from division) — prefer column.

### D5 — Injury chance + hospital severity model

- **Decision**:  
  - `injury_chance = tier_base + (100−fatigue)×0.0003 + existing_age_mod + existing_phy_mod`  
  - Keep soft-caps A+C (≤1 injury; fatigue &lt;75 eligible).  
  - Hospital days: `ceil((moderate_base[tier] × sev_mult) / (1 + 0.2×H))` with sev Minor/Moderate/Major = 0.33 / 1.0 / 2.5; minimum 1 day while still injured.  
  - Untreated overflow uses same untreated total (H=0).
- **Rationale**: Spec FR-005/006; replaces flat 1/4/7 bases with tier-aware moderate anchors.
- **Note**: Tier 3 Major untreated ≈ `ceil(8×2.5)=20` days — intentional top-end demand; Hospital L5 halves Moderate to 4 days (spec SC-003).

### D6 — Backfill: new RPC `backfill_tier_fatigue_rebalance`

- **Decision**: New idempotent SECURITY DEFINER RPC (not a silent re-run of 057 alone). For each open hospital patient: recompute candidate ETA from admission + new total using **current** `intensity_tier` + Hospital level + injury severity; `LEAST(old, candidate)`; early-discharge if `now >= final` (mirror 057 clear path including fatigue grant on clear). Overflow untreated: fair remaining via new untreated bases. Then `UPDATE player_cards SET fatigue = GREATEST(fatigue, 50) WHERE injury_tier IS NULL AND NOT in_hospital` (and not retired if that flag exists).
- **Rationale**: Spec US6 / FR-010–011; 057 math assumed 1/4/7 — must not leave patients on old clocks after tier model ships.
- **Alternatives**: Forward-only only — rejected by spec.

### D7 — AI parity without persisting bot card fatigue

- **Decision**: For a human vs bot match, compute drain and injury **probabilities** using the **human** club’s `intensity_tier` for both sides inside the simulator / post-match injury selection. Persist fatigue/injuries only for the human (existing). Do not create ephemeral bot `player_cards` rows.
- **Rationale**: Spec FR-012 “shared intensity parameters”; bot clubs have no durable fitness inventory today; inventing bot persistence is out of scope.
- **Alternatives**: Persist AI fatigue on `is_ai` players — large new surface; rejected (YAGNI).

### D8 — Cup matches

- **Decision**: No cup implementation in this feature. Contract note: when a cup path is later added, it MUST pass the human’s `intensity_tier` into the same fitness helpers (no cup downgrade). Mark FR-012 cup clause **forward-compatible / N/A until cup exists**.
- **Rationale**: No production cup code (research). Building a cup just to satisfy parity is scope creep.

### D9 — Soft-lock fillers

- **Decision**: Explicit non-goal (locked Q2). Monitor post-launch; do not couple to 015 academy.
- **Rationale**: YAGNI; drain reduction makes soft-locks rarer.

### D10 — Config mirrors

- **Decision**: Upsert `game_config` keys for ops visibility (e.g. JSON map of tier bases) **and** hardcode the same numbers in SQL RPC bodies + Python defaults (same pattern as 056 drain mirror). Bot remains source of starter drain integers; SQL remains source of daily recovery amounts.
- **Rationale**: Consistency with economy/fatigue ops culture; avoid bot reading config mid-match unless already patterned.

### D11 — Math home

- **Decision**: Keep formulas in `packages/player_engine` (`fatigue.py`, `injury_math.py`, small `intensity.py` or helpers in `fatigue.py`). **Do not** create `packages/match_engine/fatigue.py` (proposal path was wrong relative to repo).
- **Rationale**: AGENTS.md + existing call sites already import `player_engine`.

---

## 3. Migration number

- Next migration after `060_youth_academy_workflow.sql` → **`061_tier_fatigue_rebalance.sql`**.
- Extend `verify_required_schema.sql` for column `players.intensity_tier` and function `backfill_tier_fatigue_rebalance`.

---

## 4. Risks

| Risk | Mitigation |
|------|------------|
| Tier 3 Major clocks feel as bad as pre-011 | Hospital copy explains intensity; Hospital upgrades remain high value; monitor soft-locks |
| Double-counting if weekly job forgets intensity_tier | Migration backfill + job always SET intensity_tier from final division |
| Tests still assert drain base 18 / passive 25+TG×5 | Update/extend unit tests in same PR |
| Mid-match injury rolls ignore tier | Pass `intensity_tier` into `injury_chance` / `select_post_match_injury` |

---

## 5. Resolved clarifications

All spec NEEDS CLARIFICATION were resolved before specify (Q1 mapping, Q2 defer soft-lock). No remaining NEEDS CLARIFICATION for plan.
