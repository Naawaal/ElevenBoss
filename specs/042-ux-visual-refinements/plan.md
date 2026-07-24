# Implementation Plan: Store / Swap / Hospital UX Refinements

**Branch**: `042-ux-visual-refinements` | **Date**: 2026-07-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/042-ux-visual-refinements/spec.md`

## Summary

Three Discord hub UX refinements with **no schema/RPC changes**:

1. **Store energy refill guard (P1)** — Disable Buy Energy Refill when action energy is near/at max (95% of max **or** within 5 of max), with disabled label + embed copy (`Energy already full` / `Near maximum`).
2. **Swap visual comparison (P2)** — Augment `SquadSwapView` with a side-by-side PIL comparison image (names, position, OVR, key attrs) that updates on select; keep existing dual-select + Confirm gating.
3. **Hospital visual panel (P3)** — Attach a dynamically overlaid render of `assets/admited.png` (patient clipboard asset, ~5–6 lined rows) showing admitted names; regenerate on each `show_hospital_panel`; text waiting list + overflow + asset-missing fallback unchanged in behavior.

**Technical approach**: Pure near-full predicate in `packages/energy/`; image render helpers beside existing `pitch_generator.py` (Pillow + `_RENDER_SEM` + `asyncio.to_thread`); wire Store / Swap / Hospital call sites only. Reuse roster-card visual language for swap. Hospital overlays text onto the prepared clipboard asset rather than inventing bed icons.

## Technical Context

**Language/Version**: Python 3.11+ / CPython

**Primary Dependencies**: discord.py ≥2.7, Pillow (already used by `pitch_generator`), existing Supabase async reads (no new RPCs)

**Storage**: N/A (no migrations). Reads existing `players.action_energy` / `max_energy` via `sync_action_energy`; hospital via existing `hospital_patients` + waiting card queries

**Testing**: pytest — pure near-full predicate; swap selection readiness unchanged; optional render smoke (asset present → non-empty PNG bytes; missing asset → None/fallback path)

**Target Platform**: Discord bot (ephemeral hub messages) + hosted Supabase

**Project Type**: Monorepo Discord UX polish (apps/discord_bot + thin packages/energy helper)

**Performance Goals**: Image renders off-event-loop via existing semaphore (cap concurrent PIL work); hospital/swap opens stay within Discord interaction defer window (already deferred at entry points)

**Constraints**: No `discord` imports under `packages/`; no new slash commands/hub buttons beyond label/disable changes; no economy/swap/hospital math changes; Discord buttons lack native tooltips → label + embed field; hospital asset filename typo `admited.png` kept as-is; max visual hospital rows ≈ 5–6 (match asset + `hospital_bed_capacity` at L5 = 6)

**Scale/Scope**: ~8–12 files touched; 0 migrations; 3 user-facing surfaces (`/store`, `/squad` swap, `/profile`→Hospital)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| I. Monorepo | PASS | Near-full math in `packages/energy`; PIL + Discord.File only in `apps/discord_bot` |
| II. DB via RPC | PASS | No new mutations; refill/swap/admit/discharge RPCs unchanged |
| III. Typing | PASS | Typed helpers + Pydantic only if extending energy models |
| IV. Slash + defer | PASS | No new commands; existing defer paths retained |
| V. APScheduler | PASS | Untouched |
| VI. Friendly errors | PASS | Asset miss → text fallback; energy data miss → fail-open (button stays enabled) |
| VII. YAGNI | PASS | Reuse pitch/roster render patterns; no new asset art pipeline; no pitch-highlight swap variant in v1 |

**Post-Phase 1 re-check**: PASS — contracts are UI/pure-helper only; no schema; Complexity Tracking empty.

## Project Structure

### Documentation (this feature)

```text
specs/042-ux-visual-refinements/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── energy-near-full-guard.md
│   ├── swap-compare-visual.md
│   └── hospital-admitted-visual.md
└── tasks.md              # /speckit.tasks — NOT created by /speckit.plan
```

### Source Code (repository root)

```text
packages/energy/energy/
├── near_full.py          # NEW — is_energy_near_full / near_full_reason
└── __init__.py           # export helpers

apps/discord_bot/core/
├── pitch_generator.py    # EXTEND or keep; optionally share font/rarity helpers
├── swap_compare.py       # NEW — generate_swap_compare_image(out_card, in_card) -> discord.File
└── hospital_board.py     # NEW — generate_hospital_board(patients) -> discord.File | None

apps/discord_bot/cogs/
├── store_cog.py          # pass near-full into StoreHubView; disable + label + embed copy
└── squad_cog.py          # SquadSwapView: attach/update compare image on select/open

apps/discord_bot/embeds/
└── hospital_embeds.py    # keep text fields; set_image attachment://hospital_board.png

apps/discord_bot/views/
└── store_facilities.py   # show_hospital_panel: render + attachments=[file]

assets/
└── admited.png           # EXISTING base art (do not rename in v1)

tests/
├── test_energy_near_full.py       # NEW
├── test_hospital_board_slots.py   # NEW — slot cap / empty / overflow text contract
└── test_squad_swap_confirm.py     # EXTEND only if compare wiring risks Confirm gate

change_log.md             # short player-facing note when shipping
```

**Structure Decision**: Keep pure threshold logic in `packages/energy` (testable, Discord-free). Keep all Pillow + `discord.File` in `apps/discord_bot/core/` next to `pitch_generator.py`. Wire three existing surfaces only—no new cogs/commands.

## Complexity Tracking

> No constitution violations requiring justification.
