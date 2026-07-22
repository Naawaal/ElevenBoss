# Contract: Economy Source/Sink Registry (US-42.7)

**Living document** — filled 2026-07-22 from codebase grep (`apps/` + economy RPCs). Every coin/energy mutation MUST appear. New faucets/sinks add a row before ship.

## Entry schema

| Column | Required |
|--------|----------|
| `id` | yes |
| `direction` | faucet \| sink \| transfer \| n/a |
| `asset` | coins \| energy \| tokens |
| `pipeline` | RPC / `apply_club_economy` |
| `idempotency_key` | pattern or “RPC-internal” |
| `owner` | spec / module |
| `notes` | optional |

## Registry

| id | direction | asset | pipeline | idempotency_key | owner | notes |
|----|-----------|-------|----------|-----------------|-------|-------|
| `match_bot_payout` | faucet+sink | coins+energy | `apply_match_economy` → `apply_club_economy` | `match:{run_id}:{club_id}` | US-42.4 / `match_rewards.py` | Energy cost on match |
| `match_league_payout` | faucet+sink | coins+energy | `apply_match_economy` | `match:{run_id}:{club_id}` | US-42.4 / `league_rewards.py` | Active player may pay energy |
| `friendly_sandbox` | n/a | — | none | — | US-42.4 INV-11 | No competitive faucet |
| `league_milestone` | faucet | coins | `apply_club_economy` | `league_milestone:{season}:{md}:{player}` (see call site) | `league_rewards.py` | Matchday pts bonus |
| `season_prize` | faucet | coins | `distribute_season_prizes` → `apply_club_economy` | `season_prize:{season_id}:{player_id}` | 026 / US-42.5 | Humans only |
| `league_entry_refund` | faucet | coins | inside `distribute_season_prizes` | `league_entry_refund:{season}:{player}` | 026 | On complete |
| `league_entry_fee` | sink | coins | `charge_league_entry_fees` | RPC-internal / season×player | 026 / lifecycle | Prep charge |
| `daily_login` | faucet | coins/energy | `claim_daily_login` | RPC-internal daily | US-25 / `store_cog` | |
| `energy_refill` | sink+faucet | coins+energy | `purchase_energy_refill` | RPC-internal daily cap | US-25 / `store_cog` | |
| `daily_pack` | n/a† | cards | `claim_daily_pack` | daily claim | US-25 / store | †cards; coins only if RPC pays |
| `weekly_payroll` | sink | coins | `process_weekly_payroll` | week key in RPC | 019 / payroll job | |
| `transfer_buy` | sink | coins | `purchase_transfer_listing` | `transfer_buy:{listing_id}` | 017 / W6 | Gross debit |
| `transfer_sale` | faucet | coins | `purchase_transfer_listing` | `transfer_sale:{listing_id}` | 017 / W6 | Seller net |
| `transfer_tax_burn` | sink | coins | implicit (gross−net) | same purchase txn | 017 Soft | No separate ledger row |
| `agent_sale` | faucet | coins | `process_agent_sale` | RPC + daily cap | 017 | |
| `scouting_purchase` | sink | coins | `purchase_scouting_player` / scout RPCs | RPC-internal | 017 | |
| `stat_drill` | sink | coins+energy | `process_stat_drill` | RPC-internal | US-23 / development | |
| `fusion_fodder` | sink | coins | `train_with_fodder` | RPC + daily fusion cap | US-23 | |
| `evolution_start` | sink | coins+energy | `start_player_evolution` | RPC + cooldown | 018 / 028 | |
| `evolution_cancel` | sink | coins | `cancel_player_evolution` | RPC fee | 018 | |
| `facility_upgrade` | sink | coins | `upgrade_club_facility` | RPC-internal | store facilities | |
| `pending_level_rewards` | faucet | coins | `claim_pending_level_rewards` | pending row ids | US-24 | Current owner |
| `support_legendary` | n/a† | card | `claim_support_legendary_reward` | RPC | support gift | †not coin faucet |
| `mentor_transfer` | n/a | XP only | `transfer_mentor_xp` | RPC daily | US-23 | No coins |
| `tokens_gems` | n/a | tokens | none | — | profile/store display | No mutation pipe today |

## Inflation / observability signals (minimum)

| Signal | How to observe |
|--------|----------------|
| Duplicate economy key hits | Ledger / `apply_club_economy` already-applied returns |
| Faucet velocity | Sum `economy_ledger` by `source` per UTC day |
| Transfer tax volume | Sum `transfer_sales_log.tax_amount` or gross−net |
| Race losses | App logs / purchase raise rates |

## Guards

- No `UPDATE players SET coins` (or equivalent) in `apps/` — mutations via `apply_club_economy` family / economy RPCs only
- New faucet/sink MUST add a row here before enablement (epic FR-011)
- Friendly MUST NOT gain a competitive coin faucet row
