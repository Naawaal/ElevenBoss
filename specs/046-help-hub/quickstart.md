# Quickstart: In-Discord Help Hub (`046`)

Validate `/help` end-to-end after implementation. No migrations.

## Prerequisites

- Bot token in `.env`; bot running (`python -m apps.discord_bot.main`)
- Slash commands synced (restart / global sync as you usually do)
- Access to a guild channel **and** a DM with the bot
- Optional: an account **without** a `players` row to test Getting Started emphasis

## Unit checks (fast)

```bash
pytest tests/test_help_hub.py -q
```

Expect:
- Catalog contains exactly the nine required topic IDs
- `resolve_docs_url(None/"")` → `https://www.jotbird.com/app`
- Command-list formatter chunks / labels restricted entries correctly (pure fixtures OK)

## Discord smoke

### A — Hub navigation (guild, ephemeral)

1. In a server channel: `/help`
2. Confirm **only you** see the reply
3. Tap **Battle** → topic embed with Back + Read More
4. Tap **Back** → hub returns
5. Tap **Full Documentation** → opens `https://www.jotbird.com/app`
6. Open every other category once; each has substantive text (Commands = harvested list)

### B — Topic shortcut

1. `/help topic:league` (via autocomplete)
2. Lands on League topic; Back → hub
3. `/help topic:not-a-real-topic` → soft recovery (hub or clear error), no traceback

### C — Commands harvest

1. Open **Commands Reference**
2. Confirm `/help`, `/squad`, `/development`, `/store`, `/marketplace`, `/battle …`, `/admin` (marked Admin/owner only) appear consistent with Discord’s command list

### D — Unregistered emphasis

1. With a user that has no club: `/help`
2. Hub emphasizes Getting Started / `/register`
3. Other categories still work

### E — DM

1. DM the bot: `/help`
2. Help appears in the DM (not “ephemeral invisible”)
3. Category buttons still work

### F — Fail-open / stale view

1. Stop the bot, leave an old help message, restart, click a button → friendly “run `/help` again” (or disabled controls), no crash
2. Optional: break DB briefly and `/help` still shows static hub

## Done when

- [ ] Unit tests green
- [ ] Smoke A–E pass
- [ ] `change_log.md` notes `/help` for players
- [ ] No new migration; no economy/XP side effects from help
