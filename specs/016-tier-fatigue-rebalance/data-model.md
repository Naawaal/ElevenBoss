# Data Model: Division-Tier Fatigue & Injury Rebalance

**Feature**: `016-tier-fatigue-rebalance` | **Date**: 2026-07-13

## Entities

### Intensity tier (derived gameplay band)

| Attribute | Type | Rules |
|-----------|------|-------|
| `tier` | 1 \| 2 \| 3 | Required for drain, passive, injury, hospital math |
| Source divisions | text | 1←Grassroots,Amateur · 2←Semi-Pro,Professional · 3←Elite,Legendary |
| Fallback | 1 | Unknown/null division |

Persisted on the club row as `players.intensity_tier`.

### Club (`players` row)

| Field | Change | Notes |
|-------|--------|-------|
| `discord_id` | existing PK | Club id |
| `division` | existing | Settled Monday via weekly reset |
| `intensity_tier` | **NEW** | SMALLINT 1–3, NOT NULL, DEFAULT 1 |
| `hospital_level` | existing | Used in hospital day formula |
| `training_ground_level` | existing | Used in daily recovery `×2` |

**Validation**: `CHECK (intensity_tier BETWEEN 1 AND 3)`.

**Transitions**: On Monday weekly reset, after division promo/relegation UPDATEs, set `intensity_tier = map(division)` for all affected (prefer all players for drift-proofing).

### Player card (`player_cards`)

No new columns. Existing fields remain authoritative:

| Field | Role under 016 |
|-------|----------------|
| `fatigue` | 0–100; drained by tier formula; floored to ≥50 once for uninjured non-hospital cards |
| `injury_tier` | 1 Minor / 2 Moderate / 3 Major — severity multiplier input |
| `injury_recovery_days` | Untreated remaining days (overflow) |
| `injury_started_at` | Fair overflow elapsed |
| `in_hospital` | Excludes fatigue floor; hospital ETA path |

### Hospital stay (`hospital_patients`)

No new columns. `expected_recovery_date` recalculated by backfill using tier-aware total days from `admission_date`.

### Tier balance table (logical — not a DB table)

Constants in Python + SQL (+ optional `game_config` JSON mirror):

| tier | drain_base | passive_base | injury_base | moderate_days |
|------|------------|--------------|-------------|---------------|
| 1 | 8 | 35 | 0.0025 | 3 |
| 2 | 12 | 25 | 0.0040 | 5 |
| 3 | 16 | 15 | 0.0060 | 8 |

Severity multipliers: Minor 0.33, Moderate 1.0, Major 2.5.

### Match fitness application (runtime)

Not stored as a new entity. Per competitive match:

- Resolve human `intensity_tier`
- Build starter drains with that tier (both sides’ *math*; persist human only)
- Injury rolls use that tier’s base chance

## State transitions

```text
Monday 00:00 UTC weekly reset
  players.division updated (promo/relegation/stay)
  → players.intensity_tier := map(division)

Competitive match end (human club)
  → apply_match_fatigue(starter_drains from tier formula)
  → process_post_match_injuries (recovery days from tier×severity÷H)

Daily 00:05 UTC
  → process_daily_recovery (passive from intensity_tier + TG×2)

Ship migration 061 backfill (once)
  → hospital ETA fair recalc (never lengthen; early discharge)
  → fatigue := max(fatigue, 50) for eligible uninjured cards
```

## Out of model scope

- Emergency grey / academy filler cards
- Cup fixture tables
- Bot-persisted fatigue inventory
