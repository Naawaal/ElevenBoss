# Research: Youth Academy Integration

**Feature**: `015-youth-academy` | **Date**: 2026-07-12  
**Purpose**: Resolve technical unknowns for plan/contracts; freeze decisions before tasks.

---

## 1. Current state (what already ships)

| Piece | Location | Behavior today |
|-------|----------|----------------|
| YA level 1–5 | `players.youth_academy_level` (043) | Upgrade via `/store` → Club Facilities |
| Intake quality tiers | `economy.facility_effects.YOUTH_ACADEMY_TIERS` | POT/OVR/gem by level |
| Weekly intake | `process_youth_intake` + Monday job | Inserts **senior** `player_cards`; DM embed |
| Generation | `gacha.generate_youth_intake` / `youth_intake.generate_youth_intake_cards` | Ages 16–19, Common |
| Regen market | 044 scouting pool | Retirement regens — **orthogonal** to academy holding |
| Senior roster hard cap | **None** | Clubs can accumulate unbounded cards |

**Gap**: No holding phase, slots, passive academy growth, promote/release, or paid scout assignments. Facility upgrade only changes next intake numbers.

---

## 2. Decisions

### D1 — Storage: `player_cards.in_academy` flag (not a parallel table)

- **Decision**: Add `in_academy BOOLEAN NOT NULL DEFAULT FALSE`. Academy prospects are real cards excluded from XI/match/drills/marketplace until promoted (`in_academy := FALSE`).
- **Rationale**: Reuses factory, profile, age/DOB, POT; grandfather is trivial (default false); promote is one UPDATE; release is DELETE (or soft-delete if preferred — v1 DELETE).
- **Alternatives considered**:
  - Separate `youth_prospects` table — cleaner isolation, worse duplication and profile gap.
  - Status enum (`academy`/`senior`/`released`) — more states than v1 needs.

### D2 — Intake remains Monday free; seating respects slots

- **Decision**: Keep Monday 00:00 UTC job. Change `process_youth_intake` to insert with `in_academy = TRUE`, seat at most `free_slots`, return `seated_ids` + `skipped_count`. Never overwrite existing academy cards.
- **Rationale**: FR-002 / FR-015 hybrid; FR-004 capacity; FR-017 grandfather (old cards untouched).
- **Alternatives**: Replace weekly with paid-only — rejected in clarify Q1.

### D3 — Passive OVR growth (not `apply_card_xp`)

- **Decision**: Daily RPC `process_daily_academy_growth` accumulates development points and awards +1 overall (and position-weighted micro-stat bumps) capped at `potential`. No skill points, no level curve until after promote.
- **Rationale**: Spec auto-allocate / no youth drill UI; AGENTS §7 keeps senior XP pipe clean.
- **Formula** (authoritative; mirrored in SQL + `youth_math.py`):

```text
POINTS_PER_OVR = 100
daily_points = 10 + (5 * academy_level) + floor(potential / 25)
  # L1 pot82 ≈ 10+5+3 = 18 → ~5.5 days/OVR
  # L5 pot94 ≈ 10+25+3 = 38 → ~2.6 days/OVR

On tick: academy_progress += daily_points
While academy_progress >= 100 AND overall < potential:
  overall += 1
  academy_progress -= 100
  bump one primary+secondary stat per position weights (same spirit as player_factory), each stat ≤ potential
```

- **Ready guideline**: `overall >= 65` → UI “ready” (promote still allowed earlier).
- **Alternatives**: Grant XP via `apply_card_xp` — rejected (SP + level noise). Active youth drills — rejected (YAGNI / Discord attention).

### D4 — Academy slot ladder

| Level | Max slots |
|-------|-----------|
| 1 | 4 |
| 2 | 5 |
| 3 | 6 |
| 4 | 8 |
| 5 | 10 |

- **Decision**: Pure helper `academy_slot_cap(level)` in `facility_effects.py`; RPC enforces same numbers (or `game_config` JSON override later — v1 hardcode in RPC + Python mirror).
- **Rationale**: Matches approved spec table.

