# Contract: RPC Guard Audit Template

**Feature**: US-42.2 | **Wave W0**

## Purpose

Before patching, record whether each mutating RPC already enforces matrix cells.

## Checklist (fill during implement)

| RPC / path | Actions | MatchLocked | Listed | Hospital | Evo | Academy | Retired | InXI rules | Gap? |
|------------|---------|-------------|--------|----------|-----|---------|---------|------------|------|
| `create_transfer_listing` (062) | list_transfer | Y | self | Y | Y | Y | Y | Y (block XI) | No |
| `cancel_transfer_listing` (062) | cancel_listing | ? | owns listing | — | — | — | — | — | Soft — add assert |
| `process_agent_sale` (062) | agent_sell | Y | Y | Y | Y | — | Y | — | Soft — injury OK; academy soft |
| `start_player_evolution` (062→084) | start_evolution | Y | Y | Y | self | Y | Y | **Allow RosterFree + InXI**; Evolving may stay InXI | Closed (084) |

| `claim_evolution_reward` (038) / `cancel_player_evolution` (047) | claim/cancel | partial | partial | — | self | — | — | — | Soft — add assert |
| `process_stat_drill` (062) | drill | Y | Y | **N** | Y | **N** | Y | OK (InXI allow) | **Yes Critical** |
| `train_with_fodder` (062) | fusion | Y | Y | — | Y | — | — | — | Soft |
| `allocate_skill_point` / mentor (062) | allocate | Y | Y | — | — | — | — | — | Soft |
| `admit_to_hospital` (061) | admit_hospital | **N** | **N** | self | **N** | **N** | **N** | **N** | **Yes Critical** |
| `discharge_from_hospital` (050) | discharge | ? | — | self | — | — | — | — | Soft |
| `process_recovery_batch` (066) | recover_fatigue | Y | Y | Y | Y | Y | Y | — | No |
| Academy promote/release (060) | academy_* | ? | ? | ? | ? | self | ? | — | Soft |
| `swap_squad_players` (062) | assign_xi | Y | Y (reserve) | **N** | **N** | **N** | **N** | partial | **Yes Critical** |
| `retire_player_card` (053) | retire | ? | ? | ? | ? | ? | self | — | Soft |

Mark Gap = Yes only if a matrix Block can succeed today.

## Prioritized gaps (Critical first)

1. **`admit_to_hospital`** — can admit Listed / Evolving / InXI / MatchLocked club
2. **`start_player_evolution`** — can start while Hospitalized / InAcademy / InXI / Retired
3. **`process_stat_drill`** — can drill while Hospitalized / InAcademy
4. **`swap_squad_players`** — can assign hospital/evo/academy/retired reserve into XI

## Exit

Prioritized gap list drives which `CREATE OR REPLACE` bodies land in 075+.
