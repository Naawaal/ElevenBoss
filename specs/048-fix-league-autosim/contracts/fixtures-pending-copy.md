# Contract: Fixtures Pending / Forfeit Copy

**Feature**: `048-fix-league-autosim`  
**Consumers**: `LeagueCog.show_fixtures` (and hub season progress if it echoes fixture state)

## Played fixtures

| `result_type` | Display |
|---------------|---------|
| normal / null / settled | `{home} - {away} (Full Time)` (existing) |
| `forfeit` | `{home} - {away} (Forfeit)` |
| `double_forfeit` | `{home} - {away} (Double Forfeit)` |

## Unplayed + window expired

| Situation | Display |
|-----------|---------|
| Default before/during settle | `Expired (Pending Auto-Sim)` OK for at most one settle cycle |
| Still unplayed and a human side fails eligibility (best-effort) | Pending line **plus** short hint: which club must renew/replace XI — or show forfeit once settle runs |
| After successful settle | Must show played copy above, not Pending |

## Forbidden

- Implying the bot will wait forever with no outcome
- Showing “Full Time” for forfeit/double_forfeit without a forfeit cue (SC-003)
