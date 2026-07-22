# Contract: Evolution Hub Start Cost Copy

**Feature**: `028-evolution-start-button`  
**Surface**: `/development` → Evolutions → Evolution Command Center embed (Resources field)

## Current (incorrect)

```text
💰 Start cost: `25 energy` + `10×OVR` coins per track
```

## Required (honest)

Club-level formula matching live start:

```text
💰 Start cost: `25 energy` + `500+5×OVR` coins per track
```

(or equivalent wording that includes both flat and per-OVR terms; energy/flat/mult may come from hub status fields when present, else package mirrors `EVOLUTION_START_ENERGY` / `EVOLUTION_START_FLAT` / `EVOLUTION_START_OVR_MULT`).

## Rules

1. MUST NOT claim `10×OVR` as the sole coin formula.
2. MUST stay consistent with track-picker start cost for a selected card (`evolution_start_cost(ovr)`).
3. No new Discord command or button — copy-only + status-driven values.

## Call site

- `show_club_evolutions_hub` in `apps/discord_bot/cogs/development_cog.py`
