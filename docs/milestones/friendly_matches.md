# Milestone — Friendly Matches & Practice AI Mode

This milestone implements in-memory, transient friendly matches against friends and practice AI difficulties.

---

## Key Features

### 1. Challenge Friends (`/friendly challenge opponent:@User`)
Allows managers to challenge other registered managers in the server:
- Both challenger and opponent must have registered clubs in the same server.
- The challenge invitation card is posted publicly in the channel.
- A 15-minute `UiSession` is created, owned strictly by the opponent.
- Only the opponent manager is allowed to click **⚔️ Accept Challenge** or **❌ Decline**.
- Challenging a manager triggers a 5-minute challenger cooldown to prevent spam.

### 2. Practice AI Mode (`/friendly practice`)
Allows managers to immediately practice and test lineups against 5 bot difficulty levels:
1. **Beginner Bot FC** (50-59 OVR)
2. **Amateur United** (60-69 OVR)
3. **Professional City** (70-79 OVR)
4. **World Class Stars** (80-89 OVR)
5. **Legendary Eleven** (90-95 OVR)
- Selection is performed using a Discord Components V2 dropdown select menu.
- Only the command owner can select options.

### 3. In-Memory Purity & Double-Accept Protection
- **No Database Side-Effects**: Results are simulated in-memory and not written to fixtures, match results, or events tables. No changes are written to player growth, stats, or fitness/sharpness.
- **Lineup Resiliency**: If a club has no valid/saved lineup, the service builds a fallback starting XI in-memory using the club's available squad players (without modifying database state).
- **Transient Bot Generation**: AI bot teams are generated entirely in-memory as DTO inputs, ensuring zero DB impact.
- **Accept State Lock**: The UI session status transitions dynamically (`pending` -> `simulating` -> `completed`). Subsequent accept interaction clicks are rejected to prevent double-simulation.

---

## Code Base Additions

- **[`app/services/friendly_service.py`](file:///d:/Python/Discord%20Bots/ElevenBoss/app/services/friendly_service.py)**: DTO definition, in-memory bot team generators, lineup fallbacks, and match engine bridging.
- **[`app/ui/layouts/friendly.py`](file:///d:/Python/Discord%20Bots/ElevenBoss/app/ui/layouts/friendly.py)**: V2 invite card, practice difficulty select menu, and retro friendly match report view.
- **[`app/ui/handlers/friendly_handler.py`](file:///d:/Python/Discord%20Bots/ElevenBoss/app/ui/handlers/friendly_handler.py)**: Challenge invitations, decline handlers, session validators, state-lock transitions, and practice selections.
- **[`app/cogs/friendly_cog.py`](file:///d:/Python/Discord%20Bots/ElevenBoss/app/cogs/friendly_cog.py)**: `/friendly challenge` and `/friendly practice` commands registration.
- **[`app/ui/custom_ids.py`](file:///d:/Python/Discord%20Bots/ElevenBoss/app/ui/custom_ids.py)**: Scope and action whitelists registration.
- **[`app/cogs/club_cog.py`](file:///d:/Python/Discord%20Bots/ElevenBoss/app/cogs/club_cog.py)**: Integrated dispatch routing for `friendly` scope click/select interactions.
