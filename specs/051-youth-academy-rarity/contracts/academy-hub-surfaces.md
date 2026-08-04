# Contract: Academy hub surfaces

**Feature**: `051-youth-academy-rarity`  
**Shared entry**: `show_academy_hub(interaction, *, origin: Literal["development","squad","profile"])`

## Entry points

| Surface | Role |
|---------|------|
| `/development` → Youth Academy | **Primary** (FR-018) |
| `/squad` → Youth | Optional same hub |
| `/profile` → Manage Academy | Temporary compatibility |
| `/store` → Club Facilities | Upgrade only + before→after preview |
| `/academy` | **Must not exist** |

Back button returns to `origin` hub (not hard-coded Profile).

## Hub embed must show

- YA level, occupied/capacity (allow occupied > cap display), next Monday intake line
- Weekly promotes used/cap; discovery signing used/cap if applicable
- Active assessment/discovery status
- Prospect rows: fogged POT range, interval-based stars, progress, readiness advisory, aging warning if any

## Actions

- Assess scout (per prospect) / cancel-safe finalize
- Discovery scout (capacity + weekly sign gated)
- Promote (weekly cap + fee + graduation embed)
- Release (confirm; no refund)

## Graduation embed

On successful promote: name, OVR, rarity, age, time developed — replace bare success toast.

## Facility preview (`store_facilities`)

Before→after for: capacity, rarity chance summary, initial scout-range width, development speed. Copy must not claim existing prospects reroll.
