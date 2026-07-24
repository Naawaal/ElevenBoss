# Data Model: Marketplace V1.5 UX Polish

**Feature**: `045-marketplace-ux-polish`  
**Schema**: **No new tables or columns.** Presentation models over existing 017/043 data.

---

## 1. Reused persisted entities

| Entity | Source | Fields used for polish |
|--------|--------|------------------------|
| Transfer listing | `transfer_listings` | `price_coins`, `expires_at`, `created_at`, status |
| Player card (join) | `player_cards` | `name`, `position`, `overall`, `potential`, `rarity`, age via DOB |
| Price discovery | RPC `get_price_discovery` | avg/median, active low/high/count, trend, `recent_sales`, insufficient flags |
| Ownership history | RPC `get_card_ownership_history` | ordered club segments |
| Fair value | `fair_value_coins(...)` pure | ask-vs-fair line |

---

## 2. Presentation models (not tables)

### ListingPreviewLine

| Field | Meaning |
|-------|---------|
| `name` | Card display name |
| `overall` | OVR |
| `price_coins` | Ask |
| `time_left` | Relative string from `expires_at` (e.g. `14h left`, `Ending soon`) |
| optional `position` | If char budget allows in Select/desc |

### AskVsFair

| Field | Meaning |
|-------|---------|
| `ask` | Listing price |
| `fair` | Computed fair value (or null) |
| `delta_label` | e.g. `Ask 2,400 · Fair ~2,100` — never a “recommended buy” invention |

### DiscoveryPresentation

| Field | Meaning |
|-------|---------|
| `body` | Multi-line embed-safe text from RPC payload |
| `trend_label` | Human `Rising` / `Softening` / `Steady` (from `up`/`down`/`flat`) |
| `recent_sales_line` | Up to 3 prices from `recent_sales` when present |
| `insufficient` | Boolean — show need/have copy, no averages |

### MarketplaceCopyTokens

| Token | Example |
|-------|---------|
| `PRODUCT_NAME` | `Marketplace` |
| `BACK_TO_MARKET` | `Back to Market` |
| `SUB_TRANSFER_BOARD` | `Transfer Board` |
| Ownership error variants | Single shared message |

---

## 3. In-memory board session

After Apply Filters (or initial results load):

```text
TransferBoardResultsView.listings: list[row]  # already filtered+sorted bound set
sort_mode: str
# Select / Sort change → reorder or pick from listings (no DB)
# Buy success / Cancel listing / Apply Filters → refresh via _board_listings
```

---

## 4. Validation rules

1. Time-left MUST derive from real `expires_at` (or omit if null).  
2. Discovery presentation MUST NOT invent sales or trends.  
3. Ask-vs-fair MUST use existing fair-value helper — omit fair segment if calculation unavailable.  
4. No new persistence for “recently viewed” or favorite filters in this feature.
)
