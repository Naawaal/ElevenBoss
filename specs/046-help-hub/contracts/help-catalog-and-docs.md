# Contract: Help Catalog & Docs Links

**Feature**: `046-help-hub`  
**Consumers**: Embed builders, views, autocomplete, unit tests

## Required topic IDs

| ID | Minimum embedded coverage |
|----|---------------------------|
| `getting-started` | `/register`, first squad, next hubs; Core Loop (energy → match → XP/level → SP → growth) |
| `battle` | Bot Battles, Friendly, Ranked **coming soon**, live pitch, commentary |
| `squad` | `/squad`, formation, swap, pitch visual |
| `training` | `/development` drills, skill allocation, mentor transfusion |
| `evolutions` | Tracks, requirements, rewards, how to start (via development hub) |
| `league` | Seasons, registration, matchdays, divisions, rewards, automation overview |
| `economy` | Coins, gems if live, `/store` refills, marketplace listing/tax/discovery at live fidelity |
| `hospital` | Fatigue, injury, recovery, hospital upgrades |
| `commands` | Placeholder body OK — filled by harvest at render |

## Docs resolution

```text
DOCS_BASE = "https://share.jotbird.com/bright-serene-sandia"

resolve_docs_url(None | "" | whitespace) -> DOCS_BASE
resolve_docs_url(path) -> absolute URL under DOCS_BASE (no bare relative links)
```

- Hub Full Documentation → `DOCS_BASE`
- Topic Read More → `resolve_docs_url(topic.docs_path)`
- v1 may set all `docs_path` empty until jotbird deep pages exist

## Editability (SC-007)

Updating topic prose or docs paths MUST require changes only in the catalog module (plus tests if IDs change) — not edits across unrelated cogs for copy alone.

## Accuracy

- Do not document unshipped mechanics as live (except explicit “coming soon”).
- Prefer “use `/hub`” over duplicating formula tables that belong in RPCs.
