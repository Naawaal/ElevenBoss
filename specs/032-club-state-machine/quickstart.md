# Quickstart: Club State Machine (US-42.3)

## Prerequisites

- Read [spec.md](./spec.md) §B (soft lifecycle + matrix)
- US-42.1 (`074`) applied; US-42.2 (`075`) recommended
- Feature dir `specs/032-club-state-machine`

## Validation 0 — Comprehension

1. Can an Inactive club still run drills?  
2. Can an Abandoned club join a **new** league season?  
3. Is LeagueSeated a soft primary?  
4. Who owns the 21-day calendar?

**Expect**: Yes; No; No (overlay); `026`/`027`.

## Validation 1 — W0 audit

Fill [contracts/club-rpc-guard-audit.md](./contracts/club-rpc-guard-audit.md) (league cog path is Critical).

## Validation 2 — Pure tests (after W1)

```bash
pytest tests/test_club_state_matrix.py tests/test_club_state_sql_guards.py -q
```

## Validation 3 — Migration 076 (after W2)

```bash
python scratch/apply_migration_076.py
python scratch/smoke_club_state_076.py
```

Expect: `assert_club_action_allowed` + `register_league_season` exist; Inactive/Abandoned league_join raises `CLUB_STATE:`.

## Validation 4 — Persona

1. Abandoned manager taps Join League → blocked with recover/play-first copy.  
2. Active manager double-taps join → AlreadySeated, one registration row.  
3. Leave guild mid-season → club row still present (no delete).

## Out of scope

- Rewriting `026` calendars  
- Player-card busy matrix (`031`)  
- New slash commands  
