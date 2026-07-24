# Data Model: Marketplace Intelligence

**Feature**: `043-marketplace-intelligence`  
**Migration**: `086_marketplace_intelligence.sql` (forward-only)

---

## 1. `transfer_sales_log` (enriched)

Existing table from `062`. **ALTER** add nullable snapshot columns (NULL for pre-086 rows).

| Column | Type | Notes |
|--------|------|-------|
| *(existing)* `id`, `listing_id`, `seller_id`, `buyer_id`, `card_id`, `gross_price`, `tax_amount`, `seller_net`, `created_at` | unchanged | Still `CHECK (gross = tax + net)`; `UNIQUE(listing_id)` |
| `fair_value_coins` | `BIGINT` NULL | `compute_agent_offer` at purchase; CHECK NULL or `> 0` |
| `rarity` | `TEXT` NULL | Snapshot |
| `role` | `TEXT` NULL | Position/role snapshot (GK/DEF/MID/FWD or stored role string — match `player_cards.role`) |
| `overall` | `INTEGER` NULL | Snapshot |
| `potential` | `INTEGER` NULL | Snapshot |
| `age_at_sale` | `INTEGER` NULL | Effective age at sale |
| `player_name` | `TEXT` NULL | Display name at sale |

### Indexes (add)

| Name | Definition | Purpose |
|------|------------|---------|
| *(existing)* `transfer_sales_log_buyer_card_created_idx` | `(buyer_id, card_id, created_at DESC)` | Relist cooldown |
| `transfer_sales_log_created_idx` | `(created_at DESC)` | Analytics windows |
| `transfer_sales_log_card_created_idx` | `(card_id, created_at DESC)` | Card sale history |
| `transfer_sales_log_cohort_idx` | `(role, rarity, overall, created_at DESC)` | Price discovery cohort |

### Immutability

- No UPDATE of money or snapshot columns after INSERT (convention + no update RPC).  
- App/ops MUST NOT UPDATE these rows.

---

## 2. `card_ownership_history` (new)

Append-only segment trail per card.

| Column | Type | Notes |
|--------|------|-------|
| `id` | `BIGSERIAL` PK | |
| `card_id` | `UUID NOT NULL` | **No FK** to `player_cards` (survives DELETE) |
| `owner_id` | `BIGINT` NULL | `REFERENCES players(discord_id) ON DELETE SET NULL` |
| `club_name` | `TEXT NOT NULL` | Snapshot of `players.club_name` at open (fallback `'Unknown Club'`) |
| `acquired_via` | `TEXT NOT NULL` | See enum below |
| `started_at` | `TIMESTAMPTZ NOT NULL DEFAULT NOW()` | |
| `ended_at` | `TIMESTAMPTZ` NULL | NULL = current/open segment |
| `ended_via` | `TEXT` NULL | Why closed: `p2p_transfer`, `agent_sale`, … |
| `transfer_sales_log_id` | `BIGINT` NULL | Set when closed/opened by P2P sale; `REFERENCES transfer_sales_log(id) ON DELETE SET NULL` |

### `acquired_via` values

| Value | When |
|-------|------|
| `p2p_transfer` | Buyer segment after P2P purchase |
| `scouting` | Regen pool sign (if wired) |
| `youth_scout` | Academy scout sign (if wired) |
| `legacy_bootstrap` | Lazy ensure when no history existed |
| `agent_end` | Not used for open segments; prefer `ended_via='agent_sale'` on close |

### Indexes / constraints

| Name | Definition |
|------|------------|
| `card_ownership_history_card_started_idx` | `(card_id, started_at ASC)` |
| `card_ownership_history_one_open_uidx` | **UNIQUE** `(card_id) WHERE ended_at IS NULL` |
| `card_ownership_history_owner_idx` | `(owner_id, started_at DESC)` |

### State transitions

```text
  (no rows) --ensure/open--> [open segment]
  [open] --P2P sale--> close seller + open buyer
  [open] --agent sale--> close (ended_via=agent_sale); no buyer segment
  [open] --(future retire/etc.)--> close with ended_via; out of scope unless needed
```

---

## 3. Config (`game_config`)

| Key | Default | Purpose |
|-----|---------|---------|
| `price_discovery_min_sales` | `5` | Min completed cohort sales for avg/median/trend |
| `price_discovery_ovr_window` | `3` | ± OVR band for cohort |

Existing transfer/agent keys unchanged.

---

## 4. Read models (RPC JSON, not tables)

### Price discovery summary

Computed for subject `(role, rarity, overall)`:

- `sample_size`, `insufficient_data` (bool)  
- If sufficient: `avg_sale_price`, `median_sale_price`, `recent_sales[]` (bounded), `trend` (`up`/`down`/`flat`/null)  
- From active listings cohort: `active_count`, `lowest_active`, `highest_active`

### Market analytics snapshot

For `[from, to)`:

- P2P: `sales_count`, `gross_volume`, `tax_removed`, `avg_hours_to_sale`  
- Listings: `created_count`, `expired_count`, `cancelled_count`, `success_rate` (sold / created in window)  
- Agent: `agent_sale_count`, `agent_coins_paid` (from ledger or sale RPC audit)  
- Breakdowns: top positions/rarities, highest transfers, most active clubs (buyer+seller counts)

---

## 5. RLS

- `card_ownership_history`: ENABLE RLS; SELECT/INSERT/UPDATE policies for `anon, authenticated, service_role` (bot key pattern matching `transfer_sales_log`). Prefer mutations via SECURITY DEFINER helpers/RPCs.  
- `transfer_sales_log`: existing policies; no policy removal.  
- Extend `verify_required_schema.sql` + migration guard for new table, columns (as needed), functions, policies.

---

## 6. Relationships

```text
transfer_listings 1──1 transfer_sales_log (on sold)
transfer_sales_log *──1 card (logical card_id)
card_ownership_history *──1 card (logical card_id)
card_ownership_history *──1 players (owner_id, nullable if deleted)
```

---

## 7. Validation rules

1. Sales log insert only from successful purchase path.  
2. At most one open ownership segment per `card_id`.  
3. Closing a segment requires `ended_at >= started_at`.  
4. Price discovery never fabricates averages when `sample_size < min_sales`.  
5. Snapshot fields NULL only for legacy rows; new P2P sales MUST populate all snapshot columns.
)
