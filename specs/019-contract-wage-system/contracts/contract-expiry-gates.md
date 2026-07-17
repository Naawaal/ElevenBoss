# Contract: Contract expiry gates

**Feature**: 019 | **Migration**: 063 + bot `squad_validity` + squad assign

## Playability rules

Let `grace = get_game_config_int('contract_grace_days', 7)`.

| Condition | Squad assign to XI | Match / XI | UI |
|-----------|-------------------|------------|-----|
| `now < contract_expires_at` | Allowed | Allowed | Show days left |
| `expires_at ≤ now < expires_at + grace` | Allowed | Allowed | **Grace warning** on profile + Finances if any XI in grace |
| `now ≥ expires_at + grace` | **Blocked** | **Blocked** | Must renew or replace before assign / match lock |
| age ≥ 35 renew | N/A | N/A | `renew_contract` still rejects |

**No auto-release in v1** — expired cards remain owned until renew/retire/sale paths elsewhere.

## Bot / gate integration

- Extend `apps/discord_bot/core/squad_validity.py`: when loading XI cards, if any card `contract_blocks_xi(...)`, treat like invalid XI with clear message (“Contract expired: {name} — renew or replace”).
- `battle_cog` / league fixture starts must use squad_validity — grep + wire (T025).
- Squad **assign** into `squad_assignments`: reject past-grace cards (FR-007).
- Profile renew: pass `p_extension_days` from `contract_renewal_days` config (default 7); cost unchanged formula; verify age ≥35 still raises.

## SQL helpers (optional)

```sql
card_contract_blocks_xi(p_expires TIMESTAMPTZ) RETURNS BOOLEAN
```

Used if match/squad RPCs need DB-side enforcement; bot-side gate is required for all Discord entry points.

## Non-goals v1

- Auto-delete / free transfer of past-grace cards
- Blocking drills/fusion solely for expiry (only XI assign + match gate)
- Morale mutation
