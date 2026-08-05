# RPC Contracts: Feature 054 — Instant PvP Backfill and Ghost Managers

**Branch**: `054-instant-pvp-backfill` | **Date**: 2026-08-05

## Database RPC Functions

### 1. `refresh_pvp_ghost_snapshot`

Captures and stores/updates a manager's frozen squad snapshot for ghost backfill selection.

#### Signature
```sql
FUNCTION public.refresh_pvp_ghost_snapshot(
    p_owner_id BIGINT,
    p_source_run_id UUID DEFAULT NULL
) RETURNS JSONB
```

#### Inputs
- `p_owner_id`: Discord ID of the manager whose snapshot to refresh.
- `p_source_run_id`: Optional UUID of the completed match run triggering the refresh.

#### Output
```json
{
  "success": true,
  "owner_id": 123456789012345678,
  "club_name": "Kathmandu Kings",
  "xi_rating": 82.40,
  "captured_at": "2026-08-05T09:00:00Z"
}
```

#### Behavior & Errors
- Calls `build_pvp_squad_snapshot(p_owner_id)`. If squad does not have exactly 11 valid cards, marks `eligible = false` (or raises exception if explicit refresh).
- Reads player's current `club_name`, `global_lp`, division rank, and tactics.
- Upserts row into `pvp_ghost_snapshots` with `eligible = true`.

---

### 2. `try_match_pvp_queue` (Extended)

Attempts to pair queued searchers. Checks live human search first; if searcher is past `backfill_after`, evaluates ghost snapshot candidates or creates calibrated Ranked AI backfill.

#### Signature
```sql
FUNCTION public.try_match_pvp_queue(
    p_guild_id BIGINT DEFAULT NULL
) RETURNS JSONB
```

#### Output (Live Match)
```json
{
  "matched": true,
  "run_id": "a1b2c3d4-e5f6-7890-1234-56789abcdef0",
  "home_discord_id": 111,
  "away_discord_id": 222,
  "opponent_mode": "live"
}
```

#### Output (Ghost Match)
```json
{
  "matched": true,
  "run_id": "b2c3d4e5-f6a7-8901-2345-6789abcdef01",
  "home_discord_id": 111,
  "away_discord_id": 333,
  "opponent_mode": "ghost",
  "ghost_snapshot_age_seconds": 32400
}
```

#### Output (Ranked AI Backfill Match)
```json
{
  "matched": true,
  "run_id": "c3d4e5f6-a7b8-9012-3456-789abcdef012",
  "home_discord_id": 111,
  "away_discord_id": null,
  "opponent_mode": "ai_backfill"
}
```

---

### 3. `finalize_pvp_match` (Extended)

Finalizes a completed PvP match based on its `opponent_mode`.

#### Signature
```sql
FUNCTION public.finalize_pvp_match(
    p_run_id UUID,
    p_home_score INTEGER,
    p_away_score INTEGER,
    p_home_stats JSONB,
    p_away_stats JSONB,
    p_events JSONB
) RETURNS JSONB
```

#### Behavior by Mode
- **`live`**:
  - Validates energy for both home and away managers.
  - Applies 1.00x reward multipliers (coins, XP, LP).
  - Inserts 2 history rows (one per manager).
  - Updates bilateral `manager_rivalries`.
- **`ghost` / `ai_backfill`**:
  - Validates energy for home challenger only.
  - Applies mode-specific multipliers (Ghost: 0.85x coins, 0.90x XP, 0.75x pos LP, 0.50x neg LP; AI: 0.70x coins, 0.75x XP, 0.50x pos LP, 0.25x neg LP).
  - Deducts energy, grants XP/coins/LP to challenger ONLY.
  - Inserts 1 history row for challenger ONLY (with `opponent_mode` and `opponent_snapshot_age_seconds`).
  - Records encounter in `pvp_ghost_encounters`.
  - Performs NO MUTATIONS on ghost owner state or `manager_rivalries`.
