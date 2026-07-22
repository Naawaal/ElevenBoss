# Contract: RPC Guarantee Checklist (US-42.9)

Use this checklist for every new/changed mutating RPC or bot-required table in this feature (and prefer for all future features).

## Checklist

- [ ] Columns/tables exist only via numbered `supabase/migrations/NNN_*.sql`
- [ ] No invented column names vs migrations
- [ ] Complex money/ownership mutation is one RPC (or documented atomic unit) — not Python multi-step partial writes
- [ ] Idempotency key or natural uniqueness documented
- [ ] `DROP FUNCTION` old overloads when replacing signatures
- [ ] `verify_required_schema.sql` (and/or migration guard) extended for bot-required objects
- [ ] If Data API exposed: `ENABLE ROW LEVEL SECURITY` + policies in same migration
- [ ] Callers in `apps/` grepped and updated
- [ ] Fail closed if schema incomplete (INV-16)
- [ ] Does not bypass economy/XP pipes

## Sample note (pre-existing)

| RPC | Compliant? |
|-----|------------|
| `purchase_transfer_listing` | Yes — FOR UPDATE + economy keys + own-buy |
| `apply_club_economy` | Yes — ledger + key |
| `abandon_match_run` (077) | Yes — guarded |
| `distribute_season_prizes` | Yes — keys + humans-only |
| `create_transfer_listing` (075) | Yes — `assert_card_action_allowed` |

## Feature 035 note

- **No migration 078** shipped in this remainder wave (docs + greps only).
- Any future SQL under this feature MUST re-run this checklist and extend `verify_required_schema.sql`.
