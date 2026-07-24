# ElevenBoss — Full Documentation

Player guide for ElevenBoss on Discord.  
In Discord, run **`/help`** for the interactive hub. Extended reading lives at [https://share.jotbird.com/bright-serene-sandia](https://share.jotbird.com/bright-serene-sandia).

> **Note:** Exact coin costs, energy rates, and caps can be tuned by ops. Prefer the in-bot hubs for live numbers. This guide describes **how systems work**, not every formula constant.

---

## Table of contents

1. [Getting Started](#1-getting-started)
2. [Core Loop](#2-core-loop)
3. [Battle & Matches](#3-battle--matches)
4. [Squad & Formation](#4-squad--formation)
5. [Training & Development](#5-training--development)
6. [Evolutions](#6-evolutions)
7. [League System](#7-league-system)
8. [Economy, Store & Marketplace](#8-economy-store--marketplace)
9. [Hospital & Fatigue](#9-hospital--fatigue)
10. [Youth Academy](#10-youth-academy)
11. [Profile & Player Cards](#11-profile--player-cards)
12. [Leaderboards](#12-leaderboards)
13. [Commands Reference](#13-commands-reference)
14. [Tips & FAQ](#14-tips--faq)

---

## 1. Getting Started

### Register your club

1. Join a Discord server where ElevenBoss is installed.
2. Run **`/register`**.
3. Create your club and receive a **starting squad**.

You need a registered club before most hubs work (`/squad`, `/battle`, `/store`, `/development`, `/marketplace`, `/league`, etc.).

### First hour checklist

| Step | Command | Why |
|------|---------|-----|
| 1 | `/register` | Create club + starter squad |
| 2 | `/squad` | Set formation and starting XI |
| 3 | `/battle` | Play a Bot Battle (earn XP/coins) |
| 4 | `/store` | Claim daily login; learn energy refills |
| 5 | `/development` | See drills, Recover, skills |
| 6 | `/help` | Keep this guide handy in Discord |

### Need help in Discord?

- **`/help`** — interactive categories (ephemeral in servers; works in DMs too)
- **`/help topic:getting-started`** — jump straight to a section

---

## 2. Core Loop

ElevenBoss is built around a simple loop:

```text
Energy → Matches / Training → XP & Coins → Level-ups & Skill Points → Stronger squad → Better results
```

### Action energy

- Most competitive actions spend **action energy**.
- Energy **regenerates over time**.
- On **`/store`**, vote on Top.gg for your free pack, then **purchase energy refills** from the same Store whenever you’re short (refills grey out when energy is already full or near the cap).

### Matches

- Play **Bot Battles** and **Friendlies** from **`/battle`**.
- League fixtures resolve through **`/league`**.
- Matches grant **XP** and **coins**, and apply **fatigue** (and sometimes injuries).

### Growth

- Cards earn **XP** → **level up**.
- Level-ups unlock **skill points** you allocate under **`/development`**.
- Each card has **Overall (OVR)** and **Potential (POT)** — you grow toward POT, not past it via normal allocation.

### Fitness & depth

- Starters tire; rotate, **Recover**, and use the bench.
- Injured players go through the **Hospital** path.
- A deep roster beats an all-star XI that can’t stay fit.

---

## 3. Battle & Matches

### Battle hub

Open **`/battle`** for the Competitive Battle Arena.

Matches use your **saved starting XI and formation** from **`/squad`**. Fix an invalid squad before kickoff.

### Bot Battles

- Challenge a bot opponent from the battle hub.
- Costs action energy.
- Pays XP/coins on settle.
- Applies match fatigue to participants.

### Friendly Matches

- Challenge another manager with **`/battle friendly`** (mention an opponent).
- Useful for testing tactics and squads without league stakes.

### Ranked

**Coming soon.** Ranked matchmaking is not live yet — use Bot Battles and Friendlies for now.

### Live pitch & commentary

During a match you get:

- A **live pitch visual**
- **Commentary** / progress updates
- Injury prompts when relevant
- Final scoreline and settlement (XP, coins, fatigue)

### Match engine notes (ops-gated)

When Match Engine V3 flags are enabled for a match type, you may see richer tactical windows and a short **“How it was decided”** post-match summary. Until flags are on for that mode, classic simulation still applies. Ask your server ops / patch notes (`change_log.md`) for current rollout status.

---

## 4. Squad & Formation

### Squad hub

**`/squad`** is your Unified Squad Management Hub:

- View roster
- Set **formation**
- Build and **save** the starting XI
- Swap players (with compare visuals where available)

Save a **full valid 11** before important matches.

### Formations

Supported shapes include:

| Formation | Typical band mix (GK / DEF / MID / FWD) |
|-----------|----------------------------------------|
| **4-4-2** | 1 / 4 / 4 / 2 |
| **4-3-3** | 1 / 4 / 3 / 3 |
| **4-2-3-1** | 1 / 4 / 5 / 1 |
| **3-5-2** | 1 / 3 / 5 / 2 *(wingbacks count as MID)* |
| **5-3-2** | 1 / 5 / 3 / 2 |

Pick the shape that fits your **best available depth**, not just your favorite tactics poster.

### Pitch visual & swaps

- The pitch shows who occupies each slot.
- Empty or wrong-band slots can weaken performance or block kickoff.
- Swap Compare shows side-by-side attributes when choosing who goes out/in.

### Squad validity

Retirement, injuries, or incomplete saves can leave the squad invalid. The bot will tell you when you need to promote/replace before matches.

---

## 5. Training & Development

### Development hub

**`/development`** covers progression:

- Training **Drills**
- **Recover** (fitness)
- **Fusion** (fodder training)
- **Evolutions**
- **Skill allocation**
- **Mentor** transfer
- Claiming certain rewards / gifts when available

Daily login and energy refills are on **`/store`**, not Development.

### Drills

- Grant **XP** and a soft-capped **attribute boost** when rules allow.
- Consume energy.
- Respect **daily caps** (per card and per club).
- Boosts stop when attributes / projected OVR hit caps (XP/costs may still apply depending on the action).

### Skill points

- Earned from leveling.
- Spend under **Allocate Skills**.
- **POT caps** still apply — you cannot freely push every attribute forever.

### Mentor transfusion

- Potential-maxed veterans can convert surplus skill points into **youth XP**.
- Club/day limits apply — follow the hub prompts for the current conversion rate and caps.

### Fusion

- Train a main card with fodder players (coin cost applies).
- Grants fusion XP through the normal XP pipe; respect daily fusion caps.

### Recover

- **`/development` → Recover`** restores fitness for selected players.
- Costs energy per player in the batch.
- Does **not** consume drill slots.
- Prefer Recover when your XI is gassed but you still want to play.

---

## 6. Evolutions

Evolutions are managed under **`/development` → Evolutions**.

### How tracks work

1. Browse available **tracks** for eligible players.
2. Review **requirements** (matches, drills, and similar goals) and **rewards**.
3. **Start** a track when eligible (costs/progress shown before confirm).
4. Complete objectives while the track is active.
5. **Claim** stage rewards when ready.

### Tips

- You can start an evolution on a player already in your **Starting XI** and keep them there while the track runs.
- Play the match types the track asks for (bot/league, etc.).
- Unfinished tracks remain visible on the hub until completed or otherwise cleared by the system rules shown in-bot.

---

## 7. League System

### League hub

**`/league`** (and related subcommands) cover:

- Season status
- Standings
- Fixtures / matchdays
- Registration windows when open

### Registration & divisions

- Join when registration is open.
- Clubs are placed into **divisions**.
- Results influence standing and future placement across seasons.

### Matchdays & automation

- Fixtures resolve on the league schedule.
- **Auto-sim** can settle overdue matches so seasons don’t stall.
- Keep a **valid XI** ready before kickoff.
- **Pause / resume** may apply during bot downtime; opening the hub can help unstick a stranded pause when automation is healthy.

### Rewards

Match and season outcomes pay **coins** and **XP** through the normal economy and progression systems. Check the hub for your current season state and upcoming fixtures.

### Leaderboard vs league

**`/leaderboard`** Season views should track the same active season context as the league hub. Use Matchday / Season tabs as labeled in the bot.

---

## 8. Economy, Store & Marketplace

### Currencies

| Currency | Role |
|----------|------|
| **Coins** | Main economy — refills, marketplace, fusion sinks, facilities |
| **Gems (tokens)** | Shown on store/profile when available for gem sinks/features |

All coin changes go through the game’s economy systems — hubs never silently invent balances.

### Store — `/store`

- **Daily login** bonus (streak-aware; once per UTC day)
- **Vote on Top.gg** → claim your **free pack** (rarity mix has **no Legendary** from the standard daily pack)
- **Purchase energy refills** from the same hub after voting (or anytime you’re low on ⚡ — daily purchase tiers; blocked when full / near-full)
- **Club Facilities** — Youth Academy, Training Ground, Hospital, etc.

### Marketplace — `/marketplace`

Areas typically include:

| Area | Purpose |
|------|---------|
| **Transfer Board** | Browse/buy player-to-player listings |
| **My Listings** | Manage your asks and expiry |
| **Agent Sale** | Instant sell offers (daily caps apply) |
| **Scouting** | Scout / shortlist / sign flows where enabled |

#### Buying & listing

- Listings show ask price, time remaining, and card facts (OVR, rarity, etc.).
- **Fair value** and **price discovery** (recent similar sales / trend) appear when enough real market data exists.
- If data is thin, the bot says so — it does **not** invent averages.
- Purchase/list confirms show tax/net cues where applicable.
- **Career trail** can show prior owning clubs for a card.

#### Integrity

- Purchases settle atomically (one buyer wins).
- Ownership and locks prevent double-sell exploits.
- Always read the confirm screen before you commit.

---

## 9. Hospital & Fatigue

### Fatigue

- Matches drain **fitness / fatigue**.
- Low fitness hurts on-pitch performance.
- Bench players generally recover differently than starters.
- Use **`/development` → Recover`** for active recovery.
- **Daily passive recovery** also applies for eligible cards (hospital patients follow hospital rules).

Intensity / division context can change drain and recovery rates — treat hub copy as authoritative for your club’s current tier.

### Injuries

- Players can be injured in matches.
- Injured cards may be **admitted** to Hospital.
- Recovery time depends on **severity** and **Hospital facility level**.
- The Hospital board can show admitted names visually when you manage patients.

### Facility upgrades

Upgrade Hospital (and related facilities) from **`/store` → Club Facilities** to improve recovery speed / capacity where the hub allows.

---

## 10. Youth Academy

Youth Academy is part of club facilities and profile/academy flows:

- Academy **slots** scale with facility level.
- Prospects can **grow** over time and be **promoted** when ready.
- Scouting shortlists / sign flows may appear under profile or marketplace scouting (follow in-bot buttons).
- Mentor transfusion is one way maxed seniors feed youth XP (see Development).

Use **`/profile`** / academy buttons and **`/store` facilities** for the live controls.

---

## 11. Profile & Player Cards

### Club profile — `/profile`

Typical contents:

- Club identity and balances
- Finances / soft summaries
- Hospital entry points
- Academy management
- Other club-level status

### Player profile — `/player-profile`

Inspect a card’s:

- Attributes (PAC / SHO / PAS / DRI / DEF / PHY, etc.)
- OVR / POT / level / XP
- Contract / wage information when contracts are live
- Progression and state (training, hospital, academy, retired, etc.)

Use this before marketplace buys, evolution starts, or skill allocation.

---

## 12. Leaderboards

**`/leaderboard`** shows competitive rankings (e.g. Matchday / Season / other tabs as offered).

- Season tabs should align with the active league season.
- Weekly or seasonal claim buttons may appear when you qualify — follow the hub.

---

## 13. Commands Reference

Slash commands sync with the live bot. The authoritative list is always:

**`/help` → Commands**

Below is a stable overview of the main player-facing commands (subcommands may expand over time):

| Command | What it does |
|---------|----------------|
| `/help` | In-Discord guide (optional `topic` autocomplete) |
| `/register` | Create your club and starting squad |
| `/squad` | Formation, XI, swaps, pitch |
| `/battle` | Battle hub (Bot Battles, etc.) |
| `/battle friendly` | Challenge another manager |
| `/development` | Drills, Recover, fusion, evolutions, skills, mentor |
| `/store` | Daily login, Top.gg vote → free pack, **buy energy**, facilities |
| `/marketplace` | Transfer Board, agent, scouting, listings |
| `/league` | Season, standings, fixtures |
| `/profile` | Club profile & related hubs |
| `/player-profile` | Deep card inspection |
| `/leaderboard` | Rankings |
| `/admin` | **Bot owner / admin only** |

> Admin-only commands still appear in `/help` → Commands with an **Admin/owner only** note so server owners can discover them.

---

## 14. Tips & FAQ

### Energy ran out mid-grind

Open **`/store`**: vote on Top.gg for your free pack when available, and **buy an energy refill** from the same Store hub. Or wait for regen. Don’t buy a refill when the button says energy is already full / near maximum.

### My squad won’t start a match

Open **`/squad`**, fill 11 valid slots for your formation, save, and check for hospital/retired blockers.

### Should I play injured or tired stars?

Usually no — Recover, rotate, or wait. Pushing exhausted stars risks worse performances and more injuries.

### Where do I claim level rewards if DMs are off?

Use the **Claim** affordances on **`/development`** (and related claim buttons). Don’t rely only on DMs.

### Marketplace price looks wrong

Check **fair value** and **discovery** on the listing. If the bot says data is insufficient, price discovery is incomplete — not a fake “recommended price.”

### Ranked isn’t available

Correct — Ranked is **coming soon**. Use Bot Battles and Friendlies.

### Something looks stuck in League (Paused)

Open **`/league` hub**. Automation may resume play and extend windows after downtime. If it stays broken, contact server ops.

### Best way to learn the bot

1. `/help`  
2. Play one Bot Battle  
3. Open `/development` and `/store` once each  
4. Skim this document’s section for the system you’re stuck on  

---

## Document info

| Field | Value |
|-------|--------|
| Product | ElevenBoss |
| Companion in Discord | `/help` |
| Web entry | [https://share.jotbird.com/bright-serene-sandia](https://share.jotbird.com/bright-serene-sandia) |
| Patch notes | Repo root `change_log.md` |
| Maintainer tip | Keep this file aligned with `/help` catalog topics when systems change |

*End of guide.*
