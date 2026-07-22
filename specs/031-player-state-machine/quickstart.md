# Quickstart: Player State Machine (US-42.2)

## Prerequisites

- Read [spec.md](./spec.md) §B (states + matrix)
- US-42.1 applied (`074` identity) recommended before 075
- Feature dir `specs/031-player-state-machine`

## Validation 0 — Comprehension

1. Can a Listed card be drilled?  
2. Is MatchLocked a primary exclusive state?  
3. Does fatigue alone block listing?  
4. What priority wins if Listed + Hospitalized flags both set?

**Expect**: No; No (overlay); No; Block / conflict (Listed wins classify priority but mutations fail closed on conflict).

## Validation 1 — W0 audit

Fill [contracts/rpc-guard-audit.md](./contracts/rpc-guard-audit.md) via greps:

```bash
rg -n "assert_not_in_match|assert_card_not_on_transfer_list|in_hospital|in_academy|active_evolutions|active_training" supabase/migrations
```

## Validation 2 — Pure tests (after W1)

```bash
pytest tests/test_card_state_derive.py tests/test_card_state_matrix.py -q
```

## Validation 3 — Migration 075 (after W2)

```bash
python scratch/apply_migration_075.py
python scratch/smoke_player_card_state_075.py
```

## Validation 4 — Persona

1. List a RosterFree card → try Start Evolution → blocked.  
2. Start match lock → try squad swap → blocked.  
3. Cancel listing → drill allowed again.

## Out of scope

- US-42.6 purchase races  
- Soft club abandonment UI  
- New slash commands  
