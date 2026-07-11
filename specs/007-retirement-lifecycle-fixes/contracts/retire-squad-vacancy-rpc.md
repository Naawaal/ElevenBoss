# Contract: Retire Squad Vacancy RPC

**RPC**: `retire_player_card(p_card_id UUID) → JSONB`  
**Related**: `process_season_aging()`, `set_formation_and_assignments(...)`  
**Feature**: `007-retirement-lifecycle-fixes`  
**Migration**: `053_retirement_lifecycle_fixes.sql`

## `retire_player_card` behavior

1. Lock card row; reject if missing or already retired.
2. Read `owner_id`, and if present the `position_slot` from `squad_assignments` for this card.
3. `DELETE` from `squad_assignments` where `player_card_id = p_card_id`.
4. Set `is_retired = TRUE`, `retired_at = NOW()`.
5. **If a starting slot was vacated** (`v_slot` not null):
   - Load club `formation` from `squads` (default `4-4-2`).
   - `v_role := formation_slot_role(formation, v_slot)`.
   - Select one reserve: owned by `owner_id`, `is_retired = FALSE`, not in any `squad_assignments` for that club, `position = v_role`, order by `overall DESC, id ASC`, `LIMIT 1`.
   - If found: `INSERT` into `squad_assignments (discord_id, position_slot, player_card_id)`.
   - If not found: `UPDATE players SET squad_invalid = TRUE WHERE discord_id = owner_id`.
6. If after resolution the club has 11 assignments, set `squad_invalid = FALSE` (auto-clear on successful promote). If a starting slot remains empty, `squad_invalid` stays/remains `TRUE` until the manager saves a valid 11 via `set_formation_and_assignments`.
7. Return JSON including at least: `card_id`, `owner_id`, `retired_at`, `vacated_slot` (nullable), `promoted_card_id` (nullable), `squad_invalid` (bool after resolution).

## `set_formation_and_assignments`

After successfully writing all assignment rows from `p_assignments`:

- If assignment count is 11: `UPDATE players SET squad_invalid = FALSE WHERE discord_id = p_discord_id`.
- Existing validation (ownership, GK slot 1 / formation rules as currently enforced) unchanged.
- Empty slots are **not** filled by `swap_squad_players` (swap requires an existing starter); repair is auto-promote at retire time or full XI save only.

## `process_season_aging`

- Extend SELECT/UPDATE to include `sho`, `dri`.
- Apply decline per [aging-decline-curve.md](./aging-decline-curve.md).
- Continue calling `retire_player_card` for age ≥ retirement_age (vacancy logic lives there).

## Schema

```sql
ALTER TABLE public.players
  ADD COLUMN IF NOT EXISTS squad_invalid BOOLEAN NOT NULL DEFAULT FALSE;
```

Extend `verify_required_schema.sql` with `column:public.players.squad_invalid`.

## Non-goals

- New tables
- Filtering reserves by injury/fatigue
- Changing swap_squad_players beyond existing role checks
