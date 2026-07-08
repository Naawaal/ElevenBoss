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

- **GIVEN** an unregistered user attempts to run any core gameplay command other than `/register` (e.g., `/match play`, `/store`),
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
- **WHEN** I run `/store` and click the **🎫 Claim Free Pack** button,
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

### US-06: Player Levelling (Progression) — **DEPRECATED**

> **Status:** Superseded by **US-23** (v1.9). Coin-based `/player level-up` and direct OVR bumps per level are removed. Progression is XP-driven with skill-point allocation.

**Legacy acceptance criteria (v1.0.0 only):**
- Coin level-up via `/player level-up <player_id>` at cost `(current_level ^ 1.5) * 100`.
- Direct `+1 OVR` per level up to rarity cap.

**Migration note:** If `/player level-up` still exists in code, it must return an ephemeral redirect to `/development` → Skill Allocation.

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
- **AC-08c:** Running `/player-profile` displays an exhaustive profile (OVR, Role, Level/XP progress bar, PlayStyles, Morale, Contract Days, and Age) with interactive button controls for `[Start Evolution]` and `[Allocate Skill Points]`. These buttons redirect directly to pre-filtered sub-menus in the Development Center. *(Amended v1.9 — US-23: "Level Up" renamed; skill points granted on XP level-up.)*
- **AC-08d:** Entering the **Skill Allocation** sub-menu of the `/development` hub allows managers to allocate skill points earned from XP level-ups to 6 core attributes (PAC, SHO, PAS, DRI, DEF, PHY), subject to POT caps. *(Amended v1.9 — US-23.)*
- **AC-08e:** Entering the **Evolutions** sub-menu of the `/development` hub displays options/select menu for 3 basic evolution tracks allowing players to undergo progressive training challenges.
- **AC-08f:** A club may have at most **3** simultaneous active evolutions (`status = 'active'`). Attempting to start a 4th is rejected server-side with a clear error message.
- **AC-08g:** After a **cold** evolution start, the club enters a **10-hour cooldown** before another cold start. Cancelling an active evolution grants a **replacement** start in the freed slot without waiting for the cooldown; replacement starts do not reset the cooldown timer.
- **AC-08h:** The Evolution Command Center displays active slot usage (e.g. `2/3 slots used`), training energy, start-cost summary, cooldown until the next cold start, active evolutions with match progress, and recently completed history.
- **AC-08i:** Starting an evolution deducts **25 training energy** and **10 × player OVR coins** atomically in `start_player_evolution`. Insufficient training energy or coins blocks the start with no partial deduction. Replacement starts pay the same fee.

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
  - **Commentary Markdown Formatting:** Commentary rendering shifts to "Data-Side Formatting". The engine will wrap dynamic variables (e.g. `{actor}`, `{team}`) in Markdown double-asterisks (`**`) during dictionary injection, rather than using regex or post-processing on the final output. If the value is a string, any existing `**` formatting is stripped beforehand to prevent double-bolding (`****`). Non-string values are left untouched.
  - **Template Bold Policy:** Dramatic exclamations (e.g. `**GOAL!**`, `**WHAT A SAVE!**`) must be hardcoded directly into the templates in `commentary_bank.json` with markdown bold syntax, while variables/placeholders remain plain.
- **AC-09e:** Discord ticker updates are paced dynamically using the commentary line's `urgency` value (e.g. longer pauses for high-drama cliffhangers).
- **AC-09f:** Data transaction safety is preserved: Supabase writes (energy cost, rewards, XP logs, evolutions progress) are strictly executed only after the full match stream terminates.

---

# ElevenBoss v1.5 Features

### US-10: Unified Development Center Dashboard

> **As a** football club manager,
> **I want** a unified hub command (`/development`) that merges all progression UI sub-menus,
> **So that** I don't have to remember and execute multiple different commands to train, allocate skills, or evolve my players.

**Acceptance Criteria:**
- **AC-10a:** Slash command `/development` is introduced, opening the central `DevelopmentHubView` containing four button pathways: `[🏋️ Training Drills]`, `[🧬 Evolutions]`, `[⭐ Allocate Skills]`, and `[🔥 Card Fusion]` (sacrifice a bench card to grant fusion XP to a keeper via `apply_card_xp`). *(Amended v1.9 — US-23: fusion grants XP, not direct level/stat.)*
- **AC-10b:** State-swapping UI: Clicking any button updates/edits the existing dashboard message without spawning a new one or requiring the user to type other commands.
- **AC-10c:** A back-navigation button `[⬅️ Back to Hub]` is present on all sub-menu screens to allow returns to the main dashboard.
- **AC-10d:** Quick-action buttons on `/player-profile` (`[Start Evolution]` and `[Allocate Skill Points]`) correctly route the user by opening the pre-filtered sub-menu of the `/development` flow for that specific card. *(Amended v1.9 — US-23.)*
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

### AC-16e: Unreachable Guild & Season Pause
- **GIVEN** an active or registration league season whose Discord guild the bot cannot reach (removed from server or confirmed absent via API),
- **THEN** background auto-simulation must pause that season (`status = paused`) instead of logging a warning every 10 minutes.
- **AND** when the bot leaves a guild (`on_guild_remove`), any active/registration season for that guild's league must be paused automatically.
- **AND** transient Discord errors (HTTP 429/5xx while resolving the guild) must skip auto-sim for that run without pausing the season.

### AC-16f: Slash-Command Rate-Limit Resilience
- **GIVEN** a registered manager invokes a guarded slash command while Discord/Cloudflare returns HTTP 429 during interaction defer,
- **THEN** the bot must retry defer with backoff and, if still blocked, send an ephemeral user-facing retry message instead of failing silently.

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
- **THEN** the final score and events are serialized and written to `friendly_match_logs` (Option A). Competitive tables like `match_logs`, `match_history`, `player_season_stats`, and `players` career stats are completely untouched.
- **AND** no action energy is consumed, no coins are awarded, and no card XP or evolution progress is applied.
- **AND** both managers are mentioned in the final whistle embed inside the thread, and their respective entries are deleted from `match_locks`.
- **AND** the bot schedules a task to archive and lock the thread after a **120-second delay** to keep the server channels clean.

