# Contract: Top.gg Vote Check (Bot Client)

**Feature**: `025-topgg-vote-pack`  
**Module**: `apps/discord_bot/core/topgg_vote.py`

## Environment

| Variable | Required | Description |
|----------|----------|-------------|
| `TOPGG_TOKEN` | Yes (production) | Bearer token from Top.gg Integrations & API |

Missing or empty token → return `VoteCheckResult(status="unavailable")`; log once at warning level.

## Primary endpoint (v1)

```http
GET https://top.gg/api/v1/projects/@me/votes/{discord_user_id}?source=discord
Authorization: Bearer {TOPGG_TOKEN}
Accept: application/json
```

### Response handling

| HTTP | Action |
|------|--------|
| 200 + body | Parse JSON; if `nextVoteAt` (or equivalent) > now → `voted` with `vote_at` from `votedAt` / `createdAt` |
| 404 | `not_voted` |
| 401 | Log auth failure → `unavailable` (do not retry with token in logs) |
| 429 | `unavailable` (optional single retry after 1s — YAGNI: no retry v1) |
| 5xx / timeout (8s) | `unavailable` |

### Active vote rule

User has an active vote when:

- v1: parsed `nextVoteAt > datetime.now(UTC)`, **or**
- v0 fallback (if implemented): response `{ "voted": 1 }`

Vote is **stale** when API returns 404 or `nextVoteAt <= now`.

## Fallback endpoint (v0, optional)

```http
GET https://top.gg/api/bots/{bot_id}/check?userId={discord_user_id}
Authorization: {TOPGG_TOKEN}
```

Use only if v1 returns 401 and ops confirms legacy token. Map `voted: 1` → `voted` with `vote_at = now()` (less precise; prefer v1 in production).

## Vote URL (player-facing)

```text
https://top.gg/bot/{discord_application_id}/vote
```

Source: `interaction.client.user.id` at runtime.

## Public API

```python
@dataclass(frozen=True)
class VoteCheckResult:
    status: Literal["voted", "not_voted", "unavailable"]
    vote_at: datetime | None = None
    next_vote_at: datetime | None = None

async def check_topgg_vote(
    *,
    discord_user_id: int,
    token: str,
    bot_id: int | None = None,
    timeout: float = 8.0,
) -> VoteCheckResult: ...
```

## Must not

- Import `discord`
- Log `TOPGG_TOKEN` or full Authorization header
- Cache vote results across requests (single check per button click only)
- Live under `packages/`

## Bypass integration

When `game_config.topgg_vote_bypass_enabled == 1`, **caller** (`store_cog`) skips this module and passes `datetime.now(UTC)` to RPC. This module is not invoked.
