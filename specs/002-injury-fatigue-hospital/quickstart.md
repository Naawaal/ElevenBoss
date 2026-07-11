# Quickstart: Validate Fatigue, Injury & Hospital

Phases 1–2 are shipped. Section **7** covers Phase 3 when that PR lands.

## Prerequisites

- Feature branch `002-injury-fatigue-hospital` with plan implemented
- Migrations applied through fatigue/injury/hospital (`050+`)
- `DATABASE_URL` / bot staging environment
- Test club with coins for at least one Hospital upgrade and several cards

## 1. Schema

```bash
python scratch/verify_schema_full.py
# or
psql "$DATABASE_URL" -f supabase/scripts/verify_required_schema.sql
```

**Expect**: `player_cards.fatigue`, injury columns, `players.hospital_level`, `hospital_patients`, RPCs `apply_match_fatigue`, `process_post_match_injuries`, `process_daily_recovery`, extended `upgrade_club_facility`, RLS policies present.

## 2. Unit tests

```bash
pytest tests/test_fatigue_injury_math.py -q
```

**Expect**: drain formula examples; penalty tier multipliers; injury chance monotonic in fatigue; recovery days vs hospital level; roll 100 → Major; hospital costs ladder.

## 3. Phase 1 — Fatigue (manual)

1. Note fatigue on starting XI (should be 100 for fresh cards).
2. Play a **bot** match (Attack stance if possible).
3. Confirm starters’ fatigue decreased; bench cards (if any tracked) increased by ~15.
4. Confirm `/squad` or profile shows fatigue indicator.
5. Confirm `action_energy` changed only by normal match spend — not by fatigue recovery.
6. Play a **friendly** — fatigue values unchanged by post-match writes.

## 4. Phase 2 — Injury + Hospital

1. `/store` → Club Facilities → upgrade Hospital L0→L1 for 1,500 coins (respect weekly cap).
2. Force or play until a post-match injury occurs (staging may use a debug hook if added; otherwise lower chance temporarily in staging config).
3. With free bed: card shows injured + in hospital; expected return visible within 10s on profile/Hospital panel.
4. Fill beds and create overflow: DM or Hospital panel offers resolution — no silent drop.
5. Attempt drill / put injured in XI — blocked with clear message.
6. Run or await `process_daily_recovery` — fatigue rises; due patients discharge.

## 5. Regression

- Bot/league XP + economy still apply (no pipe bypass).
- YA/TG upgrades still work; weekly cap shared (second facility upgrade same week fails).
- Auto-sim league fixture completes with fatigue/injury and no interactive sub prompt.

## 6. Still out of product scope

- Career-ending retire
- Hospital multi-day build timers

## 7. Phase 3 — In-match substitution (when implemented)

```bash
pytest tests/test_match_substitution_resolve.py -q
```

**Expect**: auto-pick prefers same position then highest OVR; empty bench → 10-men; Play On tier upgrade ~60%; emergency GK flagged.

### Manual live bot match

1. Staging: force or raise mid-match injury chance so a human-side injury fires before 90'.
2. Confirm commentary pauses at stoppage (`FOUL`/`GOAL`/`SAVE`/`HALF_TIME`) with Select + Play On.
3. Select a bench player within 30s → substitute appears in later events; injured not on pitch.
4. Replay: ignore prompt → after 30s auto-pick (or 10-men if no bench).
5. Play On → player stays; performance clearly worse; post-match injury persists (possible tier bump).
6. Exhaust 3 subs then force another injury → no Select; 10-men / Play On only.
7. GK injury with no GK on bench → emergency GK path.
8. Confirm post-match: **one** injury persist (no double roll); Hospital admit/overflow still works.
9. League auto-sim fixture: completes with no Discord hang; injuries auto-resolved.
10. Friendly: still no injury/sub prompts.
