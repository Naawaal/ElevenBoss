# Contract: Remove `/club-finances` slash command

**Feature**: `010-recovery-energy-cleanup`  
**File**: `apps/discord_bot/cogs/economy_cog.py`

## Delete

- `@app_commands.command(name="club-finances", ...)` handler and its method body

## Keep

- `build_club_finances_embed`
- `fetch_club_finances_embed`
- `show_club_finances_panel`
- `ClubFinancesPanelView`
- Cog `setup` / load in `main.py` (Profile Finances imports these)

## After deploy

Discord command sync must not re-register `club-finances`. Profile **💰 Finances** still opens the panel.
