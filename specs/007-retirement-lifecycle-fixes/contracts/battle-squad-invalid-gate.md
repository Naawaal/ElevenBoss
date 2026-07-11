# Contract: Battle Squad-Invalid Gate

**Surface**: `apps/discord_bot/cogs/battle_cog.py` (and any shared helper if extracted)  
**Feature**: `007-retirement-lifecycle-fixes`

## When to block

Before starting a match for a human club, block if either:

1. `players.squad_invalid = TRUE`, or
2. Starting XI assignment count ≠ 11 (existing hard rule)

Applies to at least:

- Bot match start
- League fixture kickoff for the triggering manager
- Friendly match start (challenger and opponent each need a valid XI)

## Manager copy

When blocked primarily due to retirement fallout (`squad_invalid` true, or count≠11 with flag true):

> Your starting XI is invalid due to a recent retirement. Please visit `/squad` to set your lineup.

When blocked for incomplete XI and flag is false (never configured / partial save):

> Keep the existing “must have exactly 11 players… Configure using `/squad`” copy.

Ephemeral error embed; no match lock / energy debit on this failure path.

## Clear path

Manager uses `/squad` → save formation/assignments via `set_formation_and_assignments` → flag cleared (see [retire-squad-vacancy-rpc.md](./retire-squad-vacancy-rpc.md)).

## Optional hub hint

`/squad` hub may show a short warning when `squad_invalid` is true (not required for MVP if battle gate is wired).

## Non-goals

- New slash command
- Auto-opening squad UI from battle
- Changing match engine lineup builders
