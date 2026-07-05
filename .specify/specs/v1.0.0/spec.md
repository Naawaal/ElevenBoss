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

- **GIVEN** an unregistered user attempts to run any core gameplay command other than `/register` (e.g., `/match play`, `/gacha claim`),
- **THEN** the bot intercepts the request and returns an ephemeral error directing them to run `/register`: *"You don't have a club yet! Run `/register` to get started."* No account is created silently.
- **GIVEN** an already-registered user runs `/register`,
- **THEN** the bot responds with an ephemeral embed: *"You're already registered as Manager [manager_name] of [club_name]!"* No thread is created.

#### AC-01b: Thread Creation

- **GIVEN** an unregistered user runs `/register`,
- **WHEN** the command is processed,
- **THEN** the bot creates a **temporary Discord thread** off the channel where the command was invoked.
  - Thread name: `"⚽ ElevenBoss — Welcome, [Username]!"`
  - Thread type: `discord.ChannelType.private_thread` if the parent channel supports it (e.g., is a `TextChannel` in a guild with the `PRIVATE_THREADS` feature); if the server lacks private thread permissions, the bot will gracefully fall back to creating a public thread for the setup wizard.
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
  4. Inserts the `squads` row with `formation = '4-4-2'` and populates the `squad_assignments` junction table with the 11 inserted `player_cards` rows mapping to `position_slot` 1 through 11 (ordered GK → DEF → MID → FWD) subject to the `UNIQUE(discord_id, position_slot)` constraint.
- **AND** the bot sends a final **"Registration Complete"** message containing a list of two embeds using premium and clean aesthetics:
  - **Embed 1 (Captain Reveal / Welcome):** Gold/emerald branded welcome embed displaying the Marquee Captain's details, club details, and a quick-start tip: *"Use `/match play` to get started immediately, or `/squad-view` to see your full squad."*
  - **Embed 2 (Youth Academy Prospects):** A neutral light-gray list cleanly showing the 10 youth academy prospects with their positions and ratings (e.g., `🧤 GK - [Name] (64 OVR)`).
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
- **GIVEN** I run `/squad set-formation` (with no arguments),
- **THEN** the bot responds with an interactive View containing a Dropdown Menu listing available formations (`4-4-2`, `4-3-3`, `3-5-2`, `4-2-3-1`, `5-3-2`).
- **WHEN** I select a formation,
- **THEN** the bot saves the selected formation in the database and returns a success confirmation embed.
- **GIVEN** I run `/squad set-player` (with no arguments),
- **THEN** the bot responds with an interactive View containing two Dropdown Menus:
  - **Slot Dropdown:** Allows selecting a slot (1-11) in the active formation.
  - **Player Dropdown:** Starts disabled with a placeholder.
- **WHEN** I select a Slot from the first dropdown,
- **THEN** the bot queries my roster and updates the second dropdown to show a dynamically filtered list of my owned player cards matching the required position for that slot (GK, DEF, MID, or FWD), capped at 25 options.
- **WHEN** I select a player from the second dropdown,
- **THEN** the selected player card is transactionally assigned to the slot (removing any existing assignment for this card in other slots to avoid duplicates).

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

---

# ElevenBoss v1.1 Features

### US-05: Live Match Commentary

> **As a** football club manager,
> **I want** to watch the events of my match unfold in real-time via a commentary ticker,
> **So that** I experience the suspense of a real match rather than just seeing an instant final score.

**Acceptance Criteria:**
- **AC-05a:** The match simulation engine generates a chronological script of events (goals, misses, saves, yellow cards) that culminate in the pre-calculated final score.
- **AC-05b:** Running `/match play` posts a "Match Ticket" embed in the main channel and spawns a public thread named `"🏟️ [Home] vs [Away] - Live"`.
- **AC-05c:** The live commentary ticker plays out dynamically inside the public thread, showing a 5-event live-scroll history and pausing for 1.5 to 2.0 seconds between events to build suspense.
- **AC-05d:** Upon match completion, a "Post-Match Press Conference" embed is posted in the thread detailing final score, stats (Possession, Shots, MOTM), and rewards.
- **AC-05e:** The thread is renamed to display the final score (e.g. `🏆 [Home] [Score] [Away]`) and is locked and archived after 3 minutes.
- **AC-05f:** To ensure data integrity, all database updates (deducting energy, crediting coins/XP, logging match history) are executed *after* the final whistle event and before the Press Conference UI is posted.
- **AC-05g:** If thread creation is not supported or fails (e.g., in DMs or due to missing permissions), the command falls back gracefully to running in the parent channel.

