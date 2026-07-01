# Milestone — DM-Only Admin Settings Console

This milestone consolidates bot administrative configurations and emergency override commands into private DM controls, removing them from guild-level slash command list pickers.

## Strategic Direction
* **Server slash commands:** Dedicated solely to gameplay (`/register`, `/club`, `/squad`, `/lineup`, `/fixtures`, `/table`, `/match`, `/help`).
* **Bot DM commands:** Dedicated to admin/server settings and overrides (`/settings`, `/admin`).

---

## Command Context Restrictions
`/settings` and `/admin` are registered with DM contexts using:
```python
@app_commands.allowed_contexts(guilds=False, dms=True, private_channels=True)
```
This restricts command visibility and prevents them from appearing in normal guild/server slash command picks.

---

## Multi-Server Discoverability Flow
Since a user in a DM context could manage multiple servers, the console implements a dynamic server discovery and selection flow:
1. **DM Command `/settings` or `/admin`** is received.
2. **Discover manageable servers:** The bot scans all connected servers where it is installed.
3. **Revalidate user permission:** For each server, the bot checks if the user is a Discord Administrator or has the configured ElevenBoss Admin role.
4. **Server Picker UI:**
   * If **no servers** are manageable, show a clean permission denied message.
   * If **exactly 1 server** is manageable, skips picker and goes directly to overview dashboard.
   * If **multiple servers** are manageable, renders a V2 select dropdown menu listing the servers.

---

## Components V2 DM Settings UI
Admins interactively configure their servers using select menus:
* **Channels Setup:** Separate game channel and announcement channel select dropdowns populated with compatible text channels from the target guild.
* **Admin Role Setup:** Configuration dropdown menu populated with guild roles, including a "Clear Admin Role" option. Only Discord Administrators can edit this role.
* **Automation Setup:** View auto-join, auto-start, and registration deadlines.
* **Schedule Setup:** Toggle cron scheduling state and set days/time/timezones.
* **Admin Overrides:** sim matchday, check loop state, and manually force start leagues privately from DMs.
