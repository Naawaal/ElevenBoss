# Data Model: Fatigue, Injury & Hospital

## New / extended entities

### Player card fitness (`player_cards`)

| Column | Type | Default | Rules |
|--------|------|---------|-------|
| `fatigue` | INTEGER | 100 | CHECK 0–100; existing rows get 100 via DEFAULT |
| `injury_tier` | INTEGER NULL | NULL | NULL = healthy; v1 values 1–3 (Minor/Moderate/Major) |
| `injury_started_at` | TIMESTAMPTZ NULL | NULL | Set when injury applied |
| `injury_recovery_days` | INTEGER | 0 | Remaining days (untreated path) or mirror of plan |
| `in_hospital` | BOOLEAN | FALSE | TRUE iff active `hospital_patients` row |

**Notes**: PHY/age already exist (`phy`, `age`) for drain/injury formulas. Do not store fatigue on `players`.

### Club hospital (`players`)

| Column | Type | Default | Rules |
|--------|------|---------|-------|
| `hospital_level` | INTEGER | 0 | CHECK 0–5; beds = level + 1 |

Shares `facility_last_upgrade_at` with YA/TG for weekly upgrade cap.

### Hospital admission (`hospital_patients`)

| Column | Type | Rules |
|--------|------|-------|
| `id` | UUID PK | |
| `owner_id` | BIGINT FK → `players.discord_id` | Club owner |
| `player_card_id` | UUID FK → `player_cards.id` | |
| `injury_tier` | INTEGER | 1–3 in v1 |
| `admission_date` | TIMESTAMPTZ | DEFAULT NOW() |
| `expected_recovery_date` | TIMESTAMPTZ | NOT NULL |
| `discharge_date` | TIMESTAMPTZ NULL | NULL = active |

**Constraints**:
- Partial unique: one **active** admission per card (`WHERE discharge_date IS NULL`)
- Index: `(owner_id) WHERE discharge_date IS NULL`
- RLS enabled + SELECT/INSERT/UPDATE policies for bot roles (same pattern as league members)

### Game config keys

| Key | Value | Purpose |
|-----|-------|---------|
| `hospital_upgrade_costs` | `[1500, 4000, 10000, 25000, 60000]` | L0→1 … L4→5 |
| `fatigue_base_drain` | `22` | Match drain base |
| `fatigue_passive_per_day` | `20` | Daily recovery |
| `fatigue_hospital_per_day` | `45` | Daily recovery if admitted |
| `fatigue_bench_per_match` | `15` | Bench rest per match |

Penalty tiers and injury base chances may live in Python defaults first; promote to `game_config` only if ops tuning is needed in v1.

## Relationships

```text
players (club)
  ├── hospital_level
  ├── youth_academy_level / training_ground_level
  └── owns player_cards[]
        ├── fatigue / injury_*
        └── 0..1 active hospital_patients

upgrade_club_facility(hospital)
  → apply_club_economy(-cost)
  → players.hospital_level++

Competitive match end
  → apply_match_fatigue(starters drain, bench recover)
  → process_post_match_injuries → admit or overflow
```

## State transitions

### Fatigue

| From | Event | To |
|------|-------|-----|
| Any &lt; 100 | daily recovery / hospital day | min(100, fatigue + 20 or +45) |
| Starter post-match | drain formula | max(0, fatigue − drain) |
| Bench post-match | bench rest | min(100, fatigue + 15) |

### Injury

| From | Event | To |
|------|-------|-----|
| Healthy | post-match injury roll hit | tier 1–3; recovery days computed; try admit |
| Injured, bed free | auto-admit | `in_hospital=true`; hospital_patients row |
| Injured, beds full | overflow | `in_hospital=false`; waiting; manager resolves |
| In hospital, expected date passed | daily recovery | discharge; clear injury fields; optional fatigue bonus |
| Untreated, recovery_days → 0 | daily recovery | clear injury fields |

### Hospital level

| From | Event | To |
|------|-------|-----|
| 0–4 | successful upgrade | level+1; coins debited; `facility_last_upgrade_at=now()` |
| Any | weekly cap active | reject upgrade |

## Validation rules

- Injured cards cannot enter starting XI or drills.
- Fusion/sell of admitted card: block **or** discharge-then-proceed (pick one in tasks; prefer **block with clear error** for v1).
- Friendlies: no fatigue/injury transitions.
- Injury roll 100 → Major (not retire).
- Beds = `hospital_level + 1` (level 0 ⇒ 1 bed).
- Recovery days = `ceil(base_tier_days / (1 + 0.2 * hospital_level))` at admission time (untreated uses hospital_level 0 multiplier = 1.0×).

## Phase 3 — In-match runtime (no new DB tables)

Ephemeral match memory only (not persisted as columns). See [contracts/in-match-injury-sub.md](./contracts/in-match-injury-sub.md).

### Match runtime / `MatchState` sidecar

| Field | Type | Rules |
|-------|------|-------|
| `bench_home` / `bench_away` | list of match cards | ≤7 reserves hydrated at kickoff |
| `subs_used_home` / `subs_used_away` | int | 0–3; increment on successful sub |
| `pending_injuries` | queue | Held until stoppage yield |
| `recorded_injuries` | list | Fed to post-match RPC; skips re-roll when non-empty |
| `compromised_card_ids` | set | Play On → phase-attr ×0.50 |
| `sub_resolution` | latest choice | Written by Discord view or auto-resolve |
| `sub_wait_event` | `asyncio.Event` | Sidecar outside Pydantic (not serializable) |

### Match Injury Event (entity)

| Field | Meaning |
|-------|---------|
| `card_id`, `side`, `minute`, `tier` | Who / when / severity |
| `resolution` | `sub` \| `play_on` \| `ten_men` \| `emergency_gk` \| `auto` |
| `replacement_card_id` | Optional |

### State transitions (Phase 3 addendum)

| From | Event | To |
|------|-------|-----|
| Healthy on pitch | mid-match A+C hit | pending injury → stoppage prompt / auto-resolve |
| Prompt open | Select sub | injured off; replacement on; `subs_used++`; record |
| Prompt open | Play On | stay on pitch; compromised; record (+ tier upgrade risk at persist) |
| Prompt open | timeout | auto-pick or 10-men |
| Prompt open | no bench / no subs | 10-men; record |
| GK injured, no GK bench | emergency | outfield as GK with penalty flag |
| minute ≥ 90 | injury | record only; no prompt |
