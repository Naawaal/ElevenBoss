# Quickstart: Top.gg Vote Gate for Free Store Pack

**Feature**: `025-topgg-vote-pack`

## Prerequisites

- Migration `069_topgg_vote_pack.sql` applied
- `TOPGG_TOKEN` set on bot service (Top.gg → bot listing → Integrations & API)
- Bot listed on Top.gg with correct Discord application ID
- `verify_required_schema.sql` passes

## 1. Apply migration (local)

```bash
python scratch/apply_migration_069.py
python scratch/verify_schema_full.py
```

## 2. Unit tests

```bash
pytest tests/test_topgg_vote.py -q
```

Expect: voted / not_voted / unavailable paths; no token → unavailable.

## 3. Manual — happy path

1. Ensure pack cooldown elapsed (or test account never claimed).
2. `/store` → confirm copy mentions Top.gg vote; button **Vote & Claim Free Pack** enabled.
3. Click without voting → vote prompt embed with `https://top.gg/bot/{id}/vote`.
4. Vote on Top.gg (website).
5. Return to Discord → click again → 5-card pack embed.
6. `/store` → button disabled; cooldown timer shown (~12h).

## 4. Manual — replay prevention

1. After successful claim, if still within Top.gg vote window, attempt claim again after manipulating cooldown in DB **only in dev** — expect `VOTE_ALREADY_USED` or cooldown, never second pack from same vote.

## 5. Manual — API fail closed

1. Temporarily set invalid `TOPGG_TOKEN` on dev bot.
2. Click pack button → "verification unavailable" embed; no pack granted.

## 6. Ops bypass (emergency only)

```sql
UPDATE game_config SET value_json = '1' WHERE key = 'topgg_vote_bypass_enabled';
```

Restart bot if config is cached. Revert to `0` after Top.gg recovery.

## Rollback

- Set bypass `1` for immediate relief.
- Forward migration to restore 22h cooldown / remove vote param if full revert needed.
- Bot revert alone leaves RPC signature mismatch — coordinate DB + bot deploy.