---

# ElevenBoss v1.2 Features

### US-06: Club Economy & Wages

> **As a** football club manager,
> **I want** to manage my club's finances, review wage bills, and sell players,
> **So that** I can fund my squad development and make strategic player transactions.

**Acceptance Criteria:**
- **AC-06a:** The club's wallet supports both Coins and Tokens.
- **AC-06b:** Running `/club-finances` displays current Coins/Tokens balances and a calculated weekly wage bill forecast based on the OVR of the manager's current starting 11 squad.
- **AC-06c:** Entering the **Sell Player** sub-menu of the `/marketplace` hub displays a dropdown of owned players. Selecting a player calculates their agent sale value based on OVR and rarity, presenting a "Confirm Sale" button.
- **AC-06d:** Clicking "Confirm Sale" transactionally removes the player card from the manager's roster, credits the sale value in coins to the club, and logs the details to the transaction ledger.
- **AC-06e:** Players currently assigned to the starting 11 squad, in training, or in active evolutions cannot be sold.

### US-07: Async Training Hub

> **As a** football club manager,
> **I want** to train my player cards in specific drills asynchronously,
> **So that** their attributes and levels improve over time.

**Acceptance Criteria:**
- **AC-07a:** Managers have access to a maximum of 2 active training slots by default.
- **AC-07b:** Entering the **Training Drills** sub-menu of the `/development` hub displays all training slots, showing active/completed drills with real-time dynamic countdown timestamps.
- **AC-07c:** Empty slots display a "Start Drill" button. Clicking it presents a menu to select a player card and drill type (`cardio`, `tactics`, `match_prep`).
- **AC-07d:** Initiating a drill deducts the drill coin cost, logs it in the ledger, and sets the drill's end time.
- **AC-07e:** Training XP gains use a diminishing returns scale based on the player's current level.
- **AC-07f:** A player card can only be in one active training drill at a time, and a drill cannot be started if all training slots are currently full.

---

# ElevenBoss v1.3 Features

### US-08: Player Lifecycle & Evolutions

> **As a** football club manager,
> **I want** to track my players' aging, roles, PlayStyles, morale, contracts, and evolution tracks,
> **So that** my squad development feels complete and progressive.

**Acceptance Criteria:**
- **AC-08a:** Player cards support role attributes (`GK`, `Defender`, `Midfielder`, `Forward`), morale (impacted by match results), contracts (renewable via coins), and dynamic potential for youth cards (age 16-21).
- **AC-08b:** PlayStyles act as positive match engine simulation modifiers.
- **AC-08c:** Running `/player-profile` displays an exhaustive profile (OVR, Role, Level/XP progress bar, PlayStyles, Morale, Contract Days, and Age) with interactive button controls for `[Start Evolution]` and `[Level Up]`. These buttons redirect directly to pre-filtered sub-menus in the Development Center.
- **AC-08d:** Entering the **Skill Allocation** sub-menu of the `/development` hub allows managers to allocate acquired level-up points to 6 core attributes (PAC, SHO, PAS, DRI, DEF, PHY).
- **AC-08e:** Entering the **Evolutions** sub-menu of the `/development` hub displays options/select menu for 3 basic evolution tracks allowing players to undergo progressive training challenges.

---

# ElevenBoss v1.4 Features

### US-09: Live Stadium V2 (Dynamic Match Engine)

> **As a** football club manager,
> **I want** to play matches that respond to live touchline tactical adjustments and show dynamic, context-aware commentary,
> **So that** I feel like an active manager during games rather than a passive observer.

