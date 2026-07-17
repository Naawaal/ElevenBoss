# Data Model: Development Hub Recovery

**Feature**: `023-dev-hub-recovery`

## Entities (existing — no new tables)

### Player Card (`player_cards`)

| Field | Role for Recover |
|-------|------------------|
| `id` | Selection / RPC target |
| `owner_id` | Must match manager |
| `fatigue` (0–100) | Must be &lt; 100 to select; increased by grant, clamped to 100 |
| `injury_tier` | Must be NULL |
| `in_hospital` | Must be false |
| `is_retired` | Must be false |
| `in_academy` | Must be false (UI + RPC reject) |
| name / overall / level | Display only |

### Club (`players`)

| Field | Role for Recover |
|-------|------------------|
| `discord_id` | Owner |
| `action_energy` | Debited by total batch cost via `apply_club_economy` |
| `daily_drill_count` / `daily_drill_reset_at` | **Not** modified by Recover after this feature |

### Game config (`game_config`)

| Key | Default | Meaning |
|-----|---------|---------|
| `fatigue_recovery_energy` | 5 | Action energy **per** selected player |
| `fatigue_recovery_session` | 40 | Fatigue points granted **per** selected player |

### Related locks (unchanged tables)

- `active_evolutions` (status=`active`) — card ineligible
- Transfer listing tables / `assert_card_not_on_transfer_list` — card ineligible
- Hospital care paths — unchanged; Recover never admits/discharges

## Logical entity: Recovery Batch

| Attribute | Rule |
|-----------|------|
| `card_ids` | Distinct UUIDs, length 1–3 |
| `energy_total` | `len(card_ids) × fatigue_recovery_energy` |
| `fatigue_grant` | `fatigue_recovery_session` each (applied delta may be lower near 100) |
| `xp` / `coins` | Always 0 |
| Atomicity | All cards succeed or none (no energy spend, no fatigue change) |

## Validation rules

1. Batch size ∈ [1, 3]
2. Every card owned, not retired, not academy, not injured, not in hospital, fatigue &lt; 100
3. No active evolution; not on transfer list
4. Club not in match (`assert_not_in_match`)
5. `action_energy >= energy_total` after `sync_action_energy`
6. Duplicate IDs in the array → reject

## State transitions

```text
Eligible card (fatigue F < 100)
  --[successful Recover batch including card]-->
fatigue = min(100, F + grant)

Club energy E
  --[successful Recover batch of N]-->
E' = E - N×cost
```

No intermediate “recovering” status — sessions are instant.

## Out of model scope

- New drill-log rows for Recover
- New Recover daily counter table
- Physio inventory / Store SKUs