### D5 — Senior roster capacity for promote

- **Decision**: Introduce `game_config` key `senior_roster_cap` default **48**. Count = `player_cards` where `owner_id = X AND in_academy = FALSE AND COALESCE(is_retired,FALSE) = FALSE`. Promote blocked when count ≥ cap.
- **Rationale**: Spec requires a capacity check; none exists today. 48 is generous so grandfathered bloated clubs are not instantly bricked; still blocks infinite promote farming.
- **Alternatives**: Unlimited promote — fails FR-006 capacity language. Cap 25 — too harsh with historical intake spam.

### D6 — UI entry

- **Decision**: `/profile` gains **Manage Academy** → `AcademyHubView` (list, promote, release, scout). YA upgrades stay on Club Facilities. No `/academy` command.
- **Rationale**: Clarify Q2 / FR-016.

### D7 — Paid scouting (P2, same release)

| Tier | Duration | Cost (coins) | Fog |
|------|----------|--------------|-----|
| quick | 2h | 3_000 | position + star band only |
| standard | 8h | 10_000 | + OVR |
| deep | 24h | 25_000 | + OVR + POT/stars clear |

- **Decision**: One active assignment per club (`players.scouting_finishes_at`). On claim window, materialize `scouting_reports` row with `prospects_json` (3 candidates). Manager may **sign at most 1** into a free academy slot before report `expires_at` (default +48h from finish). Coins via `apply_club_economy` reason `youth_scout_*`.
- **Rationale**: Sink below “always better than packs”; max 1 sign controls inflation vs weekly free 3.
- **Generation**: Reuse `generate_youth_intake_cards` / academy tier; fog in embed layer only (full stats stored server-side for deep/standard honesty on sign).
- **Alternatives**: Region map — out of scope. Sign all 3 — too generous.

### D8 — Age-out

- **Decision**: If `in_academy` and `card_age_from_dob >= 20`, daily job attempts auto-promote; if senior cap full or promote fails, DELETE card and record notification payload for DM/hub banner.
- **Rationale**: Intake ages 16–19; gives at least some academy time; prevents eternal parking (FR-012).
- **Alternatives**: Auto at 18 — too aggressive vs intake age 19. Free-agent pool on release — follow-up.

### D9 — Match / squad / economy exclusions

- **Decision**: Squad assign rejects `in_academy`; marketplace sell list excludes them; development drill/fusion/mentor targets exclude them; match XP already assignment-based so XI-safe if assign blocked.
- **Rationale**: FR-003.

### D10 — Upgrade during scouting

- **Decision**: Growth ticks read **current** `youth_academy_level` each day. Existing `scouting_reports.prospects_json` not rerolled on upgrade.
- **Rationale**: Spec edge case default.

---

## 3. Industry mapping (kept Discord-simple)

| Inspiration | Kept | Cut |
|-------------|------|-----|
| EA FC scouting | Timed paid reports + shortlist | Region micromanagement |
| FM intake day | Weekly free batch | U18 league / coach reports |
| Top Eleven facilities | Level → capacity/quality | Heavy menus |

---

## 4. Risks

| Risk | Mitigation |
|------|------------|
| Clubs already have huge senior rosters from old intake | Grandfather; generous senior cap; academy stops new bloat |
| Growth too fast → wonderkids dominate | Cap at POT; L1 slow; ready at 65 still needs squad space; packs remain instant OVR |
| Double intake + scout inflation | Slot caps; scout max 1 sign; full academy skips intake seats |
| `apply_card_xp` misuse | Contract forbids; code review checklist |
| Missing RLS on `scouting_reports` | Ship RLS + policies in 060 |

---

## 5. Open items deferred to implement (not blockers)

- Exact DM copy for age-out / skipped intake
- Whether release soft-deletes vs hard DELETE (default hard DELETE)
- Optional small promote fee (spec default **off**)

All Technical Context unknowns from planning are resolved above — no remaining NEEDS CLARIFICATION.