**Acceptance Criteria:**
- **AC-09a:** Match simulation streams events dynamically in real-time via an async generator, advancing by random minute phases (6-12 mins) up to 90'.
- **AC-09b:** Interactive Touchline buttons (`[ Attack ]`, `[ Defend ]`, `[ Balanced ]`) allow managers to alter match math (momentum and ratings weight) mid-game.
- **AC-09c:** The match simulator maintains a `MatchState` object containing scores, minute, momentum, and dynamic context tags (e.g. `tied`, `late`, `high_momentum`).
- **AC-09d:** Commentary lines are dynamically generated using a JSON bank (`commentary_bank.json`) which filters and matches context tags, supporting placeholders for team/player actors.
- **AC-09e:** Discord ticker updates are paced dynamically using the commentary line's `urgency` value (e.g. longer pauses for high-drama cliffhangers).
- **AC-09f:** Data transaction safety is preserved: Supabase writes (energy cost, rewards, XP logs, evolutions progress) are strictly executed only after the full match stream terminates.

---

# ElevenBoss v1.5 Features

### US-10: Unified Development Center Dashboard

> **As a** football club manager,
> **I want** a unified hub command (`/development`) that merges all progression UI sub-menus,
> **So that** I don't have to remember and execute multiple different commands to train, allocate skills, or evolve my players.

**Acceptance Criteria:**
- **AC-10a:** Slash command `/development` is introduced, opening the central `DevelopmentHubView` containing three button pathways: `[🏋️ Training Drills]`, `[🧬 Evolutions]`, and `[⭐ Allocate Skills]`.
- **AC-10b:** State-swapping UI: Clicking any button updates/edits the existing dashboard message without spawning a new one or requiring the user to type other commands.
- **AC-10c:** A back-navigation button `[⬅️ Back to Hub]` is present on all sub-menu screens to allow returns to the main dashboard.
- **AC-10d:** Quick-action buttons on `/player-profile` (`[Start Evolution]` and `[Level Up]`) correctly route the user by opening the pre-filtered sub-menu of the `/development` flow for that specific card.
- **AC-10e:** View security and timeouts are enforced: all views have a timeout of at least 15 minutes, and only the invoking manager can interact with the buttons.

---

# ElevenBoss v1.6 Features

### US-11: Unified Marketplace Dashboard

> **As a** football club manager,
> **I want** a unified hub command (`/marketplace`) to view my coins, sell players, and search the transfer market,
> **So that** all financial trading activities are centralized.

**Acceptance Criteria:**
- **AC-11a:** Slash command `/marketplace` is introduced, opening the central `MarketplaceHubView` containing three button pathways: `[💰 Sell Player]`, `[🔍 Search Market (Soon)]` (disabled), and `[📋 My Listings (Soon)]` (disabled).
- **AC-11b:** Deprecated command: Running the old `/sell-player` command displays an ephemeral warning: *"⚠️ The Marketplace has moved! Please use /marketplace."*
- **AC-11c:** State-swapping UI: Clicking `[💰 Sell Player]` edits the existing dashboard message to present the player selection dropdown and valuation results in-place.
- **AC-11d:** Navigation: A `[⬅️ Back to Market]` button is present on the sell screen to return to the Marketplace Hub.
- **AC-11e:** Roster locks: Player cards that are currently in the Starting 11, active training, or active evolutions cannot be sold and are filtered out of the selection list.
- **AC-11f:** Security: The view has a 15-minute timeout and only the invoking manager can interact with it.

---

# ElevenBoss v1.7 Features

### US-12: Battle Arena Hub

> **As a** football club manager,
> **I want** a centralized `/battle` hub to choose bot battles, friendlies, and ranked matches,
> **So that** all competitive match play pathways are in one unified dashboard.

**Acceptance Criteria:**
- **AC-12a:** Slash command `/battle` is introduced, opening the central `ArenaHubView` containing three button pathways: `[🤖 Bot Battle]`, `[🤝 Friendly Match (Soon)]` (disabled), and `[🏆 Ranked (Soon)]` (disabled).
- **AC-12b:** Deprecated command: Running the old `/match play` command displays an ephemeral warning: *"⚠️ The match system has been moved! Please use /battle instead."*
- **AC-12c:** Bot Battle sub-command: Spawns the subcommand `/battle bot` which runs the live dynamic simulator in the Stadium thread.
- **AC-12d:** State-swapping UI: Clicking `[🤖 Bot Battle]` inside the Battle Hub launches the Bot Battle logic directly.
- **AC-12e:** Safety and timeout: All views enforce a 15-minute timeout and verify user identity.

---

# ElevenBoss v1.8 Features

### US-13: Admin Control Panel

