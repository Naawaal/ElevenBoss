# Contract: Discovery Presentation

**Feature**: `045-marketplace-ux-polish`  
**Source**: Existing `get_price_discovery` payload only

## Rendering rules

| Payload condition | UI |
|-------------------|----|
| Empty / RPC fail | Soft unavailable copy (existing tone) |
| `insufficient_data` | Need/have + active listings line; **no** avg/median/trend invention |
| Sufficient | Avg + median + n; active count/range; **human trend**; **recent sales** when array present |

## Trend mapping

| RPC `trend` | Manager label (example) |
|-------------|-------------------------|
| `up` | Rising |
| `down` | Softening |
| `flat` | Steady |
| null/missing | Omit trend line |

## Recent sales

- Show up to **3** recent prices from `recent_sales` (coins only; no fabricated opponents).  
- If key absent or empty, omit the line.

## Where shown

- Listing detail (full)  
- List-player confirm (full or same helper)  
- Buy confirm (compact: may omit recent sales if length tight, but keep fair/avg or fair cue)

## Forbidden

- Calling `get_market_analytics` from marketplace hub or board  
- Inventing recommended list prices  
)
