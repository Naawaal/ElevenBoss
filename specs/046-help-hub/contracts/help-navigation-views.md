# Contract: Help Navigation Views

**Feature**: `046-help-hub`  
**Consumers**: `HelpHubView` / topic view callbacks

## Hub embed

Must include:
- Title identifying ElevenBoss Help
- Short intro (what `/help` is for)
- Optional Getting Started emphasis line when unregistered
- Compact list or field of categories (blurbs OK)
- Controls:
  - One button per required topic (emoji + short label)
  - One **Link** button: Full Documentation → `https://share.jotbird.com/bright-serene-sandia`

Button layout: ≤5 buttons per row (Discord limit).

## Topic embed

Must include:
- Topic title + substantive fields from catalog (or harvested commands for `commands`)
- Footer and/or **Link** button Read More → `resolve_docs_url(topic.docs_path)`
- **Back** button returning to the same-message Hub embed + hub view

## Interaction rules

| Rule | Requirement |
|------|-------------|
| Ownership | Ignore / soft-reject clicks where `user.id != owner_id` |
| Edit target | Prefer `interaction.response.edit_message` / edit original help message — do not spam new public channel messages |
| Timeout | On timeout, disable controls; subsequent use gets “run `/help` again” |
| Double-tap | Last successful edit wins; no channel clutter |

## Visual

- Embed color `0x00FF87` (bot green) unless error embeds use shared `error_embed`.
- Category emoji consistent between hub buttons and topic titles.
