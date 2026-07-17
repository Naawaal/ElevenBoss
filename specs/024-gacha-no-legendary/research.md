# Research: Gacha Pack Epic Cap

**Feature**: `024-gacha-no-legendary`  
**Date**: 2026-07-17

## R1 — Where odds live today

**Decision**: Treat `packages/gacha/gacha/pack_configs.py` `PACKS["standard"]` as the code default; overlay from `game_config` at Store claim time.

**Rationale**: Audit shows weights are hardcoded `(60, 30, 8, 2)` with rarities including Legendary. No pity timer. Store copy does not currently list the 2% line, but SDD does. Spec FR-004 requires config tunability without putting DB clients in `packages/`.

**Alternatives considered**:
- Only change package defaults (no game_config) — rejected by FR-004.
- Move all pack generation into SQL RPC — rejected (YAGNI; factory stays in Python).

## R2 — Weight redistribution

**Decision**: Fold Legendary’s weight **2** into Epic → **60 / 30 / 10**.

**Rationale**: Spec Assumptions; keeps integer weights summing to 100; makes Epic the clear ceiling with slightly higher presence.

**Alternatives considered**:
- Proportional rescale of 60/30/8 → ~61.2/30.6/8.2 — messier for config and tests.
- Spread 2 points across Common/Rare/Epic — unnecessary complexity.

## R3 — Config shape

**Decision**: Two `game_config` JSON keys:

| Key | Example value |
|-----|----------------|
| `pack_standard_rarities` | `["Common","Rare","Epic"]` |
| `pack_standard_rarity_weights` | `[60,30,10]` |

Bot reads via existing `get_game_config` RPC; builds override; passes into `generate_pack` / `resolve_pack_config`.

**Rationale**: Matches other JSON tunables; parallel arrays mirror `PackConfig` fields.

**Alternatives considered**: Single JSON object `{Common:60,...}` — also fine; parallel arrays match existing dataclass and are easier to validate length equality.

## R4 — Hard ban vs soft weight=0

**Decision**: **Sanitize**: after merge, drop any `"Legendary"` entry from rarities/weights. If nothing left or lengths mismatch / non-positive sum → fall back to package Epic-capped defaults. Generation must never call `random.choices` with Legendary in the list.

**Rationale**: Spec requires no edge case can still roll Legendary (including bad ops config).

## R5 — Thank-you Legendary path

**Decision**: Do not touch `generate_support_legendary` or `support_legendary_rewards`. Grep confirms it does not use `PACKS` rarity table.

**Rationale**: FR-007 / SC-005.

## R6 — Starter / youth / regen

**Decision**: Starter squad already avoids Legendary (Rare/Epic marquee + Common youth). Regen rarity helpers are separate — out of scope unless they import pack Legendary weights (they do not today).

**Rationale**: Spec Out of Scope + Edge Cases.

## R7 — UI

**Decision**: Update `/store` Daily Gacha Pack field to state max rarity Epic and odds **60% / 30% / 10%** (or “Common / Rare / Epic”). Keep Legendary emoji maps on squad/marketplace for **owned** cards.

**Rationale**: FR-005 vs FR-006 display distinction.

## Resolved clarifications

No open NEEDS CLARIFICATION items. Spec Assumptions adopted.
