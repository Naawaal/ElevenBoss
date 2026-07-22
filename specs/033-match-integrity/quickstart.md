# Quickstart: Match Integrity (US-42.4)

## Prerequisites

- Read [spec.md](./spec.md) §B + [contracts/match-path-audit.md](./contracts/match-path-audit.md)
- Migrations `074`–`076` applied recommended
- Feature dir `specs/033-match-integrity`

## Validation 0 — Comprehension

1. Can presentation retry re-pay coins?  
2. Does friendly tick evolutions?  
3. Who owns league forfeits?  
4. After embed fails post-pay, should the run be `abandoned`?

**Expect**: No; No; `026`; No → `completed` + retry present.

## Validation 1 — W0 audit

Confirm Critical rows in `match-path-audit.md` match current `battle_cog` / `match_recovery`.

## Validation 2 — Tests (after implement)

```bash
pytest tests/test_match_integrity_recovery.py tests/test_match_integrity_sql_guards.py tests/test_match_xp.py -q
rg -n "tick_evolution_match_progress" apps/
# expect: no matches under apps/
```

## Validation 3 — Migration 077

```bash
python scratch/apply_migration_077.py
python scratch/smoke_match_integrity_077.py
```

## Validation 4 — Persona

1. Bot match pays → kill Discord send → rerun present → balance unchanged.  
2. Mid-bot restart after pay → run `completed`, not abandoned.  
3. League human play → opponent MatchLocked until end.

## Out of scope

- `026` calendar rewrite  
- Marketplace races  
- New slash commands  
