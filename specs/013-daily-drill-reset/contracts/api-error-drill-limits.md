# Contract: api_error drill limit mapping

**File**: `apps/discord_bot/core/api_errors.py`

## Bug

Substring match hits `"Daily drill limit reached"` inside  
`"Daily drill limit reached for this player (max 5 per day)"` → wrong club toast.

## Required behavior

| Raw exception contains | Friendly copy |
|------------------------|---------------|
| `Daily drill limit reached for this player` | Per-card (5) message |
| `Daily drill limit reached` (exact club raise) | Club (20) message |

Implementation: match **longest** key first among keys that are substrings of `raw`, or explicitly test per-card before club.

## Tests (`tests/test_api_errors.py`)

```python
assert "per-card" in api_error_message(
    RuntimeError("Daily drill limit reached for this player (max 5 per day)")
).lower() or "5" in ...
assert "club" in api_error_message(
    RuntimeError("Daily drill limit reached")
).lower() or "20" in ...
```
