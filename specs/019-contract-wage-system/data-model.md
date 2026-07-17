# Data Model: Contract & Wage System

**Feature**: `019-contract-wage-system` | **Date**: 2026-07-14  
**Migration**: `063_contract_wage_system.sql`

## Entities

### ClubPayrollState (`players` columns — new)

| Field | Type | Notes |
|-------|------|-------|
| `payroll_debt` | BIGINT NOT NULL DEFAULT 0 | Unpaid wage remainder (≥ 0) |
| `payroll_strikes` | INTEGER NOT NULL DEFAULT 0 | Consecutive / cumulative unpaid cycles; reset to 0 on clean pay |
| `last_payroll_at` | TIMESTAMPTZ NULL | Last successful payroll attempt (paid or partial) |
| `last_payroll_week` | TEXT NULL | ISO week key for ops/UI (optional denorm of last run) |

Existing: `coins`, `is_ai`, `squad_invalid`, `intensity_tier` — unchanged roles.

**Relationships**: One payroll state per club (`players.discord_id`).

### PayrollRun (`payroll_runs` — new)

Idempotency + audit for weekly job.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID PK | `gen_random_uuid()` |
| `club_id` | BIGINT FK → `players.discord_id` | |
| `week_key` | TEXT | e.g. `2026-W29` (UTC ISO week) |
| `bill_coins` | BIGINT | Wage bill before debt (XI derive × bill_scale) |
| `debt_before` | BIGINT | |
| `paid_coins` | BIGINT | Amount debited via economy pipe this run |
| `debt_after` | BIGINT | |
| `strikes_after` | INTEGER | |
| `status` | TEXT | `paid` \| `partial` \| `skipped_flag` \| `skipped_ai` \| `skipped_zero` |
| `created_at` | TIMESTAMPTZ | Default now() |

**Constraints**

- `UNIQUE (club_id, week_key)` — prevents double payroll on job retry.

**Indexes**

- `(week_key)`, `(club_id, created_at DESC)`

**RLS**: If bot reads via Data API, ENABLE RLS + SELECT for `anon/authenticated/service_role` (mirror `030`/`062` pattern). Prefer RPC-only access from bot for writes.

### PlayerContract (existing `player_cards`)

| Field | Role in 019 |
|-------|-------------|
| `contract_expires_at` | Expiry; renew extends; grace/gates use this |
| `overall` / `rarity` / age (DOB) / `potential` | Wage inputs (derive) |
| `morale` | **Do not mutate** on unpaid wages (D15 / YAGNI) |
| `in_academy` / `is_retired` | Excluded from XI wage scope naturally |

No new per-card wage column (D2).

### SquadAssignment (existing)

`squad_assignments` defines Starting XI — **sole wage scope** for v1 (D1).

### GameConfig keys (seed)

| Key | Default | Meaning |
|-----|---------|---------|
| `wages_payroll_enabled` | `false` | Master feature flag |
| `wages_payroll_bill_scale` | `1.0` | Multiplier on derived XI bill (soft launch) |
| `wage_scale_factor` | `1.2` | Mirror package `GameConfig.wage_scale_factor` if not already present |
| `wage_rarity_mult_common` … `_legendary` | `1.0` / `1.05` / `1.10` / `1.15` | Per-card multipliers |
| `wage_age_mult_enabled` | `false` | Keep age factor off until tuned |
| `wage_pot_mult_enabled` | `false` | Keep POT factor off until tuned |
| `contract_renewal_days` | `7` | Passed as `p_extension_days` from bot |
| `contract_grace_days` | `7` | Playable window after expiry |
| `payroll_strike_friendly_block` | `2` | Strikes ≥ N block friendlies |
| `payroll_strike_market_block` | `3` | Strikes ≥ N block new P2P list + scout buy |

Helper: `wages_payroll_enabled() RETURNS BOOLEAN` (mirror `p2p_transfer_market_enabled`).

### Economy ledger sources

| Source | Direction | Idempotency |
|--------|-----------|-------------|
| `weekly_payroll` | Club debit (−paid_coins) | `weekly_payroll:{club_id}:{week_key}` |
| `contract_renewal` | Existing | `contract_renewal:{card_id}` (unchanged) |

Debt is **not** a separate ledger row — tracked on `players.payroll_debt` and summarized in `payroll_runs`.

## State transitions

### Payroll (per club, per week)

```text
flag off / is_ai / bill=0+debt=0
        → payroll_runs status skipped_* (optional row OR no-op; prefer row for SC-001)

flag on, coins >= debt + bill
        → debit (debt+bill), debt=0, strikes=0, status=paid

flag on, coins < debt + bill
        → debit all coins toward debt first then wages
        → debt_after = remainder, strikes += 1, status=partial
```

### Contract playability

```text
now < expires_at                     → OK
expires_at ≤ now < expires_at+grace  → OK + warn (grace)
now ≥ expires_at+grace               → XI / match BLOCK until renew or replace
```

## Validation rules

1. Payroll only if `wages_payroll_enabled()`; else job no-ops (may insert skipped rows for ops — optional).
2. Never `UPDATE players.coins` outside `apply_club_economy`.
3. Wage bill = sum of derived card wages for current XI at run time × `wages_payroll_bill_scale`.
4. Renew: existing ownership/retired/age gates; extension days from config.
5. Match/squad: past-grace cards cannot be assigned to XI and cannot play (FR-007); message naming contract expiry.
6. Strike ≥ market threshold: **RPC** reject on `create_transfer_listing` / scout spend paths with debt reason; agent sale allowed. Bot pre-checks are UX only.

## Migration notes

- Add columns with defaults **0** / NULL — safe for existing clubs.
- Backfill: `UPDATE player_cards SET contract_expires_at = NOW() + INTERVAL '30 days' WHERE contract_expires_at IS NULL` (if any).
- Do **not** set flag true in migration seed.
- Extend schema guard lists for table/columns/functions/policies.
- DROP old `process_weekly_payroll` overloads if iterating signatures.

## Non-goals (schema)

- Per-card stored wage
- Multi-year contract tables
- Auto-release / free agency queues (v1)
- Morale auto-decrement columns beyond existing `morale` (v1 skip)
