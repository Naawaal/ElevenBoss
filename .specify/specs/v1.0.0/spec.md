# ElevenBoss v1.0.0 — Specification (`spec.md`)

**Feature**: Core Game Loop — v1.0.0 Initial Release
**Status**: Draft
**Version**: 1.0.0

---

## Overview

ElevenBoss is a Discord-native football (soccer) manager game. Players build a squad, configure tactical formations, simulate matches, earn currency, and compete in weekly automated leagues — all through Discord slash commands. The v1.0.0 loop is a closed economy: claim packs → build squad → spend energy on matches → earn coins → upgrade players → climb leagues.

---

## User Stories

### US-01: User Registration — Interactive Onboarding Wizard

> **As a** new Discord user,
> **I want to** run `/register` to be guided through a cinematic, interactive onboarding flow,
> **So that** I feel invested in my club from the moment I start playing.

**Acceptance Criteria:**

#### AC-01a: Trigger & Guard

- **GIVEN** an unregistered user runs any game command other than `/register`,
- **THEN** the bot responds with an ephemeral embed: *"You don't have a club yet! Run `/register` to get started."* No account is created silently.
- **GIVEN** an already-registered user runs `/register`,
- **THEN** the bot responds with an ephemeral embed: *"You're already registered as Manager [manager_name] of [club_name]!"* No thread is created.

#### AC-01b: Thread Creation

- **GIVEN** an unregistered user runs `/register`,
- **WHEN** the command is processed,
- **THEN** the bot creates a **temporary Discord thread** off the channel where the command was invoked.
  - Thread name: `"⚽ ElevenBoss — Welcome, [Username]!"`
  - Thread type: `discord.ChannelType.private_thread` if the parent channel supports it (e.g., is a `TextChannel` in a guild with the `PRIVATE_THREADS` feature); otherwise fall back to a `public_thread`.
  - Auto-archive duration: **60 minutes** (used as the inactivity timeout).
- **AND** the bot sends an initial embed inside the thread with a `discord.ui.View` containing a **"Begin Setup →"** button.
- **AND** the bot responds to the original `/register` interaction with an ephemeral message linking to the thread: *"Your private setup room is ready: [thread link]"*.

#### AC-01c: Step 1 — Club & Manager Details (Modal)

- **GIVEN** the user clicks **"Begin Setup →"** inside the onboarding thread,
- **THEN** the bot presents a `discord.ui.Modal` with two text inputs:
  - **Club Name** (`TextInput`, required, max 32 chars, placeholder: *"e.g. FC Midnight"*)
  - **Manager Name** (`TextInput`, required, max 24 chars, placeholder: *"e.g. Sir Alex"*)
- **GIVEN** the user submits the modal,
- **THEN** the bot sends a **Confirmation embed** in the thread displaying the entered values with a `discord.ui.View` containing two buttons:
  - ✅ **"Confirm Club"** — proceeds to recruitment.
  - ✏️ **"Edit Details"** — re-opens the same Modal.
- **GIVEN** the user submits the modal with an empty required field,
- **THEN** Discord's built-in modal validation prevents submission (no custom handling needed).

#### AC-01d: Step 2 — Cinematic Marquee Signing Animation

- **GIVEN** the user clicks **"Confirm Club"**,
- **THEN** the Confirmation embed is updated (via `message.edit()`) to remove the buttons and enter the recruitment animation sequence.
- **AND** the bot performs the following sequential message edits with `asyncio.sleep()` delays to simulate a cinematic effect:

  | Step | Delay | Embed Content |
  |---|---|---|
  | 1 | 0s | `🔎 Scouting the transfer market for your Marquee signing...` |
  | 2 | 1.5s | `📋 Reviewing elite player dossiers...` |
  | 3 | 1.5s | `🤝 Initiating contract negotiations...` |
  | 4 | 1.5s | `❌ Rejected! Agent demands too high. Moving on...` |
  | 5 | 2.0s | `🤝 New target found. Making an offer...` |
  | 6 | 1.5s | `⏳ Waiting for a response...` |
  | 7 | 2.0s | `✅ SIGNED! Your club's Captain has arrived!` |

- **AFTER** step 7, the bot calls `gacha.generator.generate_starter_squad()` (see plan for spec) to generate the full 11-player squad.
  - The **Marquee Player** (index 0) is **Rare or Epic** rarity, drawn from the elevated pool.
  - The remaining **10 Youth Players** are all **Common** rarity, generated with a positional guarantee.
- **THEN** the embed is updated one final time to the **Marquee Reveal** embed, spotlighting only the Captain's full card (name, position, rarity ✨, overall rating).

#### AC-01e: Account Creation, Squad Auto-Assignment & Thread Cleanup

