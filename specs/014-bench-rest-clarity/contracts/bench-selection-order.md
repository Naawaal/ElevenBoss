# Contract: Bench selection order

**Feature**: `014-bench-rest-clarity`

## Rule

`fetch_bench_ids(owner_id, starter_ids) -> list[str]` (max 7):

1. Exclude starter IDs
2. Exclude `is_retired`
3. Exclude `injury_tier IS NOT NULL`
4. Order by **`overall` descending** (tie-break: stable `id` ASC optional)
5. Return first **7** IDs

## Rationale

Matches touchline capacity; removes undefined PostgREST order so managers can predict who rests (highest-OVR unused healthy players).

## Non-goals

- Do not expand beyond 7 in this feature
- Do not require a separate “bench slot” table

## Tests

- 10 unused healthy → rest the 7 highest overall
- Injured unused never included
- Starters never included
