# Research: Hub Hot-Path Wave 2

**Date**: 2026-07-22 | **Spec**: [spec.md](./spec.md)

## Baseline (from US-43 catalog + source)

| ID | Est. sequential RTs | Dominant waste |
|----|---------------------|----------------|
| HP-4 Profile | 5 | Serial player → energy → hospital → divisions → history; divisions static |
| HP-5 Squad | 5 | Five serial selects; cards `select id` for `len` only |
| HP-6 League | 8+ | Serial guild_config → league → season; double `get_game_config`; members then maybe overwrite with V1 regs; embed extras |

## Decisions

| Topic | Decision | Rationale |
|-------|----------|-----------|
| Dashboard RPC | Defer | Gather meets SC-004 cheaper; add RPC only if fail |
| Auto-sim on open | Keep | US-42.5 / sporting integrity |
| Divisions cache | Process TTL 600s via `config_cache` | Rarely mutates; non-priced |
| Join gates | `get_game_config_many` | Same as drills; non-priced under FR-012 |
| Squad count | `select(..., count="exact")` | Avoid payload of all card ids |
| Marketplace | Out of wave | Measure later |

## Risks

- Gathering `maybe_single` calls: PostgREST client must tolerate parallel executes on shared client — already used in development_cog gather.
- Cached divisions stale after rare admin edit — TTL 10m acceptable; document invalidate helper.
