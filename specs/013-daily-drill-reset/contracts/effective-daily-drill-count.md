# Contract: effective daily drill count (pure)

**Package**: `packages/player_engine/player_engine/drill_caps.py` (new)

```python
CLUB_DAILY_DRILL_LIMIT = 20

def effective_daily_drill_count(
    count: int,
    reset_at: date | None,
    *,
    today: date,
) -> int:
    """Mirror RPC soft-reset for hub display."""
    if reset_at is None or reset_at < today:
        return 0
    return max(0, int(count))
```

## Call site

`apps/discord_bot/cogs/development_cog.py` → `show_training_menu`:

- Select `daily_drill_count, daily_drill_reset_at, training_ground_level`
- `today = datetime.now(timezone.utc).date()`
- Embed uses `effective_daily_drill_count(...)` for `Daily Drills: used/20`

## Tests

- reset yesterday, count 20 → effective 0  
- reset today, count 6 → 6  
- reset None, count 20 → 0  
