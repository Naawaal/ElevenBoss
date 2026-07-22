# Tasks: Hub Hot-Path Wave 2 (US-44)

**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

## Phase 0 — Spec

- [x] T001 Author `spec.md` / `plan.md` / `research.md` / contracts
- [x] T002 Point `.specify/feature.json` at `specs/039-hub-hot-path-wave2`
- [x] T003 Link from `.specify/specs/v1.0.0/plan.md`

## Phase 1 — League (HP-6)

- [x] T010 Batch `_league_join_limits` via `get_game_config_many`
- [x] T011 Parallelize `guild_config` ∥ `leagues` on `league_hub` / share helper with `show_hub`
- [x] T012 Conditional registration count (V1 regs XOR members)
- [x] T013 Gather join-limits ∥ player division on registration embed path
- [x] T014 `hub_timer("league_hub")`

## Phase 2 — Squad (HP-5)

- [x] T020 `asyncio.gather` in `fetch_squad_data`
- [x] T021 Card total via `count="exact"` (no full id list for len)
- [x] T022 `hub_timer("squad")` on `/squad` command path

## Phase 3 — Profile (HP-4)

- [x] T030 TTL-cache `global_divisions` (`division_cache` helper)
- [x] T031 Gather hospital ∥ history (and energy-safe ordering)
- [x] T032 `hub_timer("profile")`

## Phase 4 — Verify

- [x] T040 `tests/test_hub_hot_path_wave2.py` contracts
- [x] T041 Update US-43 hot-path catalog After column
- [x] T042 `change_log.md` blurb
- [x] T043 Mark tasks complete; feature status Implemented

## Dependencies

T010–T014 before claiming HP-6 done. T020–T022 ∥ T030–T032 after T001.
