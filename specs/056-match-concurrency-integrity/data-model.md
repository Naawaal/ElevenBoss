# Data Model & Schema Specifications: Match Concurrency & Squad Locking Integrity

**Feature**: [`spec.md`](file:///d:/Python/Discord%20Bots/ElevenBoss/specs/056-match-concurrency-integrity/spec.md) | [`plan.md`](file:///d:/Python/Discord%20Bots/ElevenBoss/specs/056-match-concurrency-integrity/plan.md)

---

## 1. Table Alterations & Constraints

### `public.match_locks`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `discord_id` | `BIGINT` | `PRIMARY KEY` / `UNIQUE` | Discord user ID of locked manager |
| `lock_type` | `TEXT` | `NOT NULL` | Mode: `friendly`, `bot`, `ranked`, `league` |
| `run_id` | `UUID` | `REFERENCES match_runs(id) ON DELETE CASCADE` | Linked active match run ID |
| `acquired_at` | `TIMESTAMPTZ` | `DEFAULT NOW()` | Timestamp when lock was acquired |

---

## 2. Stored Procedures (RPCs)

### `public.assert_manager_match_available(p_discord_id BIGINT) -> JSONB`
- **Purpose**: Queries `match_locks` for `p_discord_id`.
- **Returns**:
  ```json
  {"available": true}
  ```
  or
  ```json
  {
    "available": false,
    "lock_type": "friendly",
    "run_id": "48689ddf-a525-4eb3-b7b4-911b3e52d98c",
    "message": "manager_in_active_match"
  }
  ```

---

### `public.start_friendly_match(...) -> JSONB`
- **Inputs**:
  - `p_challenge_id UUID`
  - `p_home_id BIGINT`
  - `p_away_id BIGINT`
  - `p_squad_snapshot JSONB`
- **Logic**:
  1. Lock challenge record (`SELECT FOR UPDATE`).
  2. Canonical sort: `v_first := LEAST(p_home_id, p_away_id)`, `v_second := GREATEST(p_home_id, p_away_id)`.
  3. Verify neither `p_home_id` nor `p_away_id` exists in `match_locks`.
  4. Create `match_runs` row with `run_type = 'friendly'` and `squad_snapshot = p_squad_snapshot`.
  5. Insert two `match_locks` rows for `p_home_id` and `p_away_id` linked to the `run_id`.
  6. Return `{"success": true, "run_id": "..."}`.

---

### `public.start_single_manager_match(...) -> JSONB`
- **Inputs**:
  - `p_discord_id BIGINT`
  - `p_run_type TEXT` (`bot` or `ai_practice`)
  - `p_squad_snapshot JSONB`
- **Logic**:
  1. Verify `p_discord_id` is not in `match_locks`.
  2. Create `match_runs` row.
  3. Insert one `match_locks` row for `p_discord_id` linked to `run_id`.
  4. Return `{"success": true, "run_id": "..."}`.

---

## 3. Snapshot Data Model (`match_runs.squad_snapshot`)

```json
{
  "version": 1,
  "home_name": "FC Red Star",
  "away_name": "Blue Tigers",
  "home_formation": "4-3-3",
  "away_formation": "4-4-2",
  "home_tactics": {"mentality": "Attacking"},
  "away_tactics": {"mentality": "Balanced"},
  "home_squad": [
    {
      "id": "card-uuid-1",
      "name": "Jordan Foster",
      "position": "MID",
      "overall": 82,
      "pac": 75, "sho": 80, "pas": 85, "dri": 82, "def": 65, "phy": 70,
      "fatigue": 100
    }
  ],
  "away_squad": []
}
```
