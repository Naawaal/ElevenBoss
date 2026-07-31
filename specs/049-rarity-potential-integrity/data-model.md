# Data Model: Rarity Potential Cap Integrity (`049`)

## Core invariant

For every row in `player_cards` (and every in-memory `CreatedPlayerCard`):

```text
overall ≤ potential ≤ rarity_potential_cap(rarity)
base_potential IS NULL OR base_potential ≤ rarity_potential_cap(rarity)
rarity ∈ {Common, Rare, Epic, Legendary}
```

Age / academy / performance may affect rolls and growth **inside** the cap. They never raise the cap.

## Existing entity: `player_cards` (relevant fields)

| Field | Role in this feature |
|-------|----------------------|
| `rarity` | Selects absolute POT ceiling |
| `overall` | Must stay ≤ `potential` and ≤ rarity cap |
| `potential` | Growth ceiling; must ≤ rarity cap |
| `base_potential` | Dynamic-boost baseline; must ≤ rarity cap |
| `pac`–`phy` | True OVR inputs; repair may adjust these |
| `skill_points` / `skill_points_spent` | SP refund consistency |
| `owner_id` | Current owner (card correction target) |
| `level` / `xp` | Generally preserved |

## New function: `rarity_potential_cap(p_rarity text) → int`

| Input | Output |
|-------|--------|
| `Common` | 75 |
| `Rare` | 85 |
| `Epic` | 92 |
| `Legendary` | 99 |
| other / NULL (STRICT) | NULL |

Used by CHECKs, RPCs, and anomaly queries. Only SQL copy of the mapping (Python mirror in `RARITY_POT_CAPS`).

## Effective potential (logical, not a column)

```text
effective_potential = LEAST(potential, rarity_potential_cap(rarity))
```

Progression mutators use this while historical rows may still be dirty. After VALIDATE, equals stored `potential` for all live rows.

## New table: `potential_cap_repair_audit`

Incident evidence + idempotency for repair/refunds/DMs. **Not** a gameplay surface.

| Column | Type / notes |
|--------|----------------|
| `id` | UUID PK |
| `batch_id` | TEXT — repair batch |
| `card_id` | UUID — FK to `player_cards` (or soft ref if retired) |
| `owner_id` | BIGINT — owner at repair time |
| `rarity` | TEXT |
| `old_overall` / `new_overall` | INT |
| `old_potential` / `new_potential` | INT |
| `old_base_potential` / `new_base_potential` | INT |
| `old_stats` / `new_stats` | JSONB — pac/sho/pas/dri/def/phy (+ optional SP fields) |
| `refund_sp` | INT default 0 |
| `refund_coins` | BIGINT default 0 |
| `refund_energy` | INT default 0 |
| `refund_other` | JSONB default `{}` |
| `refund_confidence` | TEXT CHECK IN (`EXACT`,`RECONSTRUCTED`,`MANUAL_REVIEW`,`NONE`) |
| `repair_category` | TEXT CHECK IN (`A`,`B`,`C`) |
| `repair_status` | TEXT — e.g. `dry_run`, `repaired`, `refunded`, `skipped_manual`, `failed` |
| `repaired_at` | TIMESTAMPTZ |
| `notified_at` | TIMESTAMPTZ |
| `notification_attempts` | INT default 0 |
| `notification_error` | TEXT |
| `created_at` | TIMESTAMPTZ default now() |

**Uniqueness**: `UNIQUE (batch_id, card_id)` — second repair pass is no-op / upsert-safe.

**RLS**: ENABLE + SELECT/INSERT/UPDATE for `anon, authenticated, service_role` (bot service path), same pattern as other ops tables (e.g. `pack_claim_runs`).

## Repair categories (logical)

| Category | Condition | Card mutation | Auto refund |
|----------|-----------|---------------|-------------|
| **A** | POT/base illegal, OVR ≤ cap | Cap POT/base | None |
| **B** | OVR and POT illegal | Cap POT/base; reduce attrs; recalculate OVR | Removed paid progression |
| **C** | Illegal at generation | Normalize to rarity ceiling | Only subsequent paid removed progression |

## Refund confidence (logical)

| Label | Meaning |
|-------|---------|
| `EXACT` | Ledger/metadata ties cost to card+action (e.g. drill economy metadata) |
| `RECONSTRUCTED` | Inferred from aggregates (e.g. `skill_points_spent`) with documented caps |
| `MANUAL_REVIEW` | Ambiguous payer/fusion/items — no silent auto refund |
| `NONE` | Category A or no removed paid progression |

## Optional config

| Key | Purpose |
|-----|---------|
| `game_config.potential_rarity_caps_enabled` | Temporary shadow vs enforce for app/RPC soft paths; **must not** gate CHECK constraints once validated; delete after close |

## Constraints (after repair)

| Name | Expression (conceptual) |
|------|-------------------------|
| `player_cards_potential_rarity_cap_chk` | `rarity_potential_cap(rarity) IS NOT NULL AND potential ≤ rarity_potential_cap(rarity)` |
| `player_cards_base_potential_rarity_cap_chk` | cap NOT NULL AND (`base_potential` IS NULL OR `base_potential` ≤ cap) |
| `player_cards_overall_potential_chk` | `overall ≤ potential` |

Add as `NOT VALID` in 088 if desired; `VALIDATE` in 089 when anomaly count = 0.

## State transitions

```text
[illegal card]
    → inventory / dry-run (audit status dry_run, no live mutate)
    → MANUAL_REVIEW resolve (if needed)
    → repair (POT/stats) → repaired
    → refunds (idempotent) → refunded
    → notify (best-effort) → notified_at set or notification_error
    → constraints VALIDATE when global anomaly = 0

[legal card]
    → producers/ingress/progression always preserve invariant
    → CHECK rejects illegal write
```

## Related existing evidence sources (read-only for dry-run)

- Economy ledger / `apply_club_economy` metadata (`card_id`, `drill_id`, `cost`, …)
- `mentor_transfer_log` (do not auto-reverse; context only)
- `card_ownership_history` / transfer logs (payer attribution)
- Evolution completion records (refund cost if reconstructable; do not reopen claim)