#### AC-18e: League Registration Gate
- **GIVEN** a manager attempts guild league registration,
- **WHEN** their `matches_played` count is evaluated,
- **THEN** only **bot matches** count toward the minimum — friendly matches do not increment `matches_played` and do not satisfy the gate.

---

## 19. Global League Points (LP) & Divisions System

### Global vs. Server League Points
- **Server League Points**: Weekly competitive points reset to 0 at the end of each week. Determines server-specific division promotion/relegation.
- **Global League Points (LP)**: Persistent global ranking points tracked via the `global_lp` column in `players`. Determines the player's Global Division.

### Global Divisions & Scaling
- **Global Division**: Derived dynamically from `global_lp` by checking the highest division threshold met in the `global_divisions` table.
- **AI Scaling**: Bot OVR ranges and coin rewards scale based on the user's current Global Division:
  - **Bronze III**: 0 LP, Bot 50-60 OVR, 100 Coins Win Reward
  - **Bronze II**: 100 LP, Bot 55-65 OVR, 125 Coins Win Reward
  - **Bronze I**: 250 LP, Bot 60-70 OVR, 150 Coins Win Reward
  - **Silver III**: 500 LP, Bot 70-75 OVR, 200 Coins Win Reward
  - **Silver II**: 750 LP, Bot 75-80 OVR, 250 Coins Win Reward
  - **Silver I**: 1000 LP, Bot 80-85 OVR, 300 Coins Win Reward
  - **Gold**: 1500 LP, Bot 85-90 OVR, 400 Coins Win Reward
  - **Elite**: 2500 LP, Bot 90-95 OVR, 600 Coins Win Reward

### Match Payout Formula
- **Win**: +15 LP, `win_coins` awarded.
- **Draw**: +5 LP, `win_coins / 3` (integer division) awarded.
- **Loss**: -10 LP (clamped to 0 minimum), `15` coins consolation.

---

## 20. Squad Pitch Graphic Generation (Pillow Visuals)

### US-20: Dynamic Football Pitch Squad Visualization
> **As a** registered manager,
> **I want to** see a beautifully rendered football pitch showing my squad's active tactical formation and starting XI,
> **So that** I have a visually immersive view of my lineup and team.

**Acceptance Criteria:**
- **GIVEN** a user runs `/squad` or updates their squad formation/lineup,
- **THEN** the bot must generate a vertical pitch image on the fly using Pillow (PIL) containing:
  - Alternating dark/light green grass bands or a custom pitch background.
  - Rectangular player boxes positioned at the formation's relative coordinates.
  - Player OVR rating (bold font) and Name (regular font) centered in each box.
  - Positional color-coding for OVR ratings (e.g. gold for 80+, silver for 70-79).
- **AND** the image must be sent directly as a `discord.File` without writing to disk.
- **AND** the image must update dynamically when editing/swapping players or changing formations in the `/squad` menu.

---

## 21. Roster Grid Graphic Generation (Pillow Visuals)

### US-21: Dynamic Roster Graphical Grid Visualization
> **As a** registered manager,
> **I want to** see my player collection roster displayed as a visually stunning grid of cards,
> **So that** my player collection feels premium and immersive.

**Acceptance Criteria:**
- **GIVEN** a user opens the Full Roster menu via `/squad` or navigates the roster pages,
- **THEN** the bot must generate a 4x2 grid of cards showing up to 8 players on the current page using Pillow (PIL).
- **AND** each card in the grid must be styled with:
  - A premium dark slate background.
  - A 2px colored border representing its rarity (Gold: Legendary, Purple: Epic, Blue: Rare, Silver/Gray: Common).
  - The player's overall rating (OVR) and position (bold font) color-coded by rarity.
  - The player's name (regular font) centered.
  - The player's level (Lvl) and card ID (subtle gray font) at the bottom.
- **AND** the image must be sent directly as a `discord.File` without writing to disk.
- **AND** the image must update dynamically on pagination (Prev/Next buttons).

---

## 22. Pre-Launch Hardening (Audit Remediation)

### US-22: Security, Integrity & UX Hardening

> **As a** platform operator,
> **I want** all economy, roster, and match flows enforced at the database layer with consistent UI behavior,
> **So that** v1.0.0 launches without exploits, data corruption, or silent failures.

**Acceptance Criteria:**

#### AC-22a: Stat Drill RPCs
- **GIVEN** a manager opens Stat Training in `/development`,
- **THEN** `sync_training_energy` and `process_stat_drill` RPCs exist and atomically enforce energy, coins, daily limits, match locks, level-tier gates, and POT-aware skill allocation (not direct stat bumps post-v1.9). *(Amended v1.9 — US-23: drills grant XP via `apply_card_xp`.)*

#### AC-22b: Server-Side Agent Sale Pricing
- **GIVEN** a manager confirms an agent sale,
- **THEN** `process_agent_sale` recomputes the offer from live card `overall` and `rarity` (client value ignored) and rejects XI, training, evolution, and match-locked cards.

#### AC-22c: Match Lock on Roster Mutations
- **GIVEN** a manager has a row in `match_locks`,
- **THEN** squad swaps, formation changes, training, fusion, skill allocation, evolution claims, and sales are blocked until the match ends.

#### AC-22d: Atomic Squad RPCs
- **GIVEN** a formation change or bench swap,
- **THEN** a single RPC performs the mutation with row locks and revalidates ownership; partial XI states cannot persist.