- **GIVEN** the animation completes and the Marquee Reveal embed is displayed,
- **THEN** the bot executes a **single atomic Supabase transaction** (`register_new_player` RPC) that:
  1. Inserts the `players` row: `discord_id`, `username`, `club_name`, `manager_name`, `coins = 500`, `energy = 100`, `division = "Grassroots"`.
  2. Inserts **11 `player_cards` rows** with the following positional guarantee:
     - **Slot GK (1):** The Marquee Player — `Rare` or `Epic` rarity, position `GK` OR any position (see note).

     > [!NOTE]
     > The Marquee Player's position is determined by the `generate_starter_squad()` output. The Marquee card takes the `gk` slot only if it is a GK; otherwise it fills its natural position slot and the GK slot is filled by a Common youth player. The squad's `formation = '4-4-2'` remains the invariant.

  3. Inserts the 11 cards with the following formation guarantee enforced by `generate_starter_squad()`:
     - `1 GK` (Common, unless Marquee is a GK)
     - `4 DEF` (Common)
     - `4 MID` (Common)
     - `2 FWD` (Common, unless Marquee is a FWD)
     - `1 Marquee` (Rare or Epic) — replaces the Common card in its positional slot.
  4. Inserts the `squads` row with `formation = '4-4-2'` **and** populates `gk`, `slot_1` through `slot_10` with the **UUIDs of the 11 inserted `player_cards` rows**, ordered by position (GK → DEF → MID → FWD).
- **AND** the bot sends a final **"Registration Complete"** embed containing:
  - The Marquee Player's card (name, position, rarity, overall).
  - The message: *"You've signed **[Marquee Name]** to lead your club, alongside 10 youth academy prospects! Your starting 11 has been auto-assigned in a 4-4-2 and is ready for the pitch."*
  - A quick-start tip: *"Use `/match play` to get started immediately, or `/squad view` to see your full squad."*
- **AND** the thread is **deleted** after a 10-second countdown: *"This setup room will close in 10 seconds..."*
- **GIVEN** the user does not interact with the onboarding thread for **60 minutes** (thread auto-archives),
- **THEN** no account is created. The thread auto-archives via Discord's native mechanism. No partial state is left in the database.
- **GIVEN** the atomic transaction fails at any point (e.g., DB constraint violation),
- **THEN** the entire transaction is rolled back — no partial player record, no orphaned player cards, no empty squad rows are left in the database.

#### AC-01f: Error States

- **GIVEN** any step in the wizard fails due to a bot error,
- **THEN** the thread sends an ephemeral-style error embed and is **deleted** after a 15-second delay to prevent orphaned threads.
- **GIVEN** a user tries to interact with an onboarding thread that belongs to a different user (e.g., another user in a public thread),
- **THEN** the `ThreadManager` validates `interaction.user.id == thread_owner_id` and responds with an ephemeral: *"This setup wizard belongs to another player."*

---

### US-02: Daily Gacha Pack Claim

> **As a** registered player,
> **I want to** claim a free player pack every 22 hours,
> **So that** I receive new players to build my squad without spending money.

**Acceptance Criteria:**
- **GIVEN** I am a registered player,
- **WHEN** I run `/gacha claim`,
- **THEN** the bot checks my last claim timestamp.
- **AND GIVEN** 22 hours have elapsed since my last claim (or I have never claimed),
- **THEN** I receive a pack of **5 randomised players** drawn from a weighted rarity pool (`Common 60%, Rare 30%, Epic 8%, Legendary 2%`).
- **AND** each player's overall rating is derived from their rarity tier (Common 50–64, Rare 65–74, Epic 75–84, Legendary 85–99).
- **AND** my `last_claim_at` timestamp is updated atomically in the same transaction.
- **GIVEN** fewer than 22 hours have elapsed since my last claim,
- **THEN** the bot responds with a cooldown embed showing the time remaining (`HH:MM:SS`), and NO players are awarded.

---

### US-03: Squad Management

> **As a** registered player,
> **I want to** view my full player roster and configure my starting 11 with a formation,
> **So that** I can optimise my team for matches.

**Acceptance Criteria:**
- **GIVEN** I run `/squad view`,
- **THEN** I see a paginated embed listing all players I own, with their name, position, rarity, and overall rating.
- **GIVEN** I run `/squad set-formation <formation>` (e.g., `4-4-2`, `4-3-3`, `3-5-2`),
- **THEN** the bot validates the formation string conforms to `\d-\d-\d` and sums to 10 (outfield) + 1 goalkeeper = 11 total.
- **AND** my squad formation is saved to the database.
- **GIVEN** I run `/squad set-player <slot> <player_id>`,
- **THEN** the specified player is placed in the specified slot, validated against their primary position.
- **AND** if the player is already in another slot, they are moved (not duplicated).

---

### US-04: Energy System

