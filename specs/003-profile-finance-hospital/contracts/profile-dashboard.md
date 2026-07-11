# Contract: Profile dashboard embed + hub

## Surface

- **Command**: existing `/profile` (no new slash command)
- **Entry**: `show_profile(interaction, owner_id)` → ephemeral embed + `ProfileHubView`
- **Files (planned)**: `profile_cog.py`, `embeds/profile_embeds.py` (optional)

## Embed sections (order guidance)

1. Title: `Club Profile: {club_name}` (keep existing shield emoji / color language)
2. Manager / username (existing)
3. **Club Finance** — coins + gems (`tokens`); optional compact emphasis line
4. **Hospital** — per [data-model.md](../data-model.md) state rules
5. Action energy (existing sync + format helpers)
6. Global / server division, LP, weekly tiers, rankings blurb (existing)
7. Match record + trophy cabinet (existing)
8. Footer: leaderboard hint + store daily bonus; may mention hub actions briefly

## Buttons (`ProfileHubView`)

| Label | Style cue | Behavior |
|-------|-----------|----------|
| Manage Hospital | 🏥 | `show_hospital_panel(..., origin="profile")` |
| Finances | 💰 | Finance detail panel; Back → `show_profile` |
| View Club Stats | 📊 | `show_squad_hub` (edit message + pitch) |

## Guarantees

- Defer before DB work (slash and button paths that hit DB).
- Owner-only interactions.
- Re-entering `show_profile` always re-fetches coins, `hospital_level`, and active patients.
- Hospital query failure must not blank the whole embed (section fallback copy).
- No new slash commands.

## Non-goals

- Transaction ledger on the main embed
- Removing league/trophy fields
