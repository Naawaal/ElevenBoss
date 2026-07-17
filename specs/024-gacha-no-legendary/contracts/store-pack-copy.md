# Contract: Store pack copy

**Feature**: `024-gacha-no-legendary`  
**Surface**: `/store` hub — Daily Gacha Pack field (+ claim result embeds unchanged except rarity of drops)

## Required copy change

Daily Gacha Pack field MUST state that packs drop **Common / Rare / Epic** only (Epic is max), e.g.:

```text
Claim a free pack of 5 random players (Common / Rare / Epic — no Legendary).
Odds ~60% / 30% / 10%. Claimable every 22 hours.
```

Exact wording may vary; must not promise Legendary from packs.

## Unchanged

- `gacha_claim_embed` may still map Legendary emoji for display if a card somehow had that rarity (should not occur from packs); owned-card UIs keep Legendary styling.
- Support thank-you Legendary DM/hub copy stays on `/development`, not Store.

## Grep targets after ship

Player-facing pack odds strings in `store_cog.py`, `change_log.md`, `.specify/specs/v1.0.0/spec.md` — no “Legendary 2%” pack claim.