> **As a** registered player,
> **I want** my energy to regenerate passively over time,
> **So that** I am rewarded for returning to the game regularly without being locked out forever.

**Acceptance Criteria:**
- **GIVEN** a player's energy is below their maximum (`max_energy = 100`),
- **WHEN** the APScheduler energy regeneration job fires (every **5 minutes**),
- **THEN** all players with `energy < max_energy` receive `+2 energy` per tick, capped at `max_energy`.
- **GIVEN** a player checks `/profile`,
- **THEN** they see their current energy, max energy, and the estimated time to full regeneration.
- Energy is consumed when playing matches (see US-05).

---

### US-05: Play a Match

> **As a** registered player,
> **I want to** simulate a match against an opponent,
> **So that** I can earn coins and league points.

**Acceptance Criteria:**
- **GIVEN** I run `/match play` with a valid configured squad (>=11 players set),
- **WHEN** the command is processed,
- **THEN** the bot checks I have at least **10 energy**.
- **AND GIVEN** I have sufficient energy,
- **THEN** `10 energy` is deducted from my total (transactionally).
- **AND** the `match_engine` package simulates the match outcome:
  - Calculates **My Team Rating** = average overall rating of my starting 11 players.
  - Selects an **opponent** from my current division's opponent pool (AI team with division-calibrated rating).
  - Applies a **randomness modifier** (±15%) drawn from a normal distribution to both sides.
  - The higher modified rating wins. A draw occurs if the difference is within 3 points.
- **THEN** the result embed shows: final score (randomised goals consistent with outcome), my team rating vs opponent rating, coins earned, and league points earned.
- **Coin rewards**: Win = `150 coins`, Draw = `50 coins`, Loss = `0 coins`.
- **League points**: Win = `3 pts`, Draw = `1 pt`, Loss = `0 pts`.
- **GIVEN** I have fewer than 10 energy,
- **THEN** the bot responds with an ephemeral error embed showing current energy and time to next regen tick.

---

### US-06: Player Levelling (Progression)

> **As a** registered player,
> **I want to** spend coins to level up my players,
> **So that** my team's overall rating improves over time.

**Acceptance Criteria:**
- **GIVEN** I run `/player level-up <player_id>`,
- **WHEN** the command is processed,
- **THEN** the bot checks the level-up cost for this player: `cost = (current_level ^ 1.5) * 100` (rounded to nearest 10).
- **AND GIVEN** I have sufficient coins,
- **THEN** the coin deduction and player `level` increment are applied in a **single atomic transaction**.
- **AND** the player's overall rating increases by `+1` per level up to their rarity cap (Common max 75, Rare max 84, Epic max 90, Legendary max 99).
- **AND** the bot responds with a success embed showing: new level, new rating, coins spent, remaining coins.
- **GIVEN** I have insufficient coins,
- **THEN** the bot responds with an ephemeral error embed showing cost vs. current balance.
- **GIVEN** the player is already at their rarity rating cap,
- **THEN** the bot responds with an ephemeral error explaining the cap.

---

### US-07: Weekly League — Automatic Resets

> **As a** competitive player,
> **I want** the league to reset weekly with promotion/relegation,
> **So that** there is ongoing competitive pressure and a reason to keep playing.

**Acceptance Criteria:**
- **GIVEN** the weekly APScheduler job fires (every **Monday 00:00 UTC**),
- **WHEN** the reset runs,
- **THEN** the league table for each division is sorted by `league_points` descending, then by `goal_difference` as a tiebreaker.
- **AND** the **top 20%** of players in each division (minimum 1) are **promoted** to the next division tier.
- **AND** the **bottom 20%** of players in each division (minimum 1, not in the lowest division) are **relegated** to the division below.
- **AND** all players' `league_points` are reset to `0`.
- **AND** all players' `goal_difference` are reset to `0`.
- **THEN** each affected player receives a Discord DM notification (if DMs are enabled) informing them of their new division.

**Divisions (ascending)**:
`Grassroots` -> `Amateur` -> `Semi-Pro` -> `Professional` -> `Elite` -> `Legendary`

---

### US-08: Player Profile

> **As a** registered player,
> **I want to** view my full profile summary,
> **So that** I can track my progress at a glance.

**Acceptance Criteria:**
- **GIVEN** I run `/profile`,
- **THEN** I see an embed containing: **Club Name**, **Manager Name**, Discord username, current division, league points, coins balance, current energy / max energy, time to full energy, total matches played, win/draw/loss record.
- **GIVEN** I am not yet registered,
- **THEN** the bot responds with an ephemeral embed prompting me to run `/register`.

---

## Out of Scope for v1.0.0

- PvP matches (player vs. player in real-time).
- Trading players between users.
- Premium currency or monetisation.
- Web dashboard.
- Player positions enforcing positional penalties (v1.0.0 uses flat rating averages only).
