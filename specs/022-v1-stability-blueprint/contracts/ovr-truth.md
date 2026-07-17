# Contract: OVR Truth

**Feature**: `022-v1-stability-blueprint`  
**Maps to**: Spec H3, User Story 4, SC-004

## New cards

| Rule | Source |
|------|--------|
| After factory balance, displayed `overall` equals True OVR for position + stats + playstyles + potential | `packages/player_engine` factory / `calculate_true_ovr` |
| Pack / intake persistence writes that same overall | Existing RPCs with role persistence |

**Test**: pytest over seeded factory creates (extend existing pack/factory tests if present).

## Progression mutations

Allocate skill points, evolution **stat** claims, and mentor paths MUST leave stored overall consistent with True OVR / POT clamps — no displayed overall past potential rules.

Prefer refreshing overall through existing RPC paths that already recompute; do not invent a parallel True OVR write in cogs.

## Legacy inflation (H3 disposition)

1. Dry-run `scripts/fix_inflated_player_stats.py` (or equivalent) → record **count**.
2. Choose exactly one:
   - **Apply** fair rebalance under approved script rules → record applied count in registry Notes
   - **Defer** with same count documented as residual backlog (status Closed-deferred note, not silent Open)
3. Do not ship Wave 2 exit without that decision.

## Non-goals

- Changing the True OVR formula itself
- Recomputing overall on every Discord embed render
- Auto-selling or wiping inflated cards
