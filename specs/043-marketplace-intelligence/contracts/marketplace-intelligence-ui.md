# Contract: Marketplace Intelligence UI

**Feature**: `043-marketplace-intelligence`  
**Command**: Extend `/marketplace` only — no new slash command

## Entry points

| Surface | Addition |
|---------|----------|
| Transfer Board | Sort control (select or buttons) for the 7 modes; default `newest` or current behavior |
| Listing detail (pre–Buy Now) | Price discovery summary + ownership career trail (compact) |
| List Player confirm (optional but preferred) | Price discovery for the card being listed (insufficient-data friendly) |
| Owned card career | Accessible from listing detail and/or a “Career” control on My Listings / board detail — reuse one embed builder |

## Copy rules

- Label discovery as based on **similar completed sales** (position, rarity, nearby OVR).  
- When insufficient: e.g. “Not enough recent sales for similar players yet.”  
- Never show fabricated averages.  
- Ownership empty/minimal: show current club only after bootstrap, or “No prior clubs on record.”  
- Keep Regen Scouting vs Transfer Board labeling clear (unchanged).

## Interaction rules

- Defer before RPC/DB (existing hub pattern).  
- Ownership check / ephemeral ownership via existing `OwnedView` patterns.  
- Double-tap Buy Now: unchanged race behavior; history written once.  
- P2P flag off: hide Transfer Board discovery/sort; agent + scouting unchanged.

## Performance

- Do not call `get_market_analytics` on hub open.  
- Price discovery: one RPC per detail/list open.  
- Career: one query/RPC per open.  
- Sort: in-memory only after board load.

## Out of UI scope

- Ops analytics dashboard  
- Weekly market report posts  
- Featured listings carousel
