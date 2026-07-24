# Contract: Transfer Board Sort

**Feature**: `043-marketplace-intelligence`  
**Surface**: Search Market → Transfer Board (existing filters unchanged)

## Modes

| Mode key | Order |
|----------|--------|
| `lowest_price` | `price_coins` ASC |
| `highest_price` | `price_coins` DESC |
| `highest_ovr` | card `overall` DESC |
| `highest_potential` | card `potential` DESC |
| `newest` | listing `created_at` DESC |
| `ending_soon` | listing `expires_at` ASC |
| `best_value` | `price_coins / fair_value` ASC (lower better) |

## Fair value for Best Value

- Compute with existing `fair_value_coins` / `generate_agent_offer` from card OVR, rarity, age, POT at browse time.  
- If fair value missing or ≤ 0: sort those rows **last** (stable relative order among themselves).

## Application point

1. Fetch active listings (existing bound, e.g. 50).  
2. Apply existing position/OVR/age/POT band filters in-app.  
3. Apply selected sort to the filtered list.  
4. Present ≤25 Discord select options (unchanged cap).

Changing sort MUST NOT drop active filters. Empty filtered set → existing empty-state embed.

## Pure helper

`sort_transfer_listings(rows, mode, *, fair_value_for_row) → list` in `packages/economy` (or `transfer_market.py`) — unit tested; no Discord imports.

## Non-goals

- Global DB `ORDER BY` pagination across unlimited listings  
- Sorting regen scouting pool (out of scope)
