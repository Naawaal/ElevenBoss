# Contract: Bot squad identity

## Problem

Live bot/AI opponents currently hydrate as three `MatchPlayerCard`s named `Opponent Striker`, `Opponent Midfielder`, `Opponent Defender`. NSS correctly puts `card.name` into event `actor`, so commentary and Goal Scroll show those stubs.

## API

```text
build_bot_match_squad(target_ovr: int, rng: random.Random) -> list[MatchPlayerCard]
```

- Package: `packages/match_engine` (pure; no Discord/DB)
- Exported from `match_engine.__init__`

## Requirements

| Rule | Detail |
|------|--------|
| Size | Exactly 11 cards |
| Names | Human-like first+last from shared name lists; never `Opponent <Role>` stubs |
| Positions | Include GK + DEF + MID + FWD coverage (4-4-2 blueprint preferred) |
| OVR | Each card overall near `target_ovr` (small noise allowed) |
| Attrs | `pac/sho/pas/dri/def/phy` near overall (not left at default 50 when OVR is high) |
| Determinism | Same `rng` seed → same squad |

## Call sites (must migrate)

- Bot match opponent squad in `battle_cog`
- League fixture AI home squad
- League fixture AI away squad

Post-change grep MUST find **zero** `Opponent Striker` / `Opponent Midfielder` / `Opponent Defender` string literals used as card names.

## Guarantees

- Human-vs-human friendlies unchanged (real card names).
- Simulator yield sites need no actor-string rewrite for this contract.

## Non-goals

- Persisting bot players in Supabase
- Full gacha rarity / youth intake pipeline for bots
- Pre-match pitch image for AI XIs (optional later)
