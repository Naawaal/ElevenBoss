# Contract: Profile Renew UI Honesty

**Feature**: `047-fix-contract-renew`  
**Consumers**: `PlayerProfileView.renew_callback` in `apps/discord_bot/cogs/player_cog.py`

## Flow

1. Owner check + `defer(ephemeral=True)` (existing).
2. Compute cost via `calculate_contract_renewal_cost`; `p_extension_days` from `contract_renewal_days` (default 7).
3. Call `renew_contract` with optional per-click `p_idempotency_key` (UUID string recommended).
4. Re-select `contract_expires_at` (and overall/name as needed) for the card.
5. Load `contract_grace_days` (default 7).
6. **Success path**: expiry exists and is **not** past grace (`not contract_blocks_xi(...)`) → success embed naming cost + new expiry.
7. **Failure path**: RPC exception → existing error embed; **or** RPC returned without clearing past grace → error embed that renewal did not take effect (ask to retry / contact ops if persistent).

## Forbidden

- Treating bare `res.data is True` as proof the card is match-eligible without checking expiry.
- Claiming “Contract Renewed” while the card still fails the past-grace gate.

## Optional polish (not P1-blocking)

- Avoid shared static `custom_id="renew_contract_profile"` across all profile messages (unique per view or omit) so post-restart clicks fail closed cleanly.