#### AC-22e: Registration Idempotency
- **GIVEN** duplicate confirm or concurrent `/register` attempts,
- **THEN** at most one player account is created; whitespace-only club names are rejected.

#### AC-22f: League Window Enforcement
- **GIVEN** a fixture outside its `window_start`/`window_end`,
- **THEN** `execute_league_match` rejects play server-side regardless of stale UI.

#### AC-22g: Unified OVR Recalculation
- **GIVEN** any progression path (drill, fusion, skill, evolution),
- **THEN** `overall` is derived from weighted stats, playstyles, and `potential` via `recalculate_card_ovr`.

#### AC-22h: Dropdown Selection Persistence
- **GIVEN** a multi-select hub view,
- **THEN** after `edit_message`, selected options remain visible (`default=True` rebuild pattern).

#### AC-22i: View Timeouts
- **GIVEN** any hub sub-view exceeds its timeout,
- **THEN** components are disabled via `on_timeout`.

#### AC-22j: GK Slot Rule
- **GIVEN** slot 1 in the starting XI,
- **THEN** only a `position = 'GK'` card may occupy it after swaps or formation auto-assign.

#### AC-22k: `league_members` Schema
- **GIVEN** a fresh database migration run,
- **THEN** `league_members` table exists and league registration succeeds.

#### AC-22l: Deploy-Safe Assets
- **GIVEN** the bot runs on Linux (Render),
- **THEN** pitch/roster image generation resolves asset paths relative to the repo root, not a hardcoded Windows path.

---

# ElevenBoss v1.9 Features

### US-23: Dynamic Player Leveling System

> **As a** football club manager,
> **I want** my players to earn XP from matches, drills, and card fusion, automatically level up, and receive skill points I can allocate to attributes,
> **So that** every match and training session feels rewarding and progression is balanced, gated, and exploit-resistant.

**Problem statement:** Players display a Level/XP bar (e.g. `Level 3 | 75/112 XP`) but **never receive skill points on level-up**. A legacy `level` column is incremented independently by fusion, creating two conflicting progression systems. Stat drills bypass leveling by granting direct `+1` attribute gains.

**Design principles:**
1. **Single source of truth:** `player_cards.xp` drives `player_cards.level`. Level is always recomputed inside the database on every XP mutation.
2. **Three complementary XP sources, one stat sink:** Fusion / Matches / Drills → XP → Level-up → Skill points → Attribute allocation (POT-capped).
3. **All XP mutations** go through one atomic RPC: `apply_card_xp`.

#### AC-23a: Level & XP Structure
- **GIVEN** a newly registered player card,
- **THEN** it starts at `level = 1`, `xp = 0`, `skill_points_earned = 0`, `skill_points_spent = 0`, and `skill_points` (available balance) = 0.
- **AND** the maximum level is `L_MAX = 100` (configurable constant in `packages/player_engine`).
- **AND** XP required to advance from level L to L+1 is: `xp_needed(L) = floor(BASE × EXP^(L−1))` where `BASE = 100`, `EXP = 1.12`.
- **AND** cumulative XP to reach level L is the sum of `xp_needed(i)` for `i = 1..L−1`.
- **AND** each level gained awards `POINTS_PER_LEVEL = 3` skill points, added atomically to `skill_points` and `skill_points_earned`.
- **AND** skill points available satisfies: `skill_points = skill_points_earned − skill_points_spent` (enforced by RPC invariant).
- **AND** at level 100, further XP is discarded (`xp_wasted` returned in RPC JSON; no overflow).

#### AC-23b: Central XP Pipeline (`apply_card_xp`)
- **GIVEN** any XP grant (match, drill, fusion),
- **WHEN** the mutation is processed,
- **THEN** it MUST call `apply_card_xp(p_card_id, p_xp_amount, p_source)` — never a raw `SET xp = xp + N` without level sync.
- **AND** the RPC locks the card row (`FOR UPDATE`), computes old/new level from XP, grants skill points for `levels_gained`, updates `last_level_up_at` when levels increase, logs to `player_xp_log`, and returns JSON: `{old_level, new_level, levels_gained, skill_points_granted, xp_added, xp_wasted}`.
- **AND** `player_cards.level` is always equal to `level_from_xp(xp)` after the RPC completes.

#### AC-23c: Method 1 — Card Fusion (XP source)
- **GIVEN** a manager opens **Card Fusion** in `/development`,
- **WHEN** they sacrifice a bench card to feed a keeper,
- **THEN** the sacrificed card is permanently deleted (existing guards: not starting XI, not in match/training/active evolution, not self-fusion).
- **AND** fusion XP is: `50 + (sacrifice.level × 8) + (sacrifice.overall × 2)`.
- **AND** XP is applied to the keeper via `apply_card_xp(..., 'fusion')`.
- **AND** fusion does **not** directly increment `level` or any attribute on the keeper.
- **AND** each club may perform at most **3 fusions per UTC calendar day** (tracked in `fusion_daily_log`).
- **AND** the UI shows projected XP and level-up preview before confirm; warns if keeper is already at max level.

#### AC-23d: Method 2 — Skill Point Allocation (level-up reward sink)
- **GIVEN** a player has `skill_points > 0`,
- **WHEN** a manager opens **Skill Allocation** in `/development` or clicks **Allocate Skill Points** on `/player-profile`,
- **THEN** they may spend 1 skill point per tap to increase one of PAC, SHO, PAS, DRI, DEF, PHY by +1.
- **AND** `allocate_skill_point` atomically decrements `skill_points`, increments `skill_points_spent`, bumps the stat, and calls `recalculate_card_ovr`.
- **AND** allocation is rejected if: stat ≥ 99, `overall ≥ potential`, or the post-allocation OVR would exceed `potential`.
- **AND** when `apply_card_xp` returns `levels_gained > 0`, the bot sends an ephemeral notification with a link/button to Skill Allocation.

