# Contract: Club Action Matrix Freeze

**Feature**: US-42.3  
**Source of truth**: [spec.md](../spec.md) §B.5

## Rule

Pure `can_perform_club_action` and SQL `assert_club_action_allowed` MUST share Allow/Block outcomes for actions in `data-model.md` §3.

## Soft lifecycle

| Action | Active | Inactive | Abandoned |
|--------|--------|----------|-----------|
| `league_join` | A | B | B |
| `store_faucet` | A | A | A |
| `development_mutate` / `squad_mutate` / `market_mutate` | A | A | A |
| `match_start` | A | A | A |
| `recover` | — | A | A |
| `view_hub` | V | V | V |

## Overlays / kind

- **MatchLocked**: mutations Block; `view_hub` Allow; `recover` may Allow label flip
- **AI**: Block human hub mutations + `league_join` + store faucets
- **LeagueSeated same season**: `league_join` → AlreadySeated success (idempotent), not soft Block

## Change control

Amend `spec.md` §B.5 first, then pure + SQL together.
