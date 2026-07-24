# Contract: Commands Reference Harvest

**Feature**: `046-help-hub`  
**Consumers**: Commands topic embed builder

## Source of truth

At Commands topic render time, walk the bot’s application command tree:

```text
for command in bot.tree.walk_commands():
    emit CommandEntry(qualified_name, description, restricted)
```

Include **leaf** slash commands and **group subcommands** (e.g. `battle bot`, `battle friendly`, `league …`). Do not hand-maintain a parallel name list in the catalog.

## Restriction labeling

Mark `restricted=True` when any of:

- Command has non-empty `default_permissions` that gates ordinary members, or
- Command has custom `checks` (e.g. owner-only `/admin`)

Display: append a clear `Admin/owner only` (or equivalent) note on that line. **Do not hide** restricted commands.

## Presentation

- Compact `/{qualified_name} — {description}` lines (description truncated if needed for Discord limits).
- If empty description: show a neutral placeholder, not blank silence.
- If walk yields zero commands: show a calm empty state (“Commands unavailable — try again after the bot finishes syncing.”), not a crash.
- Prefer single embed with description and/or a few fields; add simple Prev/Next **only** if length limits are exceeded.

## Non-goals

- Do not sync or rewrite Discord’s command registration from help.
- Do not call Discord REST for command list if the in-memory tree is available.
- Do not require DB for this topic.
