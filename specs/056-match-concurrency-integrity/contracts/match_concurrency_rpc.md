# Contract: Match Concurrency & Squad Locking RPC Interfaces

**Feature**: [`spec.md`](file:///d:/Python/Discord%20Bots/ElevenBoss/specs/056-match-concurrency-integrity/spec.md) | [`plan.md`](file:///d:/Python/Discord%20Bots/ElevenBoss/specs/056-match-concurrency-integrity/plan.md)

---

## 1. `assert_manager_match_available`

### Request
```sql
SELECT public.assert_manager_match_available(976054227459776582);
```

### Response (Available)
```json
{
  "available": true
}
```

### Response (Locked)
```json
{
  "available": false,
  "lock_type": "friendly",
  "run_id": "48689ddf-a525-4eb3-b7b4-911b3e52d98c",
  "message": "manager_in_active_match"
}
```

---

## 2. `start_friendly_match`

### Request
```sql
SELECT public.start_friendly_match(
  'challenge-uuid',
  976054227459776582,
  123456789012345678,
  '{"version": 1, "home_squad": [...], "away_squad": [...]}'::jsonb
);
```

### Response (Success)
```json
{
  "status": "success",
  "run_id": "8b9f1234-5678-4abc-def0-123456789abc"
}
```

### Response (Error - Conflict)
```json
{
  "status": "error",
  "error_code": "MANAGER_LOCKED",
  "message": "One or both managers are currently in an active match."
}
```

---

## 3. `set_formation_and_assignments` / `swap_squad_players` SQL Exception

### Trigger Condition
`p_discord_id` exists in `public.match_locks`.

### SQL Exception Raised
```text
SQLSTATE: P0001
Message: manager_in_active_match
```