#### AC-23e: Method 3 — Match XP (passive)
- **GIVEN** a match concludes (bot, friendly, or league) and rewards are applied post-whistle,
- **THEN** each participating card receives match XP computed in pure logic and applied via `apply_card_xp`.
- **AND** base XP uses `calculate_match_development_xp(minutes, rating)` from `training_engine`, then multipliers:
  - Match type: friendly `×0.8`, bot `×1.0`, league `×1.25`
  - Goal bonus: `+5` per goal; assist bonus: `+3` per assist; MOTM: `+15`
  - Result bonus: win `+5`, draw `+2`, loss `+0`
- **AND** per-match XP is clamped to `[1, 35]`.
- **AND** abandoned/crashed matches award no XP (existing match-run recovery policy).

#### AC-23f: Method 3 — Drill XP (replaces direct stat drills)
- **GIVEN** a manager runs a stat drill in `/development`,
- **THEN** the drill grants **XP only** (no direct attribute increment).
- **AND** drill tiers and gates:

| Tier | Min level | Energy | Coin cost | Base XP |
|------|-----------|--------|-----------|---------|
| Basic | 1 | 15 | `5 × OVR` | 25 |
| Intermediate | 10 | 20 | `8 × OVR` | 60 |
| Advanced | 25 | 25 | `12 × OVR` | 120 |
| Elite | 50 | 30 | `15 × OVR` | 200 |

- **AND** final drill XP = `base_xp × (1 / (1 + 0.05 × (level − 1)))` (diminishing returns).
- **AND** drills below the player's level tier appear grayed/locked in the UI; server rejects under-level attempts.
- **AND** daily drill limit (20) and training energy checks remain enforced.

#### AC-23g: Content Gating by Player Level
- **GIVEN** evolution tracks in `EVOLUTION_TRACKS`,
- **THEN** each track has a `min_player_level` requirement:
  - Pace Masterclass: Level 5
  - Shooting Star: Level 10
  - Defensive Wall: Level 8
- **AND** `start_player_evolution` rejects starts when `card.level < track.min_player_level`.
- **AND** the Evolution Hub hides or disables tracks the player does not qualify for, showing the requirement.

#### AC-23h: Retroactive Level-Up Reward Catch-Up
- **GIVEN** the v1.9 migration runs on deploy,
- **THEN** for every card where `(level_from_xp(xp) − 1) × POINTS_PER_LEVEL > skill_points_earned`, a row is inserted into `pending_level_rewards` with `missing_points`, `claimed = false`, `notified = false`.
- **AND** on bot startup, affected club owners receive a DM embed **"🎁 Level-Up Rewards Available!"** listing players and missing points, with a **Claim All** button.
- **AND** clicking **Claim All** calls `claim_pending_level_rewards(p_owner_id)` atomically: credits `skill_points` and `skill_points_earned`, sets `claimed = true`, disables the button.
- **AND** the claim is idempotent — second click returns zero additional points.
- **AND** if DMs are disabled, managers can claim via **Claim Level Rewards** on the `/development` hub (logged for ops).
- **AND** pending rewards attach to `player_id`; the **current owner** at claim time receives the points.

#### AC-23i: Player Profile & Development UI
- **GIVEN** `/player-profile`,
- **THEN** the embed shows: XP-derived level, XP progress bar, **Available Skill Points**, and a button **Allocate Skill Points** (not "Level Up") when points > 0.
- **AND** `/development` hub pathways remain: Training Drills, Evolutions, Skill Allocation, Card Fusion — all aligned with XP/skill-point flows above.

#### AC-23j: Anti-Exploit & Integrity
- **GIVEN** any progression mutation,
- **THEN** `match_locks` blocks fusion, drills, and skill allocation during active matches.
- **AND** `skill_points_earned` must equal `(level − 1) × POINTS_PER_LEVEL` plus any retroactive claim credits (no manual inflation).
- **AND** `allocate_skill_point` enforces POT ceiling (aligned with migration 024 / `can_gain_stat_progression`).
- **AND** fusion self-target, daily fusion cap, and max-level XP waste behaviors are enforced server-side.

#### AC-23k: Deprecations & Breaking Changes
- **GIVEN** the v1.9 deploy,
- **THEN** `process_stat_drill` no longer grants direct `+1` stat (XP only).
- **AND** `train_with_fodder` no longer increments `level` or stats directly (fusion XP via `apply_card_xp`).
- **AND** `process_match_result` delegates per-card XP to `apply_card_xp`.
- **AND** existing player stats from pre-v1.9 drills/fusion are retained; only future gains use the new pipeline.

---

### US-24: Progression Hardening & Economy Safeguards (v1.9.1)

> **As a** game operator,
> **I want** retroactive rewards, skill allocation, and XP sources bounded by anti-exploit rules,
> **So that** veteran catch-up does not break competitive balance and claim flows work for every manager.

**Problem statement:** Post-audit of US-23 identified: (1) `pending_level_rewards.club_id` frozen at migration owner breaks claim after card transfer; (2) DM-only claim marks `notified` when blocked; (3) lump-sum retro payout spikes economy; (4) no daily caps on allocation, match XP per card, or drills per player.

#### AC-24a: Retroactive Reward Scaling
- **GIVEN** an unclaimed row in `pending_level_rewards`,
- **WHEN** rewards are calculated or claimed,
- **THEN** payable points = `min(RETRO_MAX_PER_PLAYER, floor(missing_raw × RETRO_SCALE_PCT / 100))` where `RETRO_SCALE_PCT = 75`, `RETRO_MAX_PER_PLAYER = 18`.
- **AND** existing unclaimed rows are re-scaled once in migration `027`.

