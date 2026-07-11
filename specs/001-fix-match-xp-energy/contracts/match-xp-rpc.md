# Contract: Match XP RPC path

## Callers

| Match type | Entry | Invokes XP? |
|------------|-------|-------------|
| bot | `apply_bot_match_rewards` | Yes — `match_type="bot"` |
| league (human) | `apply_league_human_rewards` | Yes — `match_type="league"` |
| friendly | friendly completion path | No |

## `build_process_match_result_rpc` → `process_match_result`

**Input (bot-built kwargs)**:

| Field | Type | Notes |
|-------|------|-------|
| `p_result` | text | `win` / `draw` / `loss` |
| `p_card_ids` | uuid[] | Starting XI |
| `p_xp_amounts` | int[] | Per-card from `match_xp_reward` |
| `p_card_ratings` | float[] | Team rating per card |
| `p_match_history_id` | uuid | Idempotency / audit link |
| `p_xp_amount` | int | Legacy single amount (first card); still sent |

**Card dict minimum for builder**:

- `id` (required)
- `name` (required)
- age/DOB fields as used by `effective_card_age` (recommended)

**Success**:
- Per-card `apply_card_xp(..., source related to match_simulation)`
- Caller sets `match_history.xp_applied_at`

**Hard failure**:
- RPC/permission errors propagate; `xp_applied_at` MUST NOT be set
- Manager-visible error (FR-004)

**Soft zero (not failure)**:
- Daily cap or max level → `xp_added = 0` for that card; overall RPC succeeds

## `apply_card_xp`

| Constraint | Requirement |
|------------|-------------|
| Privileges | MUST be `SECURITY DEFINER` with `search_path = public` (migration 048) |
| Match daily cap | 100 XP/card/day for match simulation source |
| Schema verify | MUST assert `prosecdef` not only function existence |
