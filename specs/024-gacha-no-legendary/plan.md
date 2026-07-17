# Implementation Plan: Gacha Pack Epic Cap (No Legendary Drops)

**Branch**: `024-gacha-no-legendary` | **Date**: 2026-07-17 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/024-gacha-no-legendary/spec.md`

## Summary

Remove **Legendary** from all gacha pack rarity mixes. Standard pack defaults become **Common 60 / Rare 30 / Epic 10** (fold old 2% Legendary into Epic). Seed the same mix in `game_config` for ops tuning. Bot reads config when claiming packs and passes an override into pure `gacha` (packages stay DB-free). Hard-sanitize so Legendary can never be rolled from packs even if bad config is inserted. Keep owned Legendaries and `generate_support_legendary` intact. Prove with ≥10k simulated rolls.

## Technical Context

**Language/Version**: Python 3.11+ / Postgres 15+

**Primary Dependencies**: `gacha` package (`pack_configs`, `generator`), Discord `/store` claim, `game_config` via existing bot helpers

**Storage**: `game_config` keys for standard pack rarities/weights (migration `068`); no new tables; no changes to `player_cards` rarity CHECK

**Testing**: pytest — update `tests/test_pack_configs.py`; add large-N zero-Legendary simulation; sanitize/invalid-config cases

**Target Platform**: Discord bot + hosted Supabase

**Project Type**: Monorepo balance/UX (pack odds only)

**Performance Goals**: Negligible — config read once per pack claim; generation unchanged

**Constraints**: AGENTS.md — no Discord/DB in `packages/`; packages accept overrides as data; never mutate owned Legendaries; thank-you Legendary path untouched

**Scale/Scope**: ~8–10 files; 1 small migration; Store copy + SDD/changelog

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| I. Monorepo | PASS | Odds resolve in `packages/gacha`; bot loads config + calls generator |
| II. DB via RPC | PASS | Config seed only; pack claim still uses existing `claim_daily_pack` |
| III. Typing | PASS | Typed PackConfig / override helpers |
| IV. Slash + defer | PASS | No new slash; Store claim already defers |
| V. APScheduler | PASS | Untouched |
| VI. Friendly errors | PASS | Invalid config → silent safe defaults (no user-facing crash) |
| VII. YAGNI | PASS | One standard pack; fold weight into Epic; no pity system |

**Post-Phase 1 re-check**: PASS — bot injects config into pure `resolve_pack_config`; package never opens Supabase. Sanitize strips Legendary even if ops mis-seeds config.

## Project Structure

### Documentation (this feature)

```text
specs/024-gacha-no-legendary/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── pack-epic-cap.md
│   ├── game-config-pack-odds.md
│   └── store-pack-copy.md
└── tasks.md             # /speckit.tasks — NOT created here
```

### Source Code (repository root)

```text
supabase/migrations/068_pack_epic_cap_odds.sql
scratch/apply_migration_068.py
supabase/scripts/verify_required_schema.sql          # optional config-key note / guard if used elsewhere

packages/gacha/gacha/pack_configs.py                 # MODIFY — defaults 60/30/10; resolve + sanitize
packages/gacha/gacha/generator.py                    # MODIFY — use resolved config; accept optional override
packages/gacha/gacha/__init__.py                     # EXPORT helpers if new

apps/discord_bot/cogs/store_cog.py                   # MODIFY — load config; pack odds copy
apps/discord_bot/core/economy_rpc.py                 # optional helper get_pack_rarity_override
# OR small apps/discord_bot/core/pack_config_rpc.py

tests/test_pack_configs.py                           # UPDATE — new weights; 10k zero Legendary
change_log.md
.specify/specs/v1.0.0/spec.md                        # pack odds AC
```

**Structure Decision**: Keep `PackConfig` as source of truth in packages. Bot optionally overlays `game_config` JSON. Generation always runs through a sanitize step that drops Legendary.

## Complexity Tracking

> No constitution violations.

## Implementation Notes (for `/speckit.tasks`)

1. Change `PACKS["standard"]` to rarities `("Common","Rare","Epic")`, weights `(60, 30, 10)`.
2. Add `sanitize_pack_config(cfg) -> PackConfig` — remove Legendary entries; if empty/invalid → Epic-capped defaults.
3. Add `resolve_pack_config(pack_id, *, rarities=None, weights=None) -> PackConfig`.
4. `generate_pack` uses resolved/sanitized config; optional kwargs for bot override.
5. Migration `068`: seed `pack_standard_rarities` / `pack_standard_rarity_weights` (JSON arrays).
6. Store claim: read config → pass override → `generate_pack`; update embed/description odds line.
7. Grep: no pack path still lists Legendary 2%; leave `generate_support_legendary` alone.
8. Tests: assert config defaults; 10k rolls → 0 Legendary; Epic ~10% ±2pp; invalid override still Epic-capped.
9. Rollback: restore 60/30/8/2 in package + config; Store copy; no player data rollback needed.
