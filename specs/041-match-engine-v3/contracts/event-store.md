# Contract: Event Store & Database Design

**Feature**: `041-match-engine-v3`  
**Deliverable**: 5

---

## Recommendation (locked)

**Append-only `public.match_events`** for bot + league. See research R2.

---

## Clarifications (Session 2026-07-22) — Phase 0 flush policy

- Flush on **possession boundaries** (when Possession ends / owner changes), plus forced flushes at HALF_TIME, FULL_TIME, injury-await, and `mark_completing`.
- Do **not** flush every micro-event on the live path.
- `simulation_schema_version` is also pinned on `match_runs` (gameplay semantics); see migration `083_match_engine_v3_events.sql`.
- Friendly: still no `match_events` by default.

---

## Schema (forward migration `083_match_engine_v3_events.sql`)

### `match_runs` columns (add if missing)

```text
engine_version TEXT NOT NULL DEFAULT 'nss_v2'   -- app sets explicitly on create
simulation_schema_version INT NOT NULL DEFAULT 1
event_schema_version INT NOT NULL DEFAULT 1
events_flushed_thru INT NOT NULL DEFAULT 0     -- last seq durable
```


### `match_events`

```text
id              UUID PK DEFAULT gen_random_uuid()
run_id          UUID NOT NULL REFERENCES match_runs(id) ON DELETE CASCADE
seq             INT NOT NULL CHECK (seq > 0)
schema_version  INT NOT NULL DEFAULT 1
engine_version  TEXT NOT NULL
minute          INT NOT NULL CHECK (minute >= 0 AND minute <= 120)
event_type      TEXT NOT NULL
side            TEXT NULL CHECK (side IN ('home','away','neutral'))
payload         JSONB NOT NULL DEFAULT '{}'
causal_hint     TEXT NULL
created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()

UNIQUE (run_id, seq)
```

### Indexes

- `UNIQUE (run_id, seq)` — primary access path
- `(run_id, event_type)` — analytics
- `(created_at)` — retention jobs optional

### RLS

Follow `030`/`031` pattern: ENABLE RLS; policies for `anon, authenticated, service_role` SELECT/INSERT as required by bot Data API. No UPDATE/DELETE policies for normal roles (append-only). Retention deletes via service_role job or SQL function.

### Constraints / concurrency

- Seq allocated in app engine; flush in transaction on **possession end** (plus forced HT/FT/injury await/`mark_completing`): insert batch WHERE seq > events_flushed_thru; update `events_flushed_thru`.
- Optional RPC `append_match_events(p_run_id, p_events jsonb)` for atomic batch + thru update.
- Never UPDATE payload of existing seq.
- Do **not** flush every individual micro-event on the live path (round-trip amplification).

### Friendly policy

Do not write `match_events` by default. Keep `friendly_match_logs`.

---

## Rollback strategy

1. Feature flag off → new runs `nss_v2`, no event writes required.
2. Migration rollback: **do not drop** `match_events` if any v3 runs exist in prod; instead stop writing. Forward-fix only per AGENTS.md.
3. If column defaults break old clients: keep defaults compatible (`nss_v2`).

---

## Retention

| run_type | Events retention (initial) |
|----------|----------------------------|
| league | 180 days or season+1 |
| bot | 90 days |
| friendly | none (table) |

Retention sweeper is ops follow-up (not Phase 0 blocker); document in tasks as optional.

### Optional retention sweeper (T079 — design only, YAGNI code)

When ops requests it, a scheduled job can:

1. `DELETE FROM match_events WHERE created_at < now() - interval '90 days'` for `run_type=bot` runs (join `match_runs`).
2. League: keep through season end + 180 days; delete after standings freeze.
3. Never delete events for `status IN ('streaming','completing')`.
4. Prefer a SQL function + pg_cron / Render cron calling service_role — not bot process loops.

Until then: table growth is acceptable at current scale; flags-off means few v3 rows.

---

## WAL / storage estimate

200 events × 300 B ≈ 60 KB/match. 10k matches/day ≈ 600 MB/day raw worst case before TOAST/compression — unlikely at current scale; still batch inserts (50–100 rows) to cut round trips.

---

## Verify guards

Extend `verify_required_schema.sql`:

- `table:public.match_events`
- `column:public.match_runs.engine_version`
- `column:public.match_runs.event_schema_version`
- `column:public.match_runs.events_flushed_thru`
- `policy:public.match_events.*` as added
