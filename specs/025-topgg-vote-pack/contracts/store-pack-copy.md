# Contract: Store Pack Copy (Vote Gate)

**Feature**: `025-topgg-vote-pack`  
**Files**: `apps/discord_bot/cogs/store_cog.py`, `apps/discord_bot/embeds/gacha_embeds.py`

## `/store` embed — Daily Gacha Pack field

**When available:**

```text
Vote on Top.gg, then claim a free pack of 5 random players (Common / Rare / Epic — no Legendary).
Odds ~60% / 30% / 10%. Available every 12 hours after your last claim.
🟢 Vote & claim available now!
```

**When on cooldown:**

```text
Vote on Top.gg, then claim a free pack of 5 random players (Common / Rare / Epic — no Legendary).
Odds ~60% / 30% / 10%. Available every 12 hours after your last claim.
⏳ Cooldown: **{hours}h {minutes}m** remaining.
```

## Button

| State | Label | Disabled |
|-------|-------|----------|
| Ready | `🗳️ Vote & Claim Free Pack` | false |
| Cooldown | `🗳️ Vote & Claim Free Pack` | true |

`custom_id` stays `store_gacha_claim` (no persistent view re-register).

## Vote prompt embed

**Title**: `🗳️ Vote Required`  
**Description**:

```text
To claim your free pack, vote for ElevenBoss on Top.gg first.

1. Click the link below to vote
2. Return here and click **Vote & Claim Free Pack** again

Vote link: {vote_url}
```

**Color**: `0xFFAA00` (amber)  
**Footer**: `Votes reset every 12 hours on Top.gg.`

## API unavailable embed

**Title**: `⚠️ Vote Verification Unavailable`  
**Description**:

```text
We couldn't verify your Top.gg vote right now. Please try again in a few minutes.

Your pack was **not** claimed.
```

**Color**: `0xE74C3C`

## Vote replay embed

**Title**: `🗳️ Vote Already Used`  
**Description**:

```text
This Top.gg vote was already used for a free pack. Vote again after your cooldown to claim another pack.
```

## Cooldown embed (update footer)

Change footer from `Pack refreshes every 22 hours.` to:

```text
Pack refreshes every 12 hours (requires a new Top.gg vote).
```

## Success embed

`gacha_claim_embed` title/description — **unchanged** (still "Free Daily Pack Claimed!").

## Must not

- Promise free pack without mentioning vote requirement
- Add new slash commands or hub buttons
- Show ops bypass flag in player UI
