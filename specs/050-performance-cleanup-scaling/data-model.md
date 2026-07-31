# Data Model: Performance, Cleanup & Scalability Hardening

**Feature**: `050-performance-cleanup-scaling` | **Date**: 2026-07-31  
**Parent**: [plan.md](./plan.md) | [spec.md](./spec.md)

This epic mostly adds **read RPC envelopes** and **operator/cache/job metadata**. Gameplay tables (`players`, `player_cards`, `transfer_listings`, etc.) remain sources of truth; no parallel economy/XP stores.

---

## 1. Existing entities (consumed, not redesigned)

| Entity | Role in this epic |
|--------|-------------------|
| `players` | Division/global leaderboard ordering; hub coins/tokens/name |
| `player_cards` | Sell eligibility, skills roster, market card attrs |
| `transfer_listings` | Browse filter/sort/page; active count for hub |
| `squad_assignments` / `active_evolutions` / `active_training` | Sell + skills eligibility joins |
| `game_config` | Batched config; V3 / league flags (tunables vs temporary flags) |
| `league_operation_runs` | Job claim windows (`job_claims.py`) |
| `league_outbox` | Durable league publish queue |
| `match_runs` | Engine version `nss_v2` / `nss_v3` for soak/drain gates |

---

## 2. Logical envelopes (RPC / cache / metrics)

### 2.1 LeaderboardPage

| Field | Meaning |
|-------|---------|
| `rows[]` | `{ discord_id, club_name, points_or_lp, tie_break, rank }` — page sized |
| `viewer_rank` | 1-based rank among eligible managers (or null if N/A) |
| `viewer_points` | Viewer LP / league points |
| `total_count` | Eligible managers in scope |
| `promotion_cutoff` / `relegation_cutoff` | Division only; null on global |
| `next_cursor` / `prev_cursor` | Opaque keyset cursors (see cursor contract) |

**Invariant**: `len(rows) <= page_size`. Never return full division population for UI pagination.

### 2.2 MarketBrowsePage

| Field | Meaning |
|-------|---------|
| `listings[]` | Display rows (listing + card summary fields needed by board UI) |
| `next_cursor` | Keyset for sort mode |
| `applied_filters` | Echo of server-applied filters (debug/UX optional) |

**Invariant**: All returned rows satisfy filters; page sized; no post-filter in Python required for correctness.

### 2.3 MarketSellEligible / MarketplaceHubState / DevelopmentHubState

| Envelope | Contents (display) |
|----------|--------------------|
| Sell eligible | Cards allowed to list + optional reason codes for ineligible (if UI needs) |
| Marketplace hub | Club name, coins, tokens, transfer_enabled, active_listing_count, listing_cap |
| Development hub | Energy snapshot fields, pending reward count, legendary-pending **flags only** (no create) |

**Invariant**: Hub-state RPCs are read-only; mutations (claim, ensure legendary, list/buy) stay separate RPCs.

### 2.4 SkillAllocationHub / MentorTargets

| Envelope | Contents |
|----------|----------|
| Skills hub | Roster summary rows + selected card full attrs needed for allocate UI |
| Mentor targets | Eligible youth/targets without second market-listing round-trip in Python |

### 2.5 CacheEntry (process-local / future L2)

| Field | Meaning |
|-------|---------|
| `key` | Namespaced string (`cfg:`, `guild:`, `standings:`, `lb:first:`, `player:profile:`) |
| `value` | JSON-serializable payload |
| `expires_at` | Absolute expiry |
| `inflight` | Single-flight future handle (memory backend) |

**Invariant**: Cache never authorizes spends/ownership/locks.

### 2.6 PerfBucket

| Field | Meaning |
|-------|---------|
| `command_or_hub` | Stable name |
| `window_start` | 1-minute bucket |
| `count`, `errors`, `retries`, `round_trips_sum` | Counters |
| `latency_samples` or running percentile sketch | Enough for p50/p95/p99 |
| `cache_hits` / `cache_misses` | When applicable |
| `status_429` / `status_5xx` | Upstream classes |
| `instance_id` | Bot process identity |

**Invariant**: Persist aggregates only (flush), not one DB row per command.

### 2.7 DurableJob (generalized claim)

| Field | Meaning |
|-------|---------|
| `job_type` | Stable name |
| `payload` | JSON |
| `idempotency_key` | Unique per logical unit of work |
| `status` | pending / claimed / completed / failed |
| `attempt_count`, `available_at`, `claimed_by`, `claimed_at`, `completed_at`, `last_error` | Lifecycle |

Reuse `league_operation_runs` / outbox patterns where possible before inventing a second queue table.

---

## 3. Validation rules

1. Leaderboard/market page size must match UI contract (division 10, board 25 unless UX changes — plan must not silently change UX page size).
2. Cursors must decode to the sort keyset; invalid cursor → empty/error message, not OFFSET fallback.
3. Development hub read RPC must not insert pending legendary / claim rewards.
4. Feature flags in `game_config` remain rows; env kill switches removed only after maturation checklist.

---

## 4. State transitions

### Job claim

```text
pending → claimed → completed
              ↘ failed (retry if available_at set)
```

### Match engine rollout (Phase 5)

```text
V2 default → V3 flags=1 soak → V3 default → no new V2 → V2 drain → V2 code removed
```

### Cache

```text
miss → single-flight refresh → set(TTL) → hit → expire → miss
invalidate on known writers (admin config, settle, etc.)
```

---

## 5. Schema change expectation

| Phase | Likely DDL |
|-------|------------|
| 1 | None (app/deps only) or tiny metrics table if flush-to-DB chosen later — prefer logs first |
| 2 | New RPCs + grants + verify guards; indexes deferred to measured migrations |
| 3 | None required for memory cache |
| 4 | CREATE INDEX … (proven only) |
| 6 | Optional outbox columns/indexes if generalization needs them |

RLS: any new exposed table follows AGENTS §8 (ENABLE + policies same migration). New RPCs called via service/anon paths must match existing security model (SECURITY DEFINER patterns consistent with peers).
