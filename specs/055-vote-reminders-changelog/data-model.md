# Data Model: Vote Reminders and Deployment Changelog

## 1. Database Schema

### `public.topgg_vote_reminders`

```sql
CREATE TABLE IF NOT EXISTS public.topgg_vote_reminders (
    discord_user_id       BIGINT PRIMARY KEY,

    last_vote_at          TIMESTAMPTZ NOT NULL,
    next_vote_at          TIMESTAMPTZ NOT NULL,

    reminder_window_key   TEXT NOT NULL,
    reminder_claimed_at   TIMESTAMPTZ,
    reminder_sent_at      TIMESTAMPTZ,

    dm_status              TEXT,
    fallback_pending       BOOLEAN NOT NULL DEFAULT FALSE,
    fallback_created_at    TIMESTAMPTZ,
    fallback_shown_at      TIMESTAMPTZ,

    last_checked_at        TIMESTAMPTZ,
    next_check_at          TIMESTAMPTZ,
    check_failure_count    INTEGER NOT NULL DEFAULT 0,

    created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT ck_topgg_reminder_dm_status
        CHECK (
            dm_status IS NULL OR
            dm_status IN ('sent', 'forbidden', 'failed')
        )
);

-- Index for due reminder queries
CREATE INDEX IF NOT EXISTS idx_topgg_vote_reminders_due
ON public.topgg_vote_reminders (next_check_at)
WHERE reminder_sent_at IS NULL;
```

---

## 2. Stored Procedures (RPCs)

### `public.claim_due_topgg_vote_reminders(p_limit INTEGER DEFAULT 100)`

```sql
CREATE OR REPLACE FUNCTION public.claim_due_topgg_vote_reminders(
    p_limit INTEGER DEFAULT 100
) RETURNS TABLE (
    discord_user_id     BIGINT,
    reminder_window_key TEXT,
    last_vote_at        TIMESTAMPTZ,
    next_vote_at        TIMESTAMPTZ,
    next_check_at       TIMESTAMPTZ,
    check_failure_count INTEGER
) LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
    RETURN QUERY
    WITH due_rows AS (
        SELECT r.discord_user_id
        FROM public.topgg_vote_reminders r
        WHERE r.reminder_sent_at IS NULL
          AND r.next_check_at <= NOW()
          AND (r.reminder_claimed_at IS NULL OR r.reminder_claimed_at < NOW() - INTERVAL '15 minutes')
        ORDER BY r.next_check_at ASC
        LIMIT LEAST(p_limit, 100)
        FOR UPDATE SKIP LOCKED
    )
    UPDATE public.topgg_vote_reminders r
    SET reminder_claimed_at = NOW(),
        updated_at = NOW()
    FROM due_rows d
    WHERE r.discord_user_id = d.discord_user_id
    RETURNING
        r.discord_user_id,
        r.reminder_window_key,
        r.last_vote_at,
        r.next_vote_at,
        r.next_check_at,
        r.check_failure_count;
END;
$$;
```

### `public.claim_deployment_changelog(p_deployment_key TEXT, p_instance_id TEXT DEFAULT 'default')`

```sql
CREATE OR REPLACE FUNCTION public.claim_deployment_changelog(
    p_deployment_key TEXT,
    p_instance_id TEXT DEFAULT 'default'
) RETURNS JSONB LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
    v_rec RECORD;
    v_curr_key TEXT;
    v_claimed_at TIMESTAMPTZ;
BEGIN
    SELECT value_json INTO v_rec FROM public.game_config WHERE key = 'last_changelog_deployment' FOR UPDATE;
    
    IF v_rec IS NOT NULL AND v_rec.value_json IS NOT NULL THEN
        v_curr_key := (v_rec.value_json #>> '{deployment_key}');
        v_claimed_at := (v_rec.value_json #>> '{claimed_at}')::TIMESTAMPTZ;
        
        IF v_curr_key = p_deployment_key AND (v_rec.value_json #>> '{posted_at}') IS NOT NULL THEN
            RETURN jsonb_build_object('status', 'already_posted', 'deployment_key', p_deployment_key);
        END IF;

        IF v_curr_key = p_deployment_key AND v_claimed_at IS NOT NULL AND v_claimed_at > NOW() - INTERVAL '10 minutes' THEN
            RETURN jsonb_build_object('status', 'already_claimed', 'deployment_key', p_deployment_key);
        END IF;
    END IF;

    -- Upsert claim
    INSERT INTO public.game_config (key, value_json)
    VALUES (
        'last_changelog_deployment',
        jsonb_build_object(
            'deployment_key', p_deployment_key,
            'claimed_at', NOW(),
            'instance_id', p_instance_id
        )
    )
    ON CONFLICT (key) DO UPDATE
    SET value_json = EXCLUDED.value_json;

    RETURN jsonb_build_object('status', 'claimed', 'deployment_key', p_deployment_key);
END;
$$;
```

### `public.complete_deployment_changelog(p_deployment_key TEXT, p_version TEXT, p_commit TEXT, p_channel_id BIGINT)`

```sql
CREATE OR REPLACE FUNCTION public.complete_deployment_changelog(
    p_deployment_key TEXT,
    p_version TEXT,
    p_commit TEXT,
    p_channel_id BIGINT
) RETURNS JSONB LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
    UPDATE public.game_config
    SET value_json = jsonb_build_object(
        'deployment_key', p_deployment_key,
        'version', p_version,
        'commit', p_commit,
        'posted_at', NOW(),
        'channel_id', p_channel_id
    )
    WHERE key = 'last_changelog_deployment';

    RETURN jsonb_build_object('status', 'completed', 'deployment_key', p_deployment_key);
END;
$$;
```

---

## 3. Python Data Models

### `apps/discord_bot/core/deployment_changelog.py`

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class ChangelogEntry:
    version: str
    date: str | None
    sections: dict[str, list[str]]  # e.g., {"Added": [...], "Fixed": [...]}
    raw_heading: str
```