> **As a** bot administrator / owner,
> **I want** a secure, DM-only `/admin` control panel,
> **So that** I can configure guild-specific league settings and channel announcements.

**Acceptance Criteria:**
- **AC-13a:** Slash command `/admin` is introduced, restricted to the bot owner, and forced to run in DM channels only (`@app_commands.dm_only()`).
- **AC-13b:** Server select: Running `/admin` displays a dropdown populated with mutual servers where the bot owner is an `Administrator`.
- **AC-13c:** Dashboard panels: Choosing a server opens the hub displaying: `[📢 Announcements]`, `[🏆 League Management (Soon)]` (disabled), and `[🔄 Switch Server]`.
- **AC-13d:** Announcements submenu: Allows setting announcement channels and notification mention roles using `ChannelSelect` and `RoleSelect`.
- **AC-13e:** Permission checks: When selecting an announcement channel, the bot verifies it has read/send permissions; if not, it reports a clean error.
- **AC-13f:** Session timeout: Admin panel views timeout in 10 minutes, disabling elements and marking the footer.

---

## 15. League Notification Policy

### AC-15a: Split-Payload Delivery

- **GIVEN** a league announcement is sent (e.g. season start, season end),
- **THEN** the notification must use a split-payload structure:
  - Role mentions reside in message `content` to trigger pings.
  - Announcement details reside in `embeds` for clean formatting.
  - Fetch `announcement_role_id` from the `guild_config` database table.
  - Construct the message `content` as: `f"<@&{role_id}>\n\n{message_body}"` (only include the role mention if `role_id` is not None).
  - Verify `announcement_role_id` exists in the guild. If the role does not exist, do not include the mention in the content to avoid "broken ping" strings like `<@&None>`.

---

## 16. League Journal & Auto-Archival System

### AC-16a: Centralized League Journal Thread
- **GIVEN** a league match is simulated (manually or auto-simulated),
- **THEN** all commentary updates, scoreboard tickers, and final results must be directed to a single centralized public thread named `#league-journal`.
- **AND** the thread ID is stored in the `guild_config` table under `league_updates_thread_id` (BIGINT).
- **AND** if the thread does not exist or has been deleted, the bot must automatically re-create the thread in the configured `league_channel_id` channel, post a pinned introductory/rules embed, and save the new thread ID to the database.

### AC-16b: Live-Scroll Ticker (Commentary Rolling Buffer)
- **GIVEN** a live match is streaming commentary,
- **THEN** the simulator must edit a single persistent embed field (`Live Commentary`) instead of flooding the channel with individual event messages.
- **AND** the `Live Commentary` field must display a rolling buffer of only the 5 most recent commentary events.

### AC-16c: Sequential Background Auto-Simulation
- **GIVEN** background auto-simulation is run (via the 10-minute interval job or admin force-sim command),
- **THEN** all unplayed matches that have exceeded their window end must be simulated sequentially to prevent rate limits and ensure Commentary is delivered correctly.

### AC-16d: Season End Summary & Archival Flow
- **GIVEN** the admin ends the season via the `/admin` control panel,
- **THEN** the bot must calculate final season statistics including:
  - League Champions (highest points, goal difference, goals for)
  - Top Scoring Club (highest total goals scored)
  - Best Defense (fewest total goals conceded)
- **AND** post the detailed Season Summary and awards embed to the League Journal thread.
- **AND** wait exactly 30 seconds before renaming the thread to `🏆-season-{season_number}-concluded`, locking it, and archiving it.
- **AND** reset `league_updates_thread_id` to NULL in `guild_config` so the next season gets a fresh journal thread.

---

## 17. League System Enhancements (Stats, Logs, & UI)

### US-17: Detailed Player Statistics & Match History logs

> **As a** league participant manager,
> **I want** to view detailed season stats (goals, assists, clean sheets, MOTM awards) and a historical Match Center box score timeline,
> **So that** I have full visibility of my team's performance and past matches.

**Acceptance Criteria:**

#### AC-17a: Database Schema Extensions
- **GIVEN** the migration is run,
- **THEN** a `match_logs` table must store the raw JSON box score and key events (goals, cards, injuries) for each league fixture.
- **AND** a `player_season_stats` table must store individual player performance statistics (goals, assists, clean sheets, MOTM awards, average rating) on a per-season basis.

