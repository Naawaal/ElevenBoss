# Contract: Wage formula & bill

**Feature**: 019 | **Pure**: `packages/economy` | **SQL mirror**: payroll RPC

## Per-card weekly wage

```text
base = (max(ovr, 40) - 40)^2 * wage_scale_factor + 10
wage = floor(base * rarity_mult * age_mult * pot_mult)
```

- `ovr`: `overall` else `base_rating` else 50  
- `wage_scale_factor`: config default **1.2** (existing)  
- `rarity_mult`: from game_config / package defaults (Common→Legendary)  
- `age_mult` / `pot_mult`: **1.0** while respective `*_enabled` flags are false  

## Club weekly bill

```text
bill = floor(sum(wage(card) for card in starting_xi) * wages_payroll_bill_scale)
```

- `starting_xi`: cards referenced by `squad_assignments` for the club (0–11).  
- Empty XI → bill 0 (still may process debt-only if debt > 0).

## Package API (planned)

- `card_weekly_wage(card: dict, config) -> int`  
- `calculate_weekly_wages(squad, config) -> int` — retain; implement via `card_weekly_wage`  
- `strike_blocks_friendly(strikes, config) -> bool`  
- `strike_blocks_market(strikes, config) -> bool`  
- `contract_in_grace(expires_at, now, grace_days) -> bool`  
- `contract_blocks_xi(expires_at, now, grace_days) -> bool`  

## Parity

SQL `process_weekly_payroll` MUST use the same arithmetic (document constants in migration comments; prefer SQL helpers calling same numeric literals as package defaults).
