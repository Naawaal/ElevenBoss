# Contract: `get_evolution_hub_status`

**Feature**: `028-evolution-start-button`  
**RPC**: `public.get_evolution_hub_status(p_owner_id bigint) → jsonb`

## Purpose

Single read model for Evolution Command Center: slots, cooldown, start eligibility, costs, active/history lists. **Must use the same `game_config` keys and defaults as `start_player_evolution` for cooldown, max active, and start costs.**

## Config keys (required alignment)

| Key | Used for | Start RPC default | Seed (046) |
|-----|----------|-------------------|------------|
| `evolution_max_active` | Slot cap / `can_*` | 3 | 3 |
| `evolution_cooldown_hours` | Cold-start window | 10 (fallback) | **6** |
| `evolution_start_energy` | Energy cost | 25 | 25 |
| `evolution_start_flat` | Coin flat | 500 | 500 |
| `evolution_start_ovr_mult` | Coin × OVR | 5 | 5 |

## Response shape (post-fix)

Existing keys retained. Cost fields updated to live config; additive flat/mult keys for honest UI.

```json
{
  "active_count": 0,
  "max_active": 3,
  "slots_label": "0/3 slots used",
  "last_evolution_started_at": "2026-07-22T…",
  "cooldown_ends_at": "2026-07-22T…",
  "cooldown_remaining_seconds": 21600,
  "can_cold_start": false,
  "can_replace": false,
  "can_start": false,
  "training_energy": 55,
  "start_energy_cost": 25,
  "start_coin_flat": 500,
  "start_coin_ovr_mult": 5,
  "start_coin_multiplier": 5,
  "active": [],
  "recent_completed": []
}
```

### Eligibility rules (unchanged semantics)

- `can_cold_start` ⟺ `active_count < max_active` AND (never started OR `now >= last_started + cooldown_hours`)
- `can_replace` ⟺ cancel after `last_evolution_started_at` exists AND `active_count < max_active`
- `can_start` ⟺ `can_cold_start OR can_replace`

### Invariants

1. If `start_player_evolution` would accept a cold start for cooldown reasons, then `can_cold_start` is true (slot permitting).
2. `cooldown_remaining_seconds` uses the same `cooldown_hours` as start.
3. `start_coin_multiplier` MUST equal live ovr mult (not legacy 10).
4. No schema change to tables; function signature unchanged (`bigint` → `jsonb`).

## Call site

- `apps/discord_bot/cogs/development_cog.py` → `fetch_evolution_hub_status` → `ClubEvolutionsHubView` Start button `disabled=not can_start`.
