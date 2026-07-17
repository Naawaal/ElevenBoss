# Contract: Select Empty-State UX

**Feature**: `022-v1-stability-blueprint`  
**Maps to**: Spec H1, User Story 3, SC-007

## Discord constraint

A Select component **must** have 1–25 options. Building `discord.ui.Select(..., options=[])` is invalid / disappears. Hubs that rebuild after the last item is removed currently drop the Select with little or no copy — perceived as “SelectMenu disappearance.”

## Required behavior

After any hub refresh where a former Select’s option list is empty:

1. **Do not** attach a Select for that list.
2. **Do** show clear empty-state text on the embed (field or description line), e.g. “No patients to discharge.” / “No transfer listings match your filters.”
3. **Do** keep a recovery control: **Back** button and/or instruction to re-run the slash command.
4. Filter controls (when present) should remain so the manager can change bands without restarting the whole marketplace flow when possible.

On view **timeout**: disable children and/or message “Session expired — run `/…` again” (existing `disable_view_on_timeout` may be extended with copy).

## Shared helper (design)

Prefer one helper in `apps/discord_bot/core/view_helpers.py`, e.g.:

- `add_select_if_options(view, *, placeholder, options, row, callback)` — no-op when `not options`
- Optional: `empty_state_embed_line(label: str) -> str` for consistent wording

Call sites to audit first (priority order):

1. `views/store_facilities.py` (hospital admit/discharge)
2. `views/academy_hub.py`
3. `views/marketplace_transfer.py` (browse / my listings / filters)
4. Other `discord.ui.Select` builders under `apps/discord_bot/views/` found by grep

## Acceptance

| Scenario | Pass |
|----------|------|
| Last hospital patient discharged | Embed says empty; Back works; no blank select strip unexplained |
| Academy with zero prospects | Empty copy + recovery |
| Transfer filter → 0 results | Empty copy; Change Filters / Back available |
| Hub timeout then click | Friendly expired / re-run message |

## Non-goals

- Persistent views for ephemeral personal hubs
- Replacing Select with Modals for free-range filters (already out of transfer v1 scope)
