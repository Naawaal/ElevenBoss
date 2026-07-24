# Contract: `/help` Command Surface

**Feature**: `046-help-hub`  
**Consumers**: Managers in guilds and DMs; Discord command tree sync

## Slash command

| Name | Description (approx.) | Options |
|------|----------------------|---------|
| `help` | Open the ElevenBoss in-Discord guide | `topic` (optional string, autocomplete) |

## Invocation rules

| Context | `ephemeral` | `@guild_only` |
|---------|-------------|----------------|
| Guild channel | `true` | **Must not** be guild-only |
| Bot DM | `false` | — |

1. Handler MUST `defer` (or send) immediately before any optional club lookup.
2. Static hub/topic bodies MUST render without requiring a successful DB call.
3. Optional club check: if `players` row missing for `interaction.user.id`, set Getting Started emphasis; on failure, proceed without emphasis.

## Topic option

| Input | Behavior |
|-------|----------|
| Omitted / empty | Open Help Hub |
| Valid catalog `id` (or accepted label alias) | Open that topic embed + Back + Read More |
| Unknown | Soft recovery: Hub with short “unknown topic” notice, or error listing valid topics — never traceback |

Autocomplete MUST return catalog topics (≤25), filtered by `current` substring (case-insensitive) on `id` and/or `label`.

## Mutations

**Forbidden**: coin/XP/energy/squad/league writes, new RPCs, schema changes.

## Registration

- Cog module registered in `ElevenBossBot.cogs_list` (e.g. `apps.discord_bot.cogs.help_cog`).
- No persistent `bot.add_view` required for help.
