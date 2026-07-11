# Data Model: Fix Match XP + Energy Regen

No new tables or columns. This feature uses existing entities and config keys.

## Entities (existing)

### Player card (`player_cards`)

| Attribute | Role in this feature |
|-----------|----------------------|
| `id` | Target of `apply_card_xp` |
| `name` | Required to attribute goals/assists/MOTM when building match XP |
| `xp` / `level` | Updated only via `apply_card_xp` |
| age / DOB fields | Used by age multiplier in `match_xp_reward` |

**Validation**: League recovery payloads MUST hydrate at least `id`, `name`, and fields needed for effective age before XP apply.

### Match history (`match_history`)

| Attribute | Role |
|-----------|------|
| `id` | Passed as `p_match_history_id` |
| `xp_applied_at` | Idempotency — set only after successful `process_match_result` |
| `run_id` | Links bot/league run for reward recovery |

**State**: `xp_applied_at IS NULL` → XP pending; non-null → skip re-apply.

### Action energy (`players.action_energy`)

| Attribute | Role |
|-----------|------|
| `action_energy` | Current energy (max from `game_config.energy_max`, default 100) |
| `action_energy_updated_at` | Lazy regen baseline for `sync_action_energy` |

**Regen rule**: `floor(minutes_elapsed × energy_regen_per_min)`, capped at max.

### Game config (`game_config`)

| Key | Target value | Notes |
|-----|--------------|-------|
| `energy_regen_per_min` | `0.25` | 1 energy / 4 minutes |
| `energy_max` | `100` | Unchanged |
| `match_energy_bot` | `15` | Already in 046; out of scope to change further |
| Energy refill keys | unchanged | FR-008 |

### XP log (`player_xp_log`)

Append-only audit of XP grants. Inserts require `apply_card_xp` SECURITY DEFINER after 047 privilege revoke.

### Daily match-XP allowance

Logical cap: 100 XP per card per day for source `match_simulation` (enforced inside `apply_card_xp`). Not a separate table for this feature.

## Relationships

```text
Match (bot|league) completed
  → match_history row
  → process_match_result(card_ids, xp_amounts)
      → apply_card_xp per card (respects daily cap / max level)
          → player_cards.xp/level + player_xp_log

Friendly completed
  → no process_match_result / no energy spend

sync_action_energy(club)
  → reads game_config.energy_regen_per_min
  → updates players.action_energy
```

## State transitions

| From | Event | To |
|------|-------|-----|
| Match rewards pending XP | `process_match_result` OK | `xp_applied_at` set |
| Match rewards pending XP | RPC hard fail | `xp_applied_at` still null; manager sees error |
| Card under daily cap | match XP grant | XP increases; log row |
| Card at daily cap / max level | match XP grant | `xp_added = 0`; match still OK |
| Energy &lt; max | time elapses + sync | energy increases toward max at 0.25/min |
