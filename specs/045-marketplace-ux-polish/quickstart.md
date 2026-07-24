# Quickstart: Marketplace V1.5 UX Polish

**Feature**: `045-marketplace-ux-polish`  
**Prerequisites**: Migrations `062`/`075`/`086` applied; P2P flag as needed for board tests; bot running latest code.

## 1. Unit checks

```powershell
pytest tests/test_marketplace_ux_polish.py tests/test_market_intelligence.py -q
```

Expect: time-left, trend labels, discovery/`recent_sales` formatting, ask-vs-fair helpers green.

## 2. Discord smoke — Transfer Board (P2P on)

1. `/marketplace` — title reads **Marketplace**; sub-areas clear.  
2. Search → Transfer Board → Apply (defaults).  
3. Results show **scannable preview** with prices and time-left.  
4. Select a listing — detail shows rarity, ask vs fair, discovery with readable trend + recent sales when data exists.  
5. Buy Now — confirm still shows compact fair/market cue.  
6. Complete or Cancel — no double charge; errors readable.

## 3. My Listings & Agent

1. My Listings — each active listing shows time remaining.  
2. Sell to Agent — offer shows **POT** before Confirm.  
3. Back buttons say **Back to Market** (or Back to Listings where appropriate).

## 4. Perf spot-check (dev)

- Change Sort on results: should **not** re-hit full board listing query (log/trace).  
- Select listing: no full board re-fetch.

## 5. Changelog

When shipping to players, add a short `change_log.md` note (clearer board, time-left, fair/market cues).

## Contracts

- [board-preview-and-buy.md](./contracts/board-preview-and-buy.md)  
- [discovery-presentation.md](./contracts/discovery-presentation.md)  
- [marketplace-copy-language.md](./contracts/marketplace-copy-language.md)  
- [marketplace-hot-path.md](./contracts/marketplace-hot-path.md)  
)
