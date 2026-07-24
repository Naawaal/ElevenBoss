# Contract: Hospital Admitted Visual

**Feature**: `042-ux-visual-refinements` | **Surface**: `/profile` → Manage Hospital (and Facilities → Hospital)

## Asset

| Property | Value |
|----------|-------|
| Path | `assets/admited.png` (filename typo preserved) |
| Size | 1536×1024 |
| Role | Base clipboard / lined patient board |
| Visual row capacity | **6** overlays max |

## Renderer (`apps/discord_bot/core/hospital_board.py`)

```text
generate_hospital_board(patients: list[dict]) -> discord.File | None
# filename when present: hospital_board.png
```

| Case | Result |
|------|--------|
| Asset readable | `discord.File` with up to 6 name lines drawn on lined rows (empty rows blank for empty hospital) |
| Asset missing/corrupt | `None` |

**Row text (minimum)**: player name. Optional short severity; full ETA stays in embed field (existing `hospital_panel_embed` patient lines).

**Overflow**: `patients[6:]` only in embed text (FR edge case).

## Panel wiring (`show_hospital_panel`)

1. Fetch player / patients / waiting (unchanged queries).
2. `file = await generate_hospital_board(patients)`.
3. `embed = hospital_panel_embed(...)`; if `file`: `embed.set_image(url="attachment://hospital_board.png")`.
4. Edit/send with `attachments=[file]` when file present; else text-only as today.
5. Admit / discharge / upgrade already refresh this function → visual stays current.

## Guarantees

- Waiting (no bed) field remains in embed.
- Empty admitted → empty board image + “*No one admitted.*” text.
- No new slash command; no hospital math/RPC changes.
- Upgrade / admit / discharge buttons unchanged aside from refreshed attachment.

## Non-goals

- Animations, per-bed clickable regions, scrolling inside the PNG.
- Renaming `admited.png` (optional later cleanup).