#### AC-24b: Claim Ownership (Current Owner)
- **GIVEN** a card with unclaimed `pending_level_rewards`,
- **WHEN** `claim_pending_level_rewards(p_owner_id)` runs,
- **THEN** only rows where `player_cards.owner_id = p_owner_id` are credited (ignore stale `club_id`).
- **AND** `club_id` is synced to `player_cards.owner_id` on migration and on each claim.
- **AND** claim remains idempotent (`claimed` flag + `FOR UPDATE`).

#### AC-24c: Fallback Claim (Development Hub)
- **GIVEN** a manager has unclaimed retro rewards,
- **WHEN** DMs are disabled or the startup DM was missed,
- **THEN** opening `/development` shows a **Claim Level Rewards** button and embed notice when `count_unclaimed_level_rewards > 0`.
- **AND** startup notifier sets `notified = true` **only** on successful DM delivery (not on `Forbidden`).
- **AND** no separate `/claim-rewards` slash command is required.

#### AC-24d: Skill Allocation Pacing
- **GIVEN** the pacing window (30 days from v1.9.1 deploy),
- **WHEN** `allocate_skill_point` is called,
- **THEN** each card may spend at most `ALLOCATION_DAILY_CAP = 15` skill points per UTC day (`daily_alloc_count` on `player_cards`).
- **AND** counter resets when `alloc_reset_date < CURRENT_DATE`.
- **AND** after pacing window ends, daily allocation cap is not enforced.

#### AC-24e: Match XP Daily Cap (Per Card)
- **GIVEN** match XP applied via `apply_card_xp(..., 'match_simulation')`,
- **WHEN** the card has already received `MATCH_XP_DAILY_CAP = 100` match XP today (sum `player_xp_log` for UTC day),
- **THEN** further match XP for that card is reduced to the remaining allowance (may be 0).

#### AC-24f: Drill Cap Per Player
- **GIVEN** `process_stat_drill`,
- **WHEN** a card has already completed `DRILL_PER_PLAYER_DAILY_CAP = 5` drills today,
- **THEN** the RPC rejects with a clear error.
- **AND** club-wide `daily_drill_count` limit (20) remains enforced.

#### AC-24g: Allocate Pre-Check
- **GIVEN** `allocate_skill_point`,
- **WHEN** allocation would exceed POT,
- **THEN** the RPC rejects **before** mutating stats (pre-check `overall >= potential` and stat < 99).
- **AND** the RPC rejects when `overall >= potential` or stat ≥ 99 before spending; post-update OVR check rolls back the whole transaction on POT breach.

#### AC-24h: Schema & Verification
- **GIVEN** migration `027_progression_hardening.sql` is applied,
- **THEN** `verify_required_schema.sql` includes new columns/table/RPC guards.
- **AND** `scratch/verify_schema_full.py` passes.

---

### US-25: Economy v2 — Unified Faucets, Sinks & Action Energy (v2.0)

> **As a** game operator,
> **I want** all coin and energy mutations centralized with DB-backed tunables,
> **So that** the economy stays auditable, balanced, and adjustable without redeploying bot code.

#### AC-25a: `game_config` Table
- **GIVEN** migration `028_economy_foundation.sql` is applied,
- **THEN** table `game_config(key, value_json, updated_at, updated_by)` exists with seed rows for match rewards, drill costs, fusion cost, energy regen, agent sale cap, and `economy_v2_enabled`.
- **AND** `get_game_config(p_key)` returns JSONB with SQL fallback defaults when key missing.

#### AC-25b: Unified `apply_club_economy` RPC
- **GIVEN** any coin or action-energy mutation (match payout, drill, fusion, refill, daily login),
- **WHEN** `apply_club_economy(p_club_id, p_coin_delta, p_energy_delta, p_source, p_idempotency_key, p_meta)` runs,
- **THEN** it syncs action energy, validates non-negative balances, updates `players.coins` and `players.action_energy`, dual-writes legacy `energy`/`training_energy`, and appends `economy_ledger` with optional `idempotency_key` (unique — replays return prior result).
- **AND** match payouts in `battle_cog` use this RPC with `match_run_id` as idempotency key.

#### AC-25c: Action Energy Pool
- **GIVEN** a registered player,
- **THEN** `players.action_energy` (max 100) regens **1 per 6 minutes** via `sync_action_energy`.
- **AND** costs: bot match 20, league 10, basic drill 10, advanced drill 15, evolution start 25 (from `game_config`). Friendly matches cost **0** energy.
- **AND** `/profile`, `/development`, and battle hub show unified `⚡ current/max` with time-to-full estimate.

#### AC-25d: Config-Driven Income
- **GIVEN** economy v2 enabled,
- **THEN** bot match coins = `floor(match_bot_win × global_division.win_coins / 100)` for wins; draw/loss use `match_bot_draw` / `match_bot_loss`.
- **AND** league match coins scale between `match_league_win_min` and `match_league_win_max` by server `division` tier.
- **AND** friendly matches award **no coins** (sandbox mode).
- **AND** `claim_daily_login` grants `daily_login_base` + streak bonus (cap +50), once per UTC day.

#### AC-25e: Config-Driven Sinks
- **GIVEN** `process_stat_drill`, `start_player_evolution`, `train_with_fodder`,
- **THEN** coin/energy costs read from `game_config` and `drill_catalog` tier metadata (basic: 100 + 2×OVR, 10⚡, 30 XP; advanced tier at level 10+: 300 + 3×OVR, 15⚡, 80 XP).
- **AND** fusion costs `fusion_coins` (200 default) per `train_with_fodder`.
- **AND** `purchase_energy_refill` grants +50 energy for escalating coin cost (200/400/600), max 3/day.

#### AC-25f: Agent Sale Daily Cap
- **GIVEN** `process_agent_sale`,
- **WHEN** club has sold `agent_sale_daily_cap` (10) cards today,
- **THEN** RPC rejects with clear error.
- **AND** sales remain ledgered as `agent_sale`.

