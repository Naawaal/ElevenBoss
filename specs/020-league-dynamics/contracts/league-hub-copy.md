# Contract: League Hub & Announcement Copy

**Feature**: `020-league-dynamics`  
**Surfaces**: `/league hub`, season start announcement, matchday reminders, Journal — **no new slash commands**

## Hub (Dynamics season)

- Deadline: show midnight UTC close using Discord timestamp (`window_end`), copy like **“Play before 00:00 UTC”** / relative `<t:…:R>`.
- Show **Seasonal Division N** (or “Division N”) for the viewer’s `division_tier`.
- If weekly rank shown elsewhere, label it **Weekly Rank** — never identical bare “Division” collision without qualifier.
- Matchday field: `Matchday X of 14` under Dynamics.

## Hub (Legacy)

- Keep existing rolling-window countdown copy.

## Season start announcement

When Dynamics:

- State **14-day** season, **daily midnight UTC** deadline, auto-sim after midnight.
- If multiple tiers: list club counts per Division 1 / 2 / ….
- Remind MoMD: biggest **manual** win that matchday earns coin bonus (amount from config).

## Reminders

- Existing 6h-before-`window_end` DM path works once Dynamics uses midnight `window_end`.
- Dedup table unchanged; ensure one DM per human per matchday.

## MoMD Journal line (example tone)

`🏅 Manager of the Matchday: **Club Name** (3–0) — +2,000 coins`

Skip entirely when no award.
