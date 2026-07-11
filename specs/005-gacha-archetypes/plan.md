# Implementation Plan: Gacha Card Archetypes & Factory Reliability

**Branch**: `005-gacha-archetypes` | **Date**: 2026-07-11 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/005-gacha-archetypes/spec.md`

## Summary

Elevate procedural card creation so packs and intake produce **distinct positional archetypes**, **True OVR that always matches the creation target** (no abandoned while-loop), and **typed factory + pack-config contracts**. Reuse existing `player_cards.role` for archetype display. Persist `role` through intake RPCs (today they omit it, so every card defaults to `Balanced`). Standard pack rarity mix stays 60/30/8/2; no new slash commands or live pack products.

**Technical approach**: (1) Archetype catalog + weighted roll in `player_factory` before stat jitter; (2) deterministic greedy ±1 OVR correction on ranked attrs; (3) `CreatedPlayerCard` Pydantic model from factory; (4) `pack_configs.py` for Standard pack; (5) migration `051` so register / daily pack / youth / scouting paths store `role`; light pack/onboarding embed show of role.

## Technical Context

**Language/Version**: Python 3.11+ (CPython)

**Primary Dependencies**: pydantic ≥2.0, local `player_engine`, `gacha`, `economy` (youth tier only)

**Storage**: Supabase Postgres — reuse `player_cards.role`; add `scouting_pool_players.role`; forward-fix intake RPCs via new migration `051_*` (no new tables)

**Testing**: pytest — archetype diversity, OVR exactness, pack config weights, payload includes `role`

**Target Platform**: Discord bot (Render) + hosted Supabase

**Project Type**: Monorepo — pure packages (`player_engine`, `gacha`) + thin bot payload/embed wiring + SQL RPCs

**Performance Goals**: Card creation O(ΔOVR) greedy adjust (typically &lt;30 attribute bumps); pack of 5 remains negligible vs RPC latency

**Constraints**: AGENTS.md — no `discord` in `packages/`; no XP/coin bypasses; columns only via migrations; SDD reconcile `.specify/specs/v1.0.0/` on implement; `change_log.md` on ship; no new slash commands/hubs; PlayStyle / True OVR formula unchanged

**Scale/Scope**: ~10–14 files; 4 RPC consumers; 1 migration; pack reveal + optional onboarding/player role line

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| I. Monorepo — no `discord` in `packages/` | PASS | Factory/archetypes/pack config in packages; embeds/payload in `apps/discord_bot` |
| II. DB mutations via RPC | PASS | Persist role only by extending existing intake RPCs; no app-level multi-row loops |
| III. Typing / Pydantic at boundaries | PASS | Factory returns `CreatedPlayerCard`; gacha maps to `GachaPlayer` (+ `role`) |
| IV. Slash + defer | PASS | No new commands; `/store` claim path unchanged |
| V. APScheduler | PASS | Regen job keeps calling factory; no new jobs |
| VI. User-friendly errors | PASS | Unknown pack id → typed domain error; RPC errors already mapped |
| VII. YAGNI | PASS | Config readiness for extra packs; do not ship Defender/Gold pack UX |

**Post-Phase 1 re-check**: PASS — contracts cover factory card, pack config, role persistence RPC; no PlayStyle rewrite; architecture layers intact.

## Project Structure

### Documentation (this feature)

```text
specs/005-gacha-archetypes/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── created-player-card.md
│   ├── pack-config.md
│   └── role-persistence-rpc.md
└── tasks.md             # /speckit.tasks (not this command)
```

### Source Code (repository root)

```text
packages/player_engine/player_engine/
├── archetypes.py              # NEW — catalog, weights, roll_archetype(position, rng)
├── player_factory.py          # MODIFY — archetype → stats → deterministic OVR balance → CreatedPlayerCard
├── models.py or created_card.py  # NEW — CreatedPlayerCard pydantic (or extend existing models module)
├── youth_intake.py           # MODIFY — consume model / keep role through overrides
├── regen_pool.py              # MODIFY — role on regen cards
└── __init__.py                # MODIFY — export CreatedPlayerCard, roll helpers as needed

packages/gacha/gacha/
├── pack_configs.py            # NEW — STANDARD_PACK and PackConfig registry
├── models.py                  # MODIFY — GachaPlayer.role
├── generator.py               # MODIFY — use pack config; map CreatedPlayerCard → GachaPlayer
└── __init__.py                # MODIFY — export pack config / generate_pack(pack_id=...)

apps/discord_bot/
├── core/card_payload.py       # MODIFY — include role
├── embeds/gacha_embeds.py     # MODIFY — show role on pack claim
├── embeds/onboarding_embeds.py # MODIFY — show role on marquee/youth if trivial
└── embeds/player embeds / player_cog  # OPTIONAL — already shows role; verify field name

supabase/migrations/
└── 051_card_role_persistence.sql   # NEW — role on intake RPCs + scouting_pool_players.role

supabase/scripts/verify_required_schema.sql  # EXTEND — column/guard for scouting role if required

tests/
├── test_player_archetypes.py       # NEW — diversity + weight shape
├── test_player_factory_ovr.py      # NEW — target OVR exactness, no while-abandon
├── test_pack_configs.py            # NEW — Standard weights; unknown pack fails
└── test_regen_pool.py              # EXTEND — role present

scratch/apply_migration_051.py     # NEW — apply pattern
change_log.md                       # MODIFY on ship
.specify/specs/v1.0.0/spec.md + plan.md  # RECONCILE on implement
```

**Structure Decision**: Keep archetype math + OVR balancing in `player_engine` (single creation pipe). Keep pack product rules in `gacha` (`pack_configs`). Bot only serializes `role` and displays it. Migration is required because current RPCs drop `role` even though the column exists.

## Complexity Tracking

> No constitution violations requiring justification.

## Implementation Notes (for `/speckit.tasks`)

1. **Archetype catalog** — lock names/weights in [research.md](./research.md) R2; store as data in `archetypes.py` (`ArchetypeDef`: name, position, weights, roll_weight). FWD must include Poacher / Speedster / Complete Forward.
2. **Factory pipeline** — `roll_archetype` → provisional stats from archetype weights (same jitter bands as today) → `balance_true_ovr_deterministic` → build `CreatedPlayerCard` with `role=archetype.name`, `overall=base_rating=true_ovr`.
3. **Balancing** — see research R3: bulk estimate optional; then greedy ±1 on top-2 / bottom-2 ranked attrs until `calculate_true_ovr(..., playstyles=[], potential)` equals target or no legal move. Delete the `attempts < 10` while-loop.
4. **Callers** — `gacha.generator`, `youth_intake`, `regen_pool` must not reintroduce dict-only creation that skips role. Prefer `model_dump(by_alias=True)` / helper for RPC JSON.
5. **Migration 051** — jsonb_to_recordset gains `role TEXT`; INSERT lists `role` with `COALESCE(role, 'Balanced')`. Same for `scouting_pool_players` + purchase copy.
6. **Pack API** — `generate_pack(n=5, pack_id="standard")` reads config; default preserves today’s mix/position weights. Do not wire a second store product in v1.
7. **UI** — pack claim embed adds one role line; squad/player already show `role`.
8. **Out of scope** — PlayStyle catalog, True OVR formula changes, historical backfill, new pack SKUs in `/store`.
