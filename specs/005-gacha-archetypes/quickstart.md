# Quickstart: Gacha Card Archetypes & Factory Reliability

**Feature**: `005-gacha-archetypes` | **Date**: 2026-07-11

Validation after implementation. Assumes migration `051` (role persistence) is applied and `verify_required_schema.sql` passes.

## Prerequisites

- Editable installs for `player_engine` and `gacha`
- `DATABASE_URL` available if verifying RPC inserts
- Bot optional for Discord embed checks

## 1. Unit: archetype diversity

```bash
pytest tests/test_player_archetypes.py -q
```

**Expect**: Fixed-seed / batch FWD generation yields ≥2 distinct `role` values; Poacher vs Speedster mean SHO/PAC differ in the expected direction ([created-player-card.md](./contracts/created-player-card.md)).

## 2. Unit: True OVR exactness

```bash
pytest tests/test_player_factory_ovr.py -q
```

**Expect**: Large batch across positions/rarities: `overall == target_ovr` when bounds allow; no leftover mismatch from abandoned loops ([data-model.md](./data-model.md)).

## 3. Unit: pack config

```bash
pytest tests/test_pack_configs.py -q
```

**Expect**: Standard mix 60/30/8/2; unknown `pack_id` raises; factory/OVR modules untouched when only config changes ([pack-config.md](./contracts/pack-config.md)).

## 4. Regen / youth role present

```bash
pytest tests/test_regen_pool.py -q
# plus youth intake tests if present / extended
```

**Expect**: Generated dict/model includes non-default archetype `role` (not always `Balanced`).

## 5. RPC persistence (manual or scratch)

1. Apply `051_card_role_persistence.sql`.
2. Claim a daily pack or register a test club with payload that includes `"role": "Poacher"`.
3. `SELECT role FROM player_cards WHERE …` → **Expect** `Poacher`, not default `Balanced`.

## 6. Discord UX smoke

1. `/store` → claim daily pack (off cooldown).
2. **Expect**: Pack embed shows role/archetype per card; rarity mix still feels Standard.
3. `/squad` (or player inspect) → **Expect** `💼 {Archetype}` matches claim.

## 7. Regression checklist

- [ ] No new slash commands
- [ ] Standard weights unchanged in code config
- [ ] `calculate_true_ovr` / PlayStyle tables untouched
- [ ] Grep: intake RPCs INSERT `role`; `card_rpc_payload` includes `role`
- [ ] `change_log.md` note prepared for ship
- [ ] `.specify/specs/v1.0.0/` reconciled on implement

## References

- [plan.md](./plan.md)
- [research.md](./research.md)
- [contracts/role-persistence-rpc.md](./contracts/role-persistence-rpc.md)