#### AC-17b: Match Engine Stat Aggregation & finalization
- **GIVEN** a league match is simulated,
- **THEN** the match engine must track and accumulate a chronological list of `Key Events` (goals, cards, injuries) during the game loop.
- **AND** when the match concludes, `LeagueMatchHandler.finalize_match()` must write the box score and timeline to `match_logs`.
- **AND** parse goalscorers and the MOTM to atomic upsert/increment their records in `player_season_stats`.

#### AC-17c: /league hub Redesign & Sub-views
- **GIVEN** a user runs `/league hub`,
- **THEN** the main dashboard embed must show a visual indicator of the active matchday (e.g. `🟢 Matchday 4/14 Active`).
- **AND** add the following interactive sub-views:
  - **`[ 📊 Standings ]`**: Clean, formatted standings table.
  - **`[ 👟 Player Stats ]`**: Renders leaderboards for Top Goals (Golden Boot), Top Assists, and Clean Sheets.
  - **`[ 📺 Match Center ]`**: Displays a select menu listing the server's completed fixtures. Selecting a fixture renders a detailed "Box Score Embed" showing the score, team stats, MOTM, and the chronological events timeline.

#### AC-17d: Announcement Permission Policy
- **GIVEN** a match result is posted to the centralized `#league-journal` thread,
- **THEN** the thread permissions must allow all users to add emoji reactions (`Add Reactions`), even if `Send Messages` is disabled for non-admins.

---

### US-18: Live Friendly Matches (Player vs Player)

> **As a** registered manager,
> **I want to** challenge another manager to a friendly match,
> **So that** we can watch a live, threaded simulation of our teams playing against each other without affecting competitive league standings.

**Acceptance Criteria:**

#### AC-18a: Challenge Command & Match Lock Guards
- **GIVEN** a registered user runs `/battle friendly opponent:[@Member]`,
- **THEN** the bot verifies that:
  - The target opponent is not the sender themselves.
  - Both the challenger and the opponent have registered manager profiles.
  - Neither the challenger nor the opponent has an active record in the `match_locks` table.
- **AND** if any guard check fails, the bot returns a descriptive ephemeral error.
- **AND** if all checks pass, the bot responds ephemerally to the challenger: *"Challenge issued to [opponent]!"* and posts a public invitation to the channel: *"⚔️ [Opponent.mention], you have been challenged by [Challenger.name]!"* equipped with a `ChallengeView` containing **Accept** and **Decline** buttons.

#### AC-18b: Challenge UI Verification & Timeout
- **GIVEN** a spectator (user other than the challenged opponent) clicks **Accept** or **Decline**,
- **THEN** the bot returns a descriptive ephemeral warning: *"This challenge belongs to another manager."*
- **GIVEN** the opponent clicks **Decline**,
- **THEN** the bot edits the original message to: *"Challenge declined by [opponent]."* and disables the buttons.
- **GIVEN** the challenge is not accepted or declined within **60 seconds**,
- **THEN** the invitation times out, and the bot edits the message to: *"Challenge to [opponent] timed out."* and disables the buttons.

#### AC-18c: Match Thread Spawning & Live Ticker
- **GIVEN** the opponent clicks **Accept**,
- **THEN** the bot deletes or edits the original challenge invitation and creates a public thread named `🤝 [Club1] vs [Club2] – Friendly` off the current channel.
- **AND** the bot immediately inserts two rows into the `match_locks` table to prevent either player from initiating concurrent matches (friendly, bot, or league).
- **AND** the bot fetches both players' active squads (starting 11) and initializes the NSS state machine.
- **AND** the bot streams the live match commentary ticker to the spawned thread in real-time, yielding kickoff, half-time, goals, saves, misses, cards, injuries, and full-time events.

#### AC-18d: Stat Isolation & Thread Clean-up
- **GIVEN** the friendly match concludes (at minute 90),
- **THEN** the final score and events are serialized and written to `friendly_match_logs` (Option A). Competitive tables like `match_logs` or `player_season_stats` are completely untouched.
- **AND** both managers are mentioned in the final whistle embed inside the thread, and their respective entries are deleted from `match_locks`.
- **AND** the bot schedules a task to archive and lock the thread after a **120-second delay** to keep the server channels clean.