#### AC-25g: Store Hub
- **GIVEN** a registered manager invokes `/store`,
- **THEN** an ephemeral hub shows coins, gems, action energy, and buttons **Claim Daily Login** and **Buy Energy Refill**.
- **AND** daily login calls `claim_daily_login` (once per UTC day); energy refill calls `purchase_energy_refill` (escalating coin cost, max 3/day).
- **AND** these actions are **not** exposed on `/development` (development remains training, fusion, evolutions, skill allocation).

#### AC-25h: Ops Tuning (no Discord admin command)
- **GIVEN** economy tuning or audit is needed,
- **THEN** operators edit `game_config` in Supabase or run [`scripts/simulate_economy.py`](scripts/simulate_economy.py) / ledger SQL — no `/economy` slash command.

#### AC-25i: Migration & Rollback
- **GIVEN** deploy,
- **THEN** existing coin balances are preserved (no wipe).
- **AND** `economy_v2_enabled` in `game_config` allows ops to disable v2 match routing without schema rollback.
- **AND** `scripts/simulate_economy.py` and `tests/test_economy_flows.py` validate 30-day archetype budgets.

### US-26: Immersive League Mode v2

> **As a** guild league manager,
> **I want** a full season-based league with clear standings, fair rewards, and immersive matchdays,
> **So that** the league feels like the flagship competitive mode of ElevenBoss.

**Design reference:** [`.specify/specs/v1.0.0/league-mode-design.md`](league-mode-design.md)

#### AC-26a: Decoupled Points
- **GIVEN** a league match concludes,
- **THEN** seasonal standings update via `league_fixtures` only.
- **AND** `players.league_points` and `players.goal_difference` are **not** modified (weekly Division Rank is bot-match only).
- **AND** profile labels weekly stats as **Division Rank Points**.

#### AC-26b: Economy & XP Pipe
- **GIVEN** a human manager plays a league match,
- **THEN** coins flow through `apply_club_economy` with `match_type=league` division scaling.
- **AND** card XP uses `build_process_match_result_rpc(..., match_type='league')` (1.25× multiplier).
- **AND** energy deducts via `sync_action_energy` + `match_energy_league` when the manager triggers play.

#### AC-26c: XI Guard
- **GIVEN** a manager with fewer than 11 squad assignments,
- **WHEN** they attempt to play a league fixture,
- **THEN** `execute_league_match` rejects with the same guard as bot/friendly matches.

#### AC-26d: Hub Dashboard
- **GIVEN** `/league hub` with an active season,
- **THEN** the embed shows: table position, points, GD, form (last 5), next opponent, matchday countdown, season progress.

#### AC-26e: Season Prizes
- **GIVEN** an admin ends a season,
- **THEN** `distribute_season_prizes` awards coins by finish tier and writes `player_league_history` + `league_season_awards`.

#### AC-26f: Matchday Spectacle
- **GIVEN** a league match starts in the journal,
- **THEN** pre-match lineup pitch images may be posted, live ticker runs, and post-match updates live standings embed.

#### AC-26g: Registration & Config
- **GIVEN** admin opens registration or configures a season,
- **THEN** `league_seasons.config_json` stores size, duration, OVR cap, bot fill, entry fee.
- **AND** hub shows registration countdown when `status='registration'`.

### US-27: League Economy Hardening

> **As a** game economy steward,
> **I want** league coin faucets and exploit vectors closed with calibrated tunables,
> **So that** immersive league mode rewards skill without inflating coins or bypassing energy gates.

**Design reference:** [`.specify/specs/v1.0.0/league-economy-calibration.md`](league-economy-calibration.md)

#### AC-27a: Entry Fee Sink
- **GIVEN** an admin starts a season with `config_json.entry_fee_coins > 0` (or global `league_entry_fee_coins`),
- **WHEN** each human is inserted into `league_participants`,
- **THEN** `apply_club_economy` debits the fee with source `league_entry` and idempotency key `league_entry:{season_id}:{player_id}`.
- **AND** managers with insufficient coins are skipped with an admin-visible warning (not silently added).
- **AND** fee may scale by division tier: `base + tier × league_entry_fee_per_division` (from `game_config`).

#### AC-27b: Entry Fee Refund
- **GIVEN** a season ends normally via `distribute_season_prizes`,
- **WHEN** a human participant finished with `is_active = TRUE`,
- **THEN** entry fee is refunded via `apply_club_economy` source `league_entry_refund` (same idempotency pattern).
- **AND** kicked/inactive/disbanded participants receive **no** refund.

#### AC-27c: Auto-Sim Coin Multiplier
- **GIVEN** a league fixture is resolved by auto-sim (`active_player_id IS NULL`),
- **WHEN** match coins are granted,
- **THEN** payout = `floor(match_coins × league_auto_sim_coin_mult)` (default **0.5**).
- **AND** season prizes and milestones are **unchanged** (manual engagement still rewarded).
- **AND** XP pipe is unchanged (energy bypass for XP is acceptable at v1; monitor OVR growth).

#### AC-27d: Calibrated `game_config` Defaults
- **GIVEN** migration `033_league_economy_calibration.sql` is applied,
- **THEN** defaults match calibration targets:

| Key | Target |
|-----|--------|
| `league_season_prize_pool_base` | 3500 |
| `league_participation_coins` | 150 |
| `league_milestone_bonus_coins` | 100 |
| `match_league_win_min` | 250 |
| `match_league_win_max` | 400 |
| `league_entry_fee_coins` | 1500 |
| `league_entry_fee_per_division` | 250 |
| `league_auto_sim_coin_mult` | 0.5 |

#### AC-27e: Join Eligibility Gate
- **GIVEN** a manager clicks Register in `/league hub`,
- **WHEN** `league_join_min_matches` (default 10) or `league_join_min_account_days` (default 7) is not met,
- **THEN** registration is rejected with a clear ephemeral message (matches played / days remaining).
- **AND** gate reads `players.matches_played` and `players.created_at` only (no new columns).

