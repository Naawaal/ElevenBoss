# Implementation Plan: Hub Hot-Path Wave 3

**Branch**: `040-hub-hot-path-wave3` | **Spec**: [spec.md](./spec.md) | **US-45**

## Summary

Apply US-43/44 patterns to marketplace + leaderboard: `asyncio.gather`, `division_cache`, `hub_timer`, fix `/leaderboard` defer. No migrations.

## Files

```text
specs/040-hub-hot-path-wave3/{spec,plan,tasks,quickstart,contracts/hot-path-wave3}.md
apps/discord_bot/cogs/marketplace_cog.py
apps/discord_bot/views/marketplace_transfer.py   # _eligible_listing_cards gather
apps/discord_bot/cogs/leaderboard_cog.py
tests/test_hub_hot_path_wave3.py
```

## Constitution

PASS — apps only; Principle II; YAGNI; no new surface.
