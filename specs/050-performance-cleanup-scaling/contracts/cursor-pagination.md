# Contract: Cursor / Keyset Pagination

**Parent**: [../spec.md](../spec.md) | **Plan**: [../plan.md](../plan.md)

## Rule

Growing list surfaces MUST NOT use `OFFSET` for primary pagination. Use compound keyset cursors matching the sort.

## Sort → cursor

| Surface | Order | Cursor tuple |
|---------|-------|--------------|
| Division leaderboard | `league_points DESC, goal_difference DESC, discord_id ASC` | `(lp, gd, discord_id)` + direction |
| Global leaderboard | `global_lp DESC, discord_id ASC` | `(global_lp, discord_id)` |
| Market newest | `created_at DESC, id DESC` | `(created_at, id)` |
| Market price | `price_coins ASC/DESC, id` | `(price_coins, id)` |
| Match history | `completed_at DESC, id DESC` | `(completed_at, id)` |
| Transfer sales / admin history | match their UI sort | compound id included |

## Encoding

- Opaque string safe for Discord custom_id / button state (base64url JSON or similar)
- Invalid/expired cursor → empty page or clear ephemeral error — **no silent OFFSET fallback**
- Page size fixed to current UX (division **10**, board **25**) unless a separate UX spec changes it

## RPC shape (illustrative)

```text
get_*_page(..., cursor text, page_size int)
  → { rows, next_cursor, prev_cursor?, viewer_*, totals? }
```

## Prohibited

- Fetching N≫page_size then slicing in Python for correctness
- Transfer Board “first 50 then filter” as the browse implementation
