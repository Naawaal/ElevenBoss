# Contract: Board Preview & Buy Path

**Feature**: `045-marketplace-ux-polish`  
**Surfaces**: Transfer Board results, listing detail, Buy confirm

## Board results (pre-select)

Embed MUST include a compact preview of loaded listings (target: up to 8 lines, Discord field limits):

- `Name` · `OVR` · ask `🪙` · time-left  
- Header may note count and “up to 25” when truncated  

Select menu descriptions SHOULD include OVR, price, and time-left (char budget permitting).

## Listing detail

MUST show when available:

- Rarity (if present on card join)  
- Ask vs fair line via `fair_value_coins`  
- Time remaining  
- Existing discovery + ownership (polished per discovery contract)  

## Buy confirm

MUST retain at least:

- Player identity + OVR  
- Ask price  
- One compact market/fair cue (fair line and/or short discovery summary)  

MUST NOT invent numbers. Tax/net reminder may appear once, briefly.

## Non-goals

- Skipping Buy confirm entirely  
- New purchase RPC  
- Recommended-price AI copy  
)
