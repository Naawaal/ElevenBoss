# Contract: Absence vs Outage

**Feature**: US-42.5

| Event | Sporting owner | Integrity behavior |
|-------|----------------|-------------------|
| Manager misses Play window | `026` assistant → legal XI or forfeit-if-illegal | Resolve **once** at deadline |
| Human Play early | US-42.4 match run + fixture mark | Deadline **skips** already played |
| Guild/bot unreachable | Pause (`026`/`027`) | **No** mass forfeit |
| Discord announce fail after settle | — | Present-retry only |

## Forfeit rule (binding)

Forfeit scorelines and “illegal after repair” criteria remain **`026` only**. This child forbids inventing those outcomes from infrastructure failure alone.
