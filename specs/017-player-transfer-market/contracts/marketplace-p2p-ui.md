# Contract: Marketplace P2P UI (`/marketplace`)

**Feature**: `017-player-transfer-market`  
**Surface**: Extend existing hub only — **no new slash command**

## Feature flag behavior

| Flag | Hub |
|------|-----|
| `false` | Today’s UX: Sell to Agent, Search Market → scouting only, My Listings **disabled** (or hidden) |
| `true` | Enable My Listings; Search Market offers **Regen Scouting** vs **Transfer Board**; listing count live |

Bot reads flag via `get_game_config` / `p2p_transfer_market_enabled` RPC each hub open (cache OK ≤60s ephemeral session).

## Hub embed

- Balance coins/tokens unchanged.
- **Active Listings: `n / slot_cap`** from DB (never hard-coded `0 / 5` when flag on; when flag off may show `—` or disabled `0 / 5`).

## Navigation map

```text
/marketplace
├── Sell to Agent          → existing sell flow (eligible excludes transfer-listed)
├── Search Market
│   ├── Regen Scouting     → existing show_scouting_menu
│   └── Transfer Board     → filter → select → Buy Now confirm
└── My Listings
    ├── Select listing → Cancel
    └── List Player → select card → Modal price → Confirm
```

## Interactions

- All buttons/selects: `defer` before RPC (Section 4 UI rule).
- Owner-only `interaction_check` (existing pattern).
- Price entry: Discord **Modal** (integer coins); show fair / floor / ceil / net preview on confirm embed before final submit **or** validate in modal submit with error followup.
- Filters (Transfer Board): **two-stage Discord UI** (action row = one Select max). Stage 1: Position + OVR/Age/POT band Selects → Apply. Stage 2: listing Select + Buy Now / Change Filters / Back. Continuous free-range min/max Modals are out of scope. Query capped 25 for select options; empty state copy.
- Buy confirm embed: name, pos, OVR, age, POT, price; note “You pay listed price. Seller nets 90% after market tax.”
- Double-tap / race: map RPC errors to friendly ephemeral (already sold / insufficient coins).

## Peer UI filters

- Agent sell eligible list: exclude active-listed card ids.
- Development / squad: exclude or reject listed cards (message: “Delist this player first”).

## Sale notification (P2)

Seller confirmation when purchase completes while offline: ephemeral on next hub open is enough for v1; optional DM later (out of scope unless tasks add it).
