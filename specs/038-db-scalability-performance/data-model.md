# Data Model: Database Scalability & Performance (US-43)

**Feature**: `038-db-scalability-performance` | **Date**: 2026-07-22

This model describes **scalability concepts and additive schema**. It does **not** invent parallel economy/XP tables. Physical changes are forward migrations **080+** only when Phase gates require them.

---

## 1. Conceptual entities (from spec)

| Entity | Meaning | Persistence |
|--------|---------|-------------|
| **Logical Action** | Manager/system intent with idempotency key | Key stored in existing ledgers / action-specific tables |
| **Idempotent Outcome** | `applied` \| `already_applied` + payload | Returned by RPC JSON; not a table |
| **Command Data Load** | Reads for one interaction | Ephemeral; may be one dashboard RPC |
| **Cache Policy / Cache Entry** | Key, TTL, layer, invalidation | Process memory (P1); shared store (P3) |
| **Phase Gate** | Metric threshold | Documented in plan/spec |
| **Job Ownership Record** | Single-owner claim for a due job | New or extended table (P3) |
| **Hot Path Catalog** | Named hubs + baselines | Spec contract doc |
| **Perf Signal Sample** | Latency / round-trips | In-process ring buffer / logs (P1) |

---

## 2. Existing tables reused

| Table | Role in US-43 |
|-------|----------------|
| `game_config` | Cached reference / economy tunables |
| `economy_ledger` | Idempotency via `idempotency_key` (unique partial); candidate index on `(club_id, created_at)` |
| `players` / `player_cards` / `squad_*` | Hub dashboard payloads |
| `league_fixtures` / `league_seasons` / `league_members` | League hub; index candidates |
| `league_operation_runs` | Pattern for job ownership (unique `operation_key`) |
| `match_locks` | Unchanged concurrency gate |

---

## 3. Additive schema (phased)

### 3.1 Phase 1 — Indexes only (typical)

No new tables required for cache (process-local).

**Candidate indexes** (confirm with EXPLAIN before ship):

```text
-- illustrative names; final DDL in migration 080
idx_league_fixtures_season_matchday ON league_fixtures (season_id, matchday)
idx_league_fixtures_season_unplayed ON league_fixtures (season_id) WHERE is_played = false
idx_economy_ledger_club_created ON economy_ledger (club_id, created_at DESC)
```

### 3.2 Phase 1 optional — batch config RPC

No table. Function `get_game_config_many(p_keys text[])` → `jsonb` object of key → value.

### 3.3 Phase 1 optional — hub dashboard RPCs

Functions e.g. `get_development_hub_bundle(p_discord_id bigint)` / `get_training_menu_bundle(...)` returning `jsonb`. Read-only assembly; must still call `sync_action_energy` semantics if energy displayed (or document freshness).

### 3.4 Phase 2 — Pack claim idempotency

Extend `claim_daily_pack` (or successor) with `p_idempotency_key text`. Persist key via ledger row and/or dedicated claim log unique constraint. Return FR-006a envelope.

### 3.5 Phase 3 — Job claims

Either:

**Option A (preferred reuse):** Insert into `league_operation_runs`-like table with `operation_key = 'job:{name}:{window}'` for **all** schedulers, or

**Option B:** New `job_claims`:

| Column | Type | Rules |
|--------|------|-------|
| `operation_key` | text PK/unique | e.g. `daily_recovery:2026-07-22` |
| `owner_instance_id` | text | bot hostname/pid token |
| `claimed_at` | timestamptz | |
| `finished_at` | timestamptz null | |
| `status` | text | `running` \| `succeeded` \| `failed` |

Claim = `INSERT … ON CONFLICT DO NOTHING` / unique violation → skip.

---

## 4. Idempotency key patterns (extend US-42 map)

| Logical action | Key pattern | Phase | Envelope |
|----------------|-------------|-------|----------|
| Economy mutation | existing `p_idempotency_key` | Done | Map `replay` → `already_applied` (adapter P1) |
| Match coins | `match:{run_id}:{club_id}` | Done | Adapter |
| Transfer buy/sale | `transfer_buy:{listing_id}` etc. | Done | Adapter |
| Daily pack / vote pack | `daily_pack:{club_id}:{utc_date}` or interaction id | **P2 gap** | FR-006a native |
| Interactive hub mutation (new) | Prefer Discord `interaction.id` when stable + domain suffix | As touched | FR-006a |
| Scheduled job | `job:{name}:{window}` | **P3** | Job claim row |

---

## 5. Cache entry shape (application)

| Field | Description |
|-------|-------------|
| `key` | See [cache-policy-and-keys.md](./contracts/cache-policy-and-keys.md) |
| `value` | Parsed config scalar/JSON |
| `expires_at` | monotonic or wall clock |
| `layer` | `process` \| `shared` (P3) |

**Invalidation**: explicit `invalidate(key|prefix)` on config write paths; TTL as backstop.

---

## 6. State transitions

### Idempotent mutation

```text
[request + key]
    → first commit → status=applied + payload
    → replay same key → status=already_applied + prior payload
    → conflicting different intent → failure reason family (not raw SQL)
```

### Job claim (P3)

```text
due → try claim → running → succeeded | failed
duplicate claim attempt → no-op (skip)
```

---

## 7. Validation rules

- Economy-priced cache keys MUST NOT be process-local-only under multi-instance (FR-012).
- Dashboard RPCs MUST NOT bypass `assert_card_action_allowed` / match locks when returning actionable UI that implies mutation eligibility — eligibility may be hint-only if documented.
- Indexes MUST appear in `verify_required_schema.sql` only if bot/RPC correctness depends on them (prefer documenting performance indexes in migration comments; guard functions always).