#### AC-27f: Hub & Admin Transparency
- **GIVEN** registration is open,
- **THEN** hub embed shows entry fee (if any) and eligibility requirements.
- **GIVEN** season start,
- **THEN** admin confirmation lists managers charged vs skipped (insufficient coins).

#### AC-27g: Simulation & Monitoring
- **GIVEN** `scripts/simulate_league_economy.py` is run post-calibration,
- **THEN** Grassroots champion (12W, 3 milestones, manual) gross injection is **~5,480 coins** (down from ~7,150 pre-US-27); entry fee is refunded on season complete.
- **AND** calibration doc §7 monitoring thresholds remain the ops playbook (ledger SQL, no admin slash).

#### Deferred (not US-27)
- Season-end XP bonus, untradeable league card prizes, promotion/relegation prize tiers, separate league-energy bar.

### US-28: League Season Announcement & Dual Threads

> **As a** guild league participant,
> **I want** a striking season launch and separated official standings vs live commentary threads,
> **So that** the league channel stays organized and matchday feels professional.

#### AC-28a: Banner Season Announcement
- **GIVEN** an admin starts a season and `league_channel_id` is configured,
- **WHEN** the season is announced,
- **THEN** the bot posts role ping (if configured) + plain text `Check /league hub...` + gold embed with `assets/background.png` and registered club list.
- **AND** footer shows matchday count.

#### AC-28b: Dual Locked Threads at Season Start
- **GIVEN** season start succeeds,
- **THEN** two public threads are created: `📊 League Journal` (official record) and `🎙️ MatchDay` (live commentary).
- **AND** both threads are **locked** immediately (bot-only posts).
- **AND** thread IDs are stored on `league_seasons` (`journal_thread_id`, `matchday_thread_id`, etc.) with `thread_format='dual_v2'`.

#### AC-28c: Output Split
- **GIVEN** `thread_format='dual_v2'`,
- **WHEN** a league match runs,
- **THEN** live commentary, pitch images, and press conference post to **MatchDay**.
- **AND** pinned/edited standings + compact result lines post to **League Journal** only.

#### AC-28d: Legacy Migration
- **GIVEN** an active season with `thread_format='legacy'` (started before US-28),
- **THEN** matches continue using single `get_or_create_league_journal` until season ends.
- **AND** new seasons always use `dual_v2`.

#### AC-28e: Season End
- **GIVEN** admin ends a `dual_v2` season,
- **THEN** season summary posts to Journal thread; both threads are locked and archived.
- **AND** parent channel receives conclusion announcement (unchanged).

#### AC-28f: Fallback
- **GIVEN** thread creation fails (missing permissions),
- **THEN** banner announcement still posts; season uses legacy journal fallback; error is logged.

---

### US-29: Match Loop Hardening & Dead Code Removal (v2.1)

> **As a** game operator and registered manager,
> **I want** bot and friendly matches to use the same economy/XP pipes as league matches, schema/RPC drift closed, and legacy debug paths removed,
> **So that** progression and economy rules are consistent, auditable, and production-safe.

**Audit source:** Codebase audit (Jul 2026) — bot path regressions vs US-23/US-25, `process_match_result` column drift, scheduler/UX gaps.

**Design reference:** [`.specify/specs/v1.0.0/league-mode-design.md`](league-mode-design.md) § Decoupled League Systems (weekly bot ladder remains; guild seasons stay fixture-based).

#### AC-29a: Bot Match Economy v2 (closes US-25b gap)
- **GIVEN** `economy_v2_enabled = true` and a manager plays `/battle bot`,
- **WHEN** the match concludes,
- **THEN** coins and energy mutate **only** via `apply_match_economy` / `apply_club_economy` with idempotency key `match_run_id`.
- **AND** energy pre-check uses `sync_action_energy` + `match_energy_cost('bot')` (default **20**), not legacy `players.energy < 10`.
- **AND** coin payout uses `compute_bot_match_coins(result, global_division.win_coins)` — not inline `win_coins` / hardcoded loss consolation.
- **AND** no direct `players.update({coins, energy})` in `battle_cog` bot path.

#### AC-29b: Bot Match XP Pipe (closes US-23e gap)
- **GIVEN** a bot match concludes for a human manager's XI,
- **WHEN** rewards are applied,
- **THEN** XP uses `build_process_match_result_rpc(..., match_type='bot')` with per-card `p_xp_amounts` — **never** hardcoded `p_xp_amount: 15`.
- **AND** evolution ticks remain inside `process_match_result` (no duplicate `tick_evolution_match_progress` on the same cards in the same flow).
- **AND** daily match XP cap per card (US-24) applies to bot and league match types. Friendly matches grant **no XP**.

#### AC-29c: `process_match_result` Schema Alignment
- **GIVEN** migration `035_match_result_schema_fix.sql` is applied,
- **THEN** `player_cards.recent_match_ratings` exists (`JSONB`, default `'[]'`).
- **AND** `process_match_result` reads potential ceiling from `base_potential` (not undefined `initial_potential` column).
- **AND** `verify_required_schema.sql` guards `recent_match_ratings`, `process_match_result`, and migration 034 `announcement_message_id`.

#### AC-29d: Atomic Daily Pack Claim
- **GIVEN** a manager claims a free pack from `/store`,
- **WHEN** `claim_daily_pack(p_club_id)` runs,
- **THEN** cooldown check, `last_claim_at` update, and card inserts occur in **one** RPC transaction.
- **AND** failed card insert does not consume the 22h cooldown.
- **AND** `store_cog` calls the RPC only — no sequential `UPDATE` then `INSERT` in app code.

