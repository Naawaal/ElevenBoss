# Contract: Hospital / Profile / Pre-Match UI

**Feature**: `016-tier-fatigue-rebalance`  
**Surfaces**: `/store` → Facilities Hospital; `/profile` injury lines; `/battle` pre-match ticket  
**No new slash commands**

## 1. Hospital panel (`hospital_embeds.hospital_panel_embed`)

Add intensity context under the title / description, driven by `players.intensity_tier` (+ optional division name):

```text
🏥 Hospital — Level {H}/{max}
⚠️ League Intensity: {Low|Medium|High} ({Division})
{Tier 3 only example:} Base recovery times are longer than lower leagues.
🛏️ Beds: … · Recovery: {mult}× …
```

Tier 1 must not show the “High / longer than lower leagues” warning.

## 2. Injury report (profile)

When a card is injured (hospital or untreated), show:

```text
🔴 INJURED: {Minor|Moderate|Major} ({optional type label if already shown})
📅 Expected Return: {eta}
(Base: {untreated_or_tier_base_days}d @ {Division/Tier label} | Facility Bonus: −{pct}%)
```

Facility bonus % = `round((1 - hospital_recovery_multiplier(H)) * 100)` when in hospital; untreated shows Facility Bonus 0% / “untreated”.

No fake injury block when healthy.

## 3. Pre-match warning (`/battle` competitive ticket)

If count of starters with `fatigue < 30` is ≥ 1:

```text
⚠️ Warning: {N} players are heavily fatigued. High risk of injury.
```

Advisory only — must not block match start. Omit when N = 0. Friendliest/sandbox flows that skip fatigue persistence do not need the warning.

## Copy helpers

Prefer small pure or embed-local helpers for labels/pct so cogs stay thin; no Discord imports in `packages/`.
