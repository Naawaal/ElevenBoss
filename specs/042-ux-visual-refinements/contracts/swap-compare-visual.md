# Contract: Swap Compare Visual

**Feature**: `042-ux-visual-refinements` | **Surface**: Squad hub → Swap Players

## Renderer (`apps/discord_bot/core/swap_compare.py`)

```text
generate_swap_compare_image(
  out_card: dict | None,
  in_card: dict | None,
) -> discord.File   # filename: swap_compare.png
```

Layout: two columns — **OUT** (left) / **IN** (right). Each column is a card panel:

| Element | Behavior |
|---------|----------|
| Header | `OUT` / `IN` |
| Empty side | Placeholder text (“Select starter…” / “Select reserve…”) |
| Filled side | Name, position, OVR; rarity border if known; attr lines when keys present |

Reuse visual language from roster grid (dark panel, rarity outline, Roboto fonts under `assets/fonts/`).

## View wiring (`SquadSwapView`)

| Event | Behavior |
|-------|----------|
| Open swap | Build image from current selections (usually both null → dual placeholders); `edit`/`send` with `attachments=[file]`, `embed.set_image(url="attachment://swap_compare.png")` |
| Bench select | Clear incompatible reserve as today; regenerate image; `edit_message(embed, view, attachments=[file])` |
| Reserve select | Regenerate; edit |
| Confirm / Back | Existing flows; hub restores pitch attachment on Back |

## Guarantees

- Dual selects + Confirm gating **unchanged** (`_swap_selection_ready`, eligibility filters).
- Zero eligible reserves: Confirm disabled; IN column placeholder / empty messaging; no fabricated partner.
- Image is advisory only — never the sole confirm gate.

## Non-goals

- Pitch-highlight alternate in v1.
- Replacing select menus with image maps.
- Changing `swap_squad_players` RPC.