#### AC-29e: Slash Command Defer Compliance
- **GIVEN** `/battle bot`, `/battle friendly`, or `/register` (new-user path) is invoked,
- **THEN** `interaction.response.defer` runs **before** any Supabase query or match simulation.
- **AND** handlers use `followup.send` / `followup.edit` after defer (no bare `followup` without prior defer).

#### AC-29f: Matchday Reminder Dedup
- **GIVEN** `league_matchday_reminder_job` runs hourly,
- **WHEN** a matchday window is within 6 hours of closing,
- **THEN** each human participant receives **at most one** DM per `(season_id, matchday)` pair.
- **AND** dedup state is persisted (e.g. `league_matchday_reminders` table or milestone-style flag).

#### AC-29g: Production Hygiene — Debug Instrumentation Removed
- **GIVEN** deploy to production,
- **THEN** no cog/core module writes to `debug-*.log` files (`battle_cog`, `league_cog`, `league_journal`, `development_cog`, `squad_cog`).
- **AND** `AGENTS.md` verification checklist item for debug removal passes.

#### AC-29h: Dead Code & Legacy Path Removal
- **GIVEN** economy v2 is the only supported match economy (`economy_v2_enabled` defaults true),
- **THEN** direct `players.coins` / `energy` fallback branches in `league_rewards.py` and inline bot payout math are **deleted** (not left behind).
- **AND** `energy_regen_job` is removed from scheduler **or** repurposed to call `sync_action_energy` batch — not a no-op `regen_energy_tick` cron.
- **AND** disabled "Ranked (Soon)" UI stub in `battle_cog` is removed.
- **AND** `README.md` no longer references deleted `gacha_cog.py` / `/gacha-claim` (points to `/store`).

#### AC-29i: Division Ladder Clarity (no accidental cross-wipe)
- **GIVEN** `weekly_league_reset_job` runs Monday 00:00 UTC,
- **THEN** it promotes/relegates on `players.division` + `players.league_points` / `goal_difference` only (weekly **Division Rank** ladder per `league-mode-design.md`).
- **AND** it does **not** modify `global_lp`, guild `league_fixtures`, or season standings.
- **AND** `/profile` labels `league_points` as **Division Rank (weekly)** and does not imply guild season rank.

#### AC-29j: Test & CI Health
- **GIVEN** `pytest tests/` runs in CI,
- **THEN** `tests/test_training.py` imports from `packages/training` (or is removed if superseded by `test_progression.py`).
- **AND** new tests cover bot/friendly economy+XP wiring (`tests/test_match_loop_hardening.py` or extend `test_match_xp` / `test_economy_flows`).

#### AC-29k: Ship Checklist
- **GIVEN** implementation complete,
- **THEN** migration 035 applied, `verify_required_schema.sql` passes, `change_log.md` updated for player-facing match economy/XP changes.
- **AND** grep confirms zero `p_xp_amount": 15` and zero direct `players.update` coin mutations in `apps/discord_bot/cogs/battle_cog.py`.

---

## 30. League Points Integration & `/leaderboard` (US-30)

### Terminology (3 tracks — do not conflate)

| DB column | Player label | Earned from |
|-----------|--------------|-------------|
| `players.league_points` | **Division Rank** (weekly) | Bot battles only (3/1/0) |
| `players.global_lp` | **Global LP** (persistent) | Bot battles (+15/+5/−10) |
| Fixture-derived `points` | **Season Pts** | Guild league matches only |

### US-30: `/leaderboard` Rankings Hub

> **As a** registered manager,
> **I want to** view my standing across Division Rank, Global LP, and guild Season tables in one place,
> **So that** competitive points feel meaningful and I know where I rank.

**Acceptance Criteria:**

#### AC-30a: Command & session
- **GIVEN** a registered player runs `/leaderboard`,
- **THEN** the bot defers ephemeral immediately and shows an embed with three tab buttons: **Division Rank**, **Global LP**, **Season**.
- **AND** only the invoking manager can use the buttons (`interaction_check`).

#### AC-30b: Division Rank tab
- **GIVEN** Division Rank tab is active,
- **THEN** the embed lists human players in the selected server division sorted by `league_points` DESC, `goal_difference` DESC.
- **AND** a division Select defaults to the viewer's `players.division`.
- **AND** the viewer's rank, weekly tier progress (6/12/18), promo/releg zones, and Monday reset countdown are shown.
- **AND** a **Claim Weekly** button appears when an unclaimed tier is available; claim uses RPC `claim_weekly_rank_tier` via `apply_club_economy`.

#### AC-30c: Global LP tab
- **GIVEN** Global LP tab is active,
- **THEN** the embed lists top human players by `global_lp` with global division tier labels.
- **AND** the viewer's global rank and LP progress bar to next tier are shown.

#### AC-30d: Season tab
- **GIVEN** an active guild season exists,
- **THEN** the Season tab reuses `fetch_standings()` + `format_standings_table()` (fixture-derived Season Pts).
- **AND** empty states handle: no guild, no league, no active season, spectator not registered.

#### AC-30e: Post-match labels
- **GIVEN** a bot battle ends,
- **THEN** rewards show **Division Rank** and **Global LP** (not ambiguous "league pts").
- **GIVEN** a guild league match ends,
- **THEN** rewards show actual economy v2 coins and **Season Pts**.

#### AC-30f: Weekly tier economy
- **GIVEN** weekly Division Rank pts cross 6, 12, or 18 thresholds,
- **THEN** coin rewards scale by server division tier via `apply_club_economy` with idempotency key `weekly_tier:{iso_week}:{player_id}:{tier}`.
- **AND** unclaimed tiers reset Monday 00:00 UTC with `league_points`.

#### AC-30g: Pure logic consolidation
- **GIVEN** match result scoring,
- **THEN** all W/D/L and LP formulas live in `packages/leagues/leagues/match_points.py` (single source of truth).

