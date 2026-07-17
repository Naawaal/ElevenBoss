# Contract: Transfer Tax & Price Bounds (pure)

**Feature**: `017-player-transfer-market`  
**Package**: `packages/economy/economy/transfer_market.py`  
**SQL mirror**: RPC bodies use same formulas / `game_config` multiples

## Fair value

```text
fair = generate_agent_offer(ovr, rarity, age=age, potential=pot)
     # SQL: public.compute_agent_offer(...)
```

## Bounds

```text
floor_mult = get_config(transfer_price_floor_mult, 0.75)
ceil_mult  = get_config(transfer_price_ceil_mult, 2.5)

floor = max(50, floor(fair * floor_mult))
ceil  = max(floor, floor(fair * ceil_mult))

assert floor <= price <= ceil   # else reject list
```

## Tax

```text
tax_bps = get_config(transfer_tax_bps, 1000)   # 1000 = 10%
tax     = floor(gross * tax_bps / 10000)
net     = gross - tax
# equivalently net = floor(gross * (10000 - tax_bps) / 10000) with tax = gross - net
```

Preview for UI: `seller_net_preview(price) -> int`.

## Tests (`tests/test_transfer_market_math.py`)

- Tax 10% of 1000 → tax 100, net 900
- Floor/ceil ordering never inverted
- Price below floor / above ceil rejected by pure `validate_listing_price`
- Fair value at OVR 45+ matches existing agent offer spirit
