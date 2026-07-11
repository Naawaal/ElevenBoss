# Contract: Energy regen display

## Effective regen (source of truth)

| Lever | Value |
|-------|-------|
| `game_config.energy_regen_per_min` | `0.25` |
| Implied | +1 energy every 4 minutes |
| Empty→full at max 100 | 400 minutes ≈ 6h 40m |

`sync_action_energy` already reads this key (default fallback must be `0.25` after this feature, not `0.1666667`, wherever bot code duplicates the rate).

## Player-visible strings

| Surface | Contract |
|---------|----------|
| Energy status (`format_action_energy_status`) | Time-to-full computed with effective regen (0→100 shows ~6h 40m, not 10h) |
| Insufficient energy error (`api_errors`) | Must say regenerates +1 every **4 minutes** (or equivalent derived from config), not 6 |
| `/store` refill copy | Unchanged (coin refill, not passive regen) |
| Friendly footer | Unchanged (no energy / no XP) |

## Bot helper defaults

| Helper | Required default after fix |
|--------|----------------------------|
| `REGEN_PER_MIN` (or replacement) | `0.25` / `1/4` |
| Async paths with DB | Prefer `get_game_config_numeric('energy_regen_per_min', 0.25)` |

## Out of contract

- Changing refill costs, refill amount, or daily refill cap
- Changing `energy_max`
- Adding a new slash command for energy
