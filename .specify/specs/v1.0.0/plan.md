# ElevenBoss v1.0.0 — Technical Plan (`plan.md`)

**Feature**: Core Game Loop — v1.0.0 Initial Release
**Status**: Draft
**Depends On**: `spec.md` v1.0.0

---

## 1. Repository Structure

```
ElevenBoss/
├── apps/
│   └── discord_bot/
│       ├── __init__.py
│       ├── main.py
│       ├── cogs/
│       │   ├── __init__.py
│       │   ├── onboarding_cog.py    # /register command + guard check
│       │   ├── gacha_cog.py
│       │   ├── squad_cog.py
│       │   ├── match_cog.py
│       │   ├── player_cog.py
│       │   └── profile_cog.py
│       ├── core/                    # Internal app-layer utilities (may import discord)
│       │   ├── __init__.py
│       │   └── thread_manager.py    # Thread lifecycle: create, dispatch UI, cleanup
│       ├── embeds/
│       │   ├── __init__.py
│       │   ├── onboarding_embeds.py # Welcome, confirmation, recruitment, final embeds
│       │   ├── gacha_embeds.py
│       │   ├── match_embeds.py
│       │   └── common_embeds.py
│       ├── middleware/
│       │   └── guard.py             # ensure_registered() → prompts /register (no auto-create)
│       └── db/
│           └── client.py
├── packages/
│   ├── match_engine/
│   │   ├── pyproject.toml
│   │   └── match_engine/
│   │       ├── __init__.py
│   │       ├── models.py
│   │       └── simulator.py
│   ├── economy/
│   │   ├── pyproject.toml
│   │   └── economy/
│   │       ├── __init__.py
│   │       ├── models.py
│   │       └── calculator.py
│   ├── gacha/
│   │   ├── pyproject.toml
│   │   └── gacha/
│   │       ├── __init__.py
│   │       ├── models.py
│   │       ├── generator.py
│   │       └── data/player_names.json
│   ├── leagues/
│   │   ├── pyproject.toml
│   │   └── leagues/
│   │       ├── __init__.py
│   │       ├── models.py
│   │       └── calculator.py
│   └── energy/
│       ├── pyproject.toml
│       └── energy/
│           ├── __init__.py
│           ├── models.py
│           └── calculator.py
├── supabase/
│   └── migrations/
│       ├── 001_initial_schema.sql
│       └── 002_indexes.sql
├── .specify/
│   ├── memory/constitution.md
│   └── specs/v1.0.0/
│       ├── spec.md
│       ├── plan.md
│       └── tasks.md
├── pyproject.toml
├── requirements.txt
└── .env
```

---

## 2. Database Schema

### `players` Table
```sql
CREATE TABLE players (
    discord_id        BIGINT PRIMARY KEY,
    username          TEXT NOT NULL,
    club_name         TEXT NOT NULL DEFAULT '',
    manager_name      TEXT NOT NULL DEFAULT '',
    coins             INTEGER NOT NULL DEFAULT 500 CHECK (coins >= 0),
    energy            INTEGER NOT NULL DEFAULT 100 CHECK (energy >= 0 AND energy <= 100),
    max_energy        INTEGER NOT NULL DEFAULT 100,
    division          TEXT NOT NULL DEFAULT 'Grassroots',
    league_points     INTEGER NOT NULL DEFAULT 0,
    goal_difference   INTEGER NOT NULL DEFAULT 0,
    matches_played    INTEGER NOT NULL DEFAULT 0,
    wins              INTEGER NOT NULL DEFAULT 0,
    draws             INTEGER NOT NULL DEFAULT 0,
    losses            INTEGER NOT NULL DEFAULT 0,
    last_claim_at     TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### `player_cards` Table
```sql
CREATE TABLE player_cards (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id      BIGINT NOT NULL REFERENCES players(discord_id) ON DELETE CASCADE,
    name          TEXT NOT NULL,
    position      TEXT NOT NULL CHECK (position IN ('GK','DEF','MID','FWD')),
    rarity        TEXT NOT NULL CHECK (rarity IN ('Common','Rare','Epic','Legendary')),
    base_rating   INTEGER NOT NULL,
    level         INTEGER NOT NULL DEFAULT 1,
    overall       INTEGER NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### `squads` Table
```sql
CREATE TABLE squads (
    discord_id    BIGINT PRIMARY KEY REFERENCES players(discord_id) ON DELETE CASCADE,
    formation     TEXT NOT NULL DEFAULT '4-4-2',
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```
The `squads` table links one-to-one with a player's Discord ID, keeping track of their active formation (e.g., `'4-4-2'`).

### `squad_assignments` Table
```sql
CREATE TABLE squad_assignments (
    discord_id      BIGINT NOT NULL REFERENCES squads(discord_id) ON DELETE CASCADE,
    player_card_id  UUID NOT NULL REFERENCES player_cards(id) ON DELETE CASCADE,
    position_slot   INTEGER NOT NULL CHECK (position_slot >= 1 AND position_slot <= 11),
    PRIMARY KEY (discord_id, player_card_id),
    UNIQUE (discord_id, position_slot)
);
```
This is a junction table mapping a squad to its starting 11 player cards. It is subject to two critical integrity constraints:
- **Composite `PRIMARY KEY (discord_id, player_card_id)`:** Enforces that a specific player card UUID can only be assigned to a single manager's squad assignment at most once.
- **`UNIQUE (discord_id, position_slot)`:** Enforces that each position slot (1-11) is occupied by at most one player card for a given manager.

### `match_history` Table
```sql
CREATE TABLE match_history (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    player_id         BIGINT NOT NULL REFERENCES players(discord_id),
    result            TEXT NOT NULL CHECK (result IN ('win','draw','loss')),
    my_rating         NUMERIC(5,2) NOT NULL,
    opponent_rating   NUMERIC(5,2) NOT NULL,
    goals_for         INTEGER NOT NULL,
    goals_against     INTEGER NOT NULL,
    coins_earned      INTEGER NOT NULL,
    points_earned     INTEGER NOT NULL,
    played_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## 3. Package Specifications

### `match_engine`
- **Input**: `MatchInput(my_players: list[PlayerCard], opponent_base_rating: float)`
- **Output**: `MatchResult(result, goals_for, goals_against, my_rating, opponent_rating, coins_earned, points_earned)`
- **Algorithm**: mean rating -> normal distribution modifier (±15%) -> compare -> scoreline

### `economy`
- `level_up_cost(current_level: int) -> int`: `round((level ** 1.5) * 100 / 10) * 10`
- `rarity_rating_cap(rarity: str) -> int`: Common=75, Rare=84, Epic=90, Legendary=99
- No DB calls — pure business rules only.

### `gacha`
- `generate_pack(n: int = 5) -> GachaPack`
  - Weighted rarity: Common 60%, Rare 30%, Epic 8%, Legendary 2%
  - Names from bundled `data/player_names.json`
- `generate_starter_squad() -> StarterSquad` *(used exclusively by onboarding)*
  - Returns a guaranteed 11-player squad with strict positional composition:
    - **1 GK** — Common rarity, position `GK`.
    - **4 DEF** — Common rarity, position `DEF`.
    - **4 MID** — Common rarity, position `MID`.
    - **2 FWD** — Common rarity, position `FWD`.
    - **1 Marquee** — Rare (80% chance) or Epic (20% chance) rarity. Position drawn proportionally from non-GK slots (`DEF/MID/FWD`). Replaces the Common card in that positional slot.
  - Total card breakdown: **10 Common + 1 Rare/Epic = 11 cards**.
  - Cards are ordered: `[GK, DEF×4, MID×4, FWD×2]` — the Marquee card occupies index 0 of the returned list (surfaced as Captain), regardless of its position, for display purposes. The squad assignment maps by position, not index order.

**New Pydantic Model** (add to `packages/gacha/gacha/models.py`):
```python
class StarterSquad(BaseModel):
    marquee: GachaPlayer           # Rare or Epic — the Captain
    youth: list[GachaPlayer]       # Exactly 10 Common players

    @property
    def all_players(self) -> list[GachaPlayer]:
        """Full 11-player list: [marquee] + youth, ordered GK→DEF→MID→FWD."""
        ordered = sorted(
            [self.marquee] + self.youth,
            key=lambda p: ["GK", "DEF", "MID", "FWD"].index(p.position)
        )
        return ordered
```

### `leagues`
- `compute_promotions_relegations(entries: list[LeagueEntry]) -> PromotionResult`
- Top 20% promoted, bottom 20% relegated (min 1 each)

### `energy`
- `ticks_to_full(current, max_energy, regen_per_tick=2) -> int`
- `apply_regen_tick(current, max_energy, regen_per_tick=2) -> int`

---

## 4. Discord Bot Architecture

- `intents = discord.Intents.default()` — NO `MESSAGE_CONTENT` intent
- All commands via `app_commands.Group` or `@app_commands.command`
- All commands `defer(ephemeral=True)` immediately

### `middleware/guard.py` — Registration Gatekeeper

Unregistered users are blocked from executing core gameplay commands (such as `/match play`, `/gacha claim`, `/squad view`, etc.) by a middleware check:
- **`ensure_registered(interaction: discord.Interaction) -> bool`**: Implemented using discord.py's `@app_commands.check` decorator on commands/cogs.
- **Verification Logic**: Queries the `players` table using the user's `discord_id`.
- **Response**: If unregistered, intercepts the interaction and returns an ephemeral error embed directing them to run `/register`. It returns `False`, blocking execution. No database rows are created during this check.

### Squad Junction Queries & Slot Assignment

Managing the Starting 11 and squad configuration uses junction table queries against Supabase:
- **Fetching the Starting 11**: Retrieved via a joined query between `squad_assignments` and `player_cards` (specifically, `.select("position_slot, player_cards(*)")`), filtering by the user's `discord_id`.
- **Updating a Squad Slot**:
  1. **Conflict Resolution**: To avoid violating the composite `PRIMARY KEY` or `UNIQUE` constraints (e.g., if a player card is already assigned to a different slot), the command first runs a `DELETE` query on `squad_assignments` targeting the user's `discord_id` and the chosen `player_card_id`.
  2. **Assignment Update**: An `UPSERT` operation is performed on `squad_assignments` containing `discord_id`, `position_slot`, and `player_card_id` to assign the player to the new slot.


### `core/thread_manager.py` — Thread Lifecycle Module

This is an internal Discord-aware module (lives in `apps/discord_bot/core/`, **not** in `packages/`). It owns the full onboarding thread lifecycle.

```python
class ThreadManager:
    """
    Manages the creation, UI dispatch, and safe cleanup of onboarding threads.
    """
    def __init__(self, bot: commands.Bot) -> None: ...

    async def create_onboarding_thread(
        self,
        interaction: discord.Interaction,
        owner_id: int,
    ) -> discord.Thread:
        """Creates the private/public thread and sends the initial welcome embed."""
        ...

    async def delete_thread_after(
        self,
        thread: discord.Thread,
        delay_seconds: int,
        *,
        countdown_message: discord.Message | None = None,
    ) -> None:
        """Waits `delay_seconds`, then deletes the thread. Optionally edits
        countdown_message to display a live countdown before deletion."""
        ...

    def check_owner(self, interaction: discord.Interaction, owner_id: int) -> bool:
        """Returns True if interaction.user.id == owner_id."""
        ...
```

### Onboarding Flow State Machine

The `/register` command drives a stateful modal+view flow entirely within the thread:

```
/register
  └─► ThreadManager.create_onboarding_thread()
        └─► Thread created; WelcomeView ("Begin Setup →" button) sent
              └─► [User clicks Begin Setup]
                    └─► ClubSetupModal presented
                          └─► [User submits Modal]
                                └─► ConfirmationView ("Confirm" / "Edit" buttons) sent
                                      ├─► [Edit] → re-present ClubSetupModal
                                      └─► [Confirm]
                                            └─► Animation loop (7 message.edit() steps)
                                                  └─► gacha.generate_starter_squad()
                                                        ├─► Returns: StarterSquad
                                                        │     .marquee  → 1× Rare/Epic (Captain)
                                                        │     .youth    → 10× Common (positional guarantee)
                                                        └─► Supabase RPC register_new_player():
                                                              1. INSERT players row
                                                              2. INSERT 11 player_cards rows
                                                                 └─ collect returned UUIDs
                                                              3. INSERT squads row with formation='4-4-2'
                                                              4. INSERT 11 squad_assignments rows
                                                                 mapping to slots 1-11
                                                                   └─► Marquee Reveal embed
                                                                         (Captain stats displayed)
                                                                           └─► Twin-embed Registration Complete
                                                                                 (Captain stats + 10 youth list)
                                                                                   └─► delete_thread_after(delay=10)
```

### Error Recovery

- Any uncaught exception at any wizard step → catch in cog → `thread_manager.delete_thread_after(thread, 15)` with error embed.
- View `on_timeout` (60-min inactivity) → disable all buttons; thread auto-archives via Discord.

### APScheduler Jobs
- Energy regen: `"interval", minutes=5` — Bulk UPDATE on `players` table
- League reset: `"cron", day_of_week="mon", hour=0` — Compute promotions, bulk UPDATE, send DMs

---

## 5. Dependency Management

### `requirements.txt`
```
discord.py>=2.7.0
supabase>=2.0.0
pydantic>=2.0.0
apscheduler>=3.10.0
python-dotenv>=1.0.0
```

### Local Package Install (editable)
```bash
pip install -e packages/match_engine
pip install -e packages/economy
pip install -e packages/gacha
pip install -e packages/leagues
pip install -e packages/energy
```

---

## 6. Key Design Decisions

| Decision | Rationale |
|---|---|
| Packages return Pydantic models, NOT write to DB | Enforces Constitution Principle I (package boundary) |
| `ensure_registered` **prompts** instead of auto-creating | Explicit onboarding creates player investment; no orphaned half-created accounts |
| `ThreadManager` in `apps/core/` (not `packages/`) | Needs `discord.Thread` — Constitution forbids discord imports in packages |
| Thread auto-archive (60 min) as inactivity timeout | Leverages Discord's native mechanism; no bot-side polling or cleanup timers needed |
| `discord.ui.Modal` for club/manager name | Structured input with built-in validation; no raw message parsing (Constitution Principle IV) |
| Sequential `message.edit()` for recruitment animation | Single persistent message; no message spam; natural cinematic pacing |
| APScheduler (not Celery/Redis) | Simpler ops footprint; runs in bot's event loop |
| Bulk UPDATE for energy regen | Single DB round-trip for all players; efficient at scale |
| SQL stored procedures for financial transactions | PostgreSQL-level atomicity stronger than app-level retry |

---

## 7. ElevenBoss v1.1 Architecture (Live Match Commentary)

### A. Pure Logic Layer (`packages/engine/`)

This layer remains 100% database-agnostic and Discord-agnostic, ensuring business rules can be reused across any UI or platform.

#### 1. Models (`packages/engine/models.py`)
Add the following models:
* `EventType` (Enum): Represents the type of match event (e.g., `KICKOFF`, `GOAL`, `MISS`, `SAVE`, `YELLOW_CARD`, `FULL_TIME`).
* `MatchEvent` (Pydantic Model):
  * `minute` (int): Match minute (1-90).
  * `type` (EventType): The type of event.
  * `text` (str): Commentary text of the event. Must use pure text (no Discord `<@id>` mentions) to ensure reusability.
  * `score_update` (str | None): Current score update formatted as `HomeScore - AwayScore` (e.g. `1 - 0`), if any.

#### 2. Commentary Generator (`packages/engine/commentary.py`)
* Implement a stateless, pure function: `generate_match_script(result: MatchResult) -> list[MatchEvent]`.
* Inputs: The simulated `MatchResult` (containing final score, team names, statistics).
* Outputs: A list of 5 to 7 chronological `MatchEvent` objects beginning with `KICKOFF` (0'), containing 3 to 5 key actions (goals, saves, cards) mapped to realistic minutes, and concluding with `FULL_TIME` (90') matching the simulated score.

---

### B. Application Presentation Layer (`apps/discord_bot/cogs/match_cog.py`)

This layer handles Discord slash command invocation, UI rendering, pacing, and database mutation scheduling.

#### 1. Command Invocation
* Command `/match play` must immediately invoke `await interaction.response.defer(ephemeral=False)`.

#### 2. Live Stadium Thread & Ticker Flow
* **Match Ticket:** Send a rich embed to the main channel representing the match ticket.
* **Public Thread Creation:** Create a public thread on the ticket message: `await message.create_thread(name=f"🏟️ {home_team} vs {away_team} - Live", auto_archive_duration=60)`.
* **Fallback Channel Handling:** If thread creation is unsupported (e.g. DMs, missing permissions), catch the exception, log a warning, and fall back to streaming events inside the parent channel.
* **Commentary Stream:** Send the initial kickoff message inside the thread (or channel if fallback) and run the live commentary loop:
  * Iterate through `MatchEvent` list. For each event, edit the commentary message with a 5-event live-scroll history.
  * Pause for `asyncio.sleep(1.5)` between events (`2.0` on full time).
* **Press Conference Summary:** Upon completion, send a separate "Post-Match Press Conference" embed in the thread showing stats (Possession, Shots, MOTM) and rewards.
* **Rename & Archive Cleanup:** Edit the thread name to display the final score (e.g. `🏆 {home_team} {score} {away_team}`). Schedule a background task (`asyncio.create_task`) that sleeps for 180 seconds and then locks and archives the thread (`await thread.edit(locked=True, archived=True)`).

#### 3. Delayed Database Mutations
* **CRITICAL**: The bot must NOT perform any database writes (Supabase RPCs or upserts for energy cost, coin rewards, XP, match history insert) until the live ticker loop finishes.
* If the loop crashes or the connection is severed mid-match, no rewards are given and no energy is deducted. This prevents half-applied states or reward duplication.

---

## 8. ElevenBoss v1.2 Architecture (Economy & Training System)

### A. Database Extensions & Ledger

#### 1. Table Alterations
* **`players` table extension:** Add `tokens` (INT default 0) and `training_slots_max` (INT default 2) columns. Convert `coins` from `INTEGER` to `BIGINT`.

#### 2. Economy Ledger
```sql
CREATE TABLE public.economy_ledger (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    club_id     BIGINT NOT NULL REFERENCES public.players(discord_id) ON DELETE CASCADE,
    amount      BIGINT NOT NULL,
    currency    TEXT NOT NULL CHECK (currency IN ('coins', 'tokens')),
    source      TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

#### 3. Active Training Drills
```sql
CREATE TABLE public.active_training (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    club_id     BIGINT NOT NULL REFERENCES public.players(discord_id) ON DELETE CASCADE,
    card_id     UUID NOT NULL REFERENCES public.player_cards(id) ON DELETE CASCADE,
    drill_type  TEXT NOT NULL CHECK (drill_type IN ('cardio', 'tactics', 'match_prep')),
    end_time    TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

### B. Atomic SQL RPC Transactions

#### 1. `process_training_start`
* **Purpose:** Safely starts a training drill if the user has slots available and sufficient coins.
* **Arguments:** `p_club_id BIGINT, p_card_id UUID, p_drill TEXT, p_cost BIGINT, p_duration_hours NUMERIC`.
* **Execution:**
  1. Lock `players` row.
  2. Verify player owns `player_cards` card.
  3. Verify card is not already training.
  4. Verify active drills count is less than `training_slots_max`.
  5. Verify coins are greater than or equal to `p_cost`.
  6. Deduct `p_cost` from `players.coins`.
  7. Insert negative amount transaction log into `economy_ledger`.
  8. Insert training drill row into `active_training`.

#### 2. `process_agent_sale`
* **Purpose:** Transactionally deletes a player card, credits the sale value in coins, and logs it.
* **Arguments:** `p_club_id BIGINT, p_card_id UUID, p_sale_value BIGINT`.
* **Execution:**
  1. Verify card ownership.
  2. Delete player card from `player_cards`.
  3. Add `p_sale_value` to `players.coins`.
  4. Insert transaction log into `economy_ledger`.

---

### C. Pure Logic Packages

#### 1. Economy Package (`packages/economy/`)
* **`calculate_weekly_wages(squad, config)`:** Calculates wage bill forecast. Wage: `(OVR - 40)^2 * wage_scale_factor + 10`.
* **`generate_agent_offer(player_ovr, player_rarity, config)`:** Computes buyer offer: `((OVR - 45)^2.5 * 1.5 + 50) * rarity_multiplier`.

#### 2. Training Package (`packages/training/`)
* **`calculate_xp_gain(drill, player_lvl, config)`:** Computes training drill XP: `drill_base_xp * (1.0 / (1.0 + 0.05 * (player_lvl - 1)))`.

---

## 9. ElevenBoss v1.3 Architecture (Player Lifecycle & Evolutions)

### A. Database Extensions & Evolution Tracking

#### 1. Table Alterations
* **`player_cards` table extension:** Add `role` (TEXT default 'Balanced'), `morale` (INT default 80), `contract_expires_at` (TIMESTAMPTZ), `potential` (INT), and `age` (INT default 25). Also ensure it has `xp` (INT default 0).

#### 2. Player PlayStyles
```sql
CREATE TABLE public.player_playstyles (
    card_id        UUID NOT NULL REFERENCES public.player_cards(id) ON DELETE CASCADE,
    playstyle_key  TEXT NOT NULL,
    PRIMARY KEY (card_id, playstyle_key)
);
```

#### 3. Active Evolutions
```sql
CREATE TABLE public.active_evolutions (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    card_id           UUID NOT NULL REFERENCES public.player_cards(id) ON DELETE CASCADE,
    evolution_id      TEXT NOT NULL,
    target_metric     TEXT NOT NULL,
    current_progress  INTEGER NOT NULL DEFAULT 0,
    target_goal       INTEGER NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

#### 4. Player XP Logs
```sql
CREATE TABLE public.player_xp_log (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    card_id     UUID NOT NULL REFERENCES public.player_cards(id) ON DELETE CASCADE,
    xp_amount   INTEGER NOT NULL,
    source      TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

### B. Atomic SQL RPC Transactions

#### 1. `process_match_result`
* **Purpose:** Atomically updates player metrics (distributes role-based XP, updates evolutions progress, and adjusts morale) after a simulated match.
* **Arguments:** `p_result TEXT, p_card_ids UUID[], p_xp_amount INTEGER`.
* **Execution:**
  1. Update `player_cards` set `xp = xp + p_xp_amount` for all cards in `p_card_ids`.
  2. Log XP additions to `player_xp_log` for each card.
  3. Increment `current_progress` in `active_evolutions` for cards in `p_card_ids` where target_metric is matched.
  4. Adjust morale: +5 for win, +1 for draw, -5 for loss, clamped to [10, 100].

#### 2. `renew_contract`
* **Purpose:** Deducts contract costs from coins and extends the expiry timestamp.
* **Arguments:** `p_club_id BIGINT, p_card_id UUID, p_cost BIGINT, p_extension_days INTEGER`.
* **Execution:**
  1. Verify card ownership.
  2. Verify player coins >= `p_cost`.
  3. Deduct `p_cost` from `players.coins`.
  4. Update `player_cards` contract expiry date.
  5. Log ledger transaction.

---

### C. Pure Logic Player Engine Package (`packages/player_engine/`)
* **`calculate_level(xp)`**: Returns the level given current XP based on the exponential curve: `100 * 1.12^level`.
* **`roll_dynamic_potential(age, recent_ratings)`**: Calculates dynamic potential improvements for young players (age 16-21).
* **`calculate_contract_renewal_cost(ovr, config)`**: Computes coin renewal fees.

---

## 10. ElevenBoss v1.4 Architecture (Live Stadium V2 — Dynamic Match Engine)

### A. Core Commentary Data Layer
* **`commentary_bank.json`**: Static JSON file storing commentary templates categorized by events (`KICKOFF`, `CHANCE`, `GOAL`, `FOUL`, `MISS`, `FULL_TIME`). Contains metadata fields for `tags` and `urgency`.
* **`CommentaryEngine`**: Python class loaded at runtime to filter lines using active context tags, resolving placeholder formatting.
  * **`bold_vars(variables: dict) -> dict`**: Helper utility to wrap string values in Markdown double-asterisks (`**`), stripping existing `**` beforehand to prevent double-bolding (`****`). Leaves non-string values (e.g. integers) untouched.
  * **`render_commentary(template: str, variables: dict) -> str`**: Hydrates templates by first passing variables through `bold_vars`, then using `.format()`.
  * The `get_commentary()` method in `CommentaryEngine` delegates formatting to `render_commentary()`.

### B. Live Simulator State Machine (`v2_simulator.py`)
* **`MatchState`**: tracks home/away ratings, current score, minute, momentum (-100 to 100), tactics modifier, and a list of context tags.
* **`stream_match(state, home_squad, away_squad)`**: Async generator yielding events in random minute intervals, adjusting momentum and determining events.

### C. Touchline Interactivity Flow
* **`TouchlineView`**: Holds Attack, Defend, and Balanced buttons updating the `MatchState.home_tactics_modifier` live.
* **Commentary streaming**: Commands `/match-play` consume events from `stream_match`, editing messages in real-time, and concluding with database writes.

---

## 11. ElevenBoss v1.5 Architecture (Unified Development Center UI Refactor)

### A. Dashboard views (`development_cog.py`)
* **`DevelopmentHubView`**: The central navigation panel presenting buttons for Training Drills, Evolutions, and Skill Allocation.
* **`TrainingSubView`, `EvolutionsSubView`, `SkillsSubView`**: Independent UI Views containing navigation buttons `[⬅️ Back to Hub]` that use `interaction.response.edit_message` to transition seamlessly between screens without generating separate messages.
* **Timeout and security**: Explicit 15-minute timeout on all views.

### B. Cross-cog Route integration
* **`player_cog.py` / `/player-profile`**:
  * Button `[Start Evolution]` spawns the `EvolutionsSubView` directly, pre-filtered for the selected player ID.
  * Button `[Level Up]` spawns the `SkillsSubView` directly, pre-filtered for the selected player ID.

---

## 12. ElevenBoss v1.6 Architecture (Unified Marketplace Dashboard)

### A. Marketplace Dashboard views (`marketplace_cog.py`)
* **`MarketplaceHubView`**: The central panel presenting buttons for Sell Player, Search Market, and My Listings.
* **`SellPlayerSubView`**: In-place replacement view containing the player select dropdown, confirm button, and `[⬅️ Back to Market]` button using `interaction.response.edit_message`.
* **Deprecation of old command**: `/sell-player` in `economy_cog.py` is updated to return an ephemeral warning message guiding players to use `/marketplace`.

### B. Logical Locks
* Checks active squad assignments, active training, and active evolutions before listing player cards for sale. Calls RPC `process_agent_sale` to execute the transaction atomically.

---

## 13. ElevenBoss v1.7 Architecture (Battle Arena Hub)

### A. Battle Dashboard views (`battle_cog.py`)
* **`ArenaHubView`**: The central navigation panel presenting buttons for Bot Battle, Friendly Match, and Ranked Match.
* **Slash Command Group**:
  * `/battle` command: Spawns the central `ArenaHubView`.
  * `/battle bot` subcommand: Directly executes the live dynamic simulator loop in the Stadium thread.
* **State Swapping Navigation**:
  * Clicking `[ 🤖 Bot Battle ]` in the Hub edits the message to inform the user and programmatically launches the `run_bot_battle` simulation routine.
* **Deprecation of old command**: `/match play` in `match_cog.py` is updated to return an ephemeral warning message directing players to `/battle`.

---

## 14. ElevenBoss v1.8 Architecture (Admin Control Panel)

### A. Database Configurations (`guild_config` table)
* `guild_id` (BIGINT, PRIMARY KEY)
* `league_channel_id` (BIGINT, NULLABLE)
* `announcement_role_id` (BIGINT, NULLABLE)
* `league_status` (TEXT)
* `updated_at` (TIMESTAMP)

### B. Admin Panel Views (`admin_cog.py`)
* **Access Control**: `@app_commands.dm_only()` and `@app_commands.check(is_owner)` are enforced on the `/admin` command.
* **`GuildSelectView`**: Text select menu listing eligible mutual servers.
* **`AdminHubView`**: Primary options panel (`📢 Announcements`, `🔄 Switch Server`).
* **`AnnouncementSubView`**: Submenu displaying target channel/role config settings, with buttons for `Set Channel` and `Set Role`.
* **`ChannelSelectView` / `RoleSelectView`**: Integrates `discord.ui.ChannelSelect` and `discord.ui.RoleSelect` elements to update values in Supabase, performing strict guild-membership and bot channel permission checks.

---

## 15. ElevenBoss v1.9 Architecture (League Notification Delivery)

### A. Split-Payload Announcement Helper
* **`send_league_announcement(guild, channel_id, embed, message_body)`**: Refactors the notification formatting logic to resolve the ping issue.
  1. Fetches `announcement_role_id` for the specific `guild_id` from `guild_config`.
  2. Constructs the message `content` as: `f"<@&{role_id}>\n\n{message_body}"` if the role is found.
  3. Verifies role existence within the guild. If not found, excludes the mention to prevent broken pings.
  4. Dispatches the notification using `channel.send(content=formatted_content, embed=announcement_embed)`.

---

## 16. ElevenBoss v2.0 Architecture (League Journal & Auto-Archival)

### A. Database Schema (`guild_config` table update)
* `league_updates_thread_id` (BIGINT, NULLABLE) - Stores the centralized active League Journal thread ID.

### B. Engine Abstraction (`IMatchOutputHandler` and implementations)
* **`IMatchOutputHandler`**: Abstract interface specifying:
  - `initialize(...)`: Setup of commentary channel/thread.
  - `start_match(...)`: Post initial scoreboard state.
  - `update_ticker(...)`: Edit scoreboard/ticker state with rolling commentary updates.
  - `finalize_match(...)`: Post-match stats and rewards summary.
* **`StandardMatchHandler`**: Handles standard bot battles, spawning a unique dynamic thread and archiving it.
* **`LeagueMatchHandler`**: Handles league fixtures, directing output to the centralized Journal thread, utilizing message edits for live-scrolling commentary (rolling 5 events), and disabling views.

### C. Sequential Auto-Simulation
* **`auto_sim_expired_fixtures(...)`**: Scans for expired matches, resolves/creates the journal thread, and runs matches sequentially using the match engine (`run_league_match_simulation`) to avoid rate-limiting.

### D. Conclude Season Flow (`admin_end_season(...)`)
1. Marks the active season completed.
2. Calculates final statistics (champion, top scoring club, best defense).
3. Posts the detailed Season Summary embed to the Journal thread.
4. Spawns a background task to wait 30 seconds, then rename/lock/archive the thread.
5. Resets `league_updates_thread_id` in `guild_config` to NULL.

---

## 17. ElevenBoss v2.1 Architecture (League Stats, Logs, & UI)

### A. Database Schema (`009_league_stats.sql` migration)
* **`match_logs`**:
  - `fixture_id` (UUID, PRIMARY KEY, references `league_fixtures(id)` on delete cascade)
  - `box_score` (JSONB) - stores `{possession_home, possession_away, shots_home, shots_away, motm, home_goals, away_goals}`
  - `key_events` (JSONB) - list of events: `[{"minute": int, "type": str, "actor": str, "team": str}]`
* **`player_season_stats`**:
  - `player_id` (BIGINT, references `players(discord_id)` on delete cascade)
  - `season_id` (UUID, references `league_seasons(id)` on delete cascade)
  - `goals` (INTEGER, default 0)
  - `assists` (INTEGER, default 0)
  - `clean_sheets` (INTEGER, default 0)
  - `motm_awards` (INTEGER, default 0)
  - `average_rating` (NUMERIC(4,2), default 6.00)
  - PRIMARY KEY `(player_id, season_id)`
  - Indexes on `(season_id, goals)`, `(season_id, assists)`, `(season_id, clean_sheets)` for high-performance leaderboards.

### B. Match Engine Enhancements (`match_engine`)
* The simulation engine will return a chronological sequence of all key match events (goals, cards, injuries) within `MatchResult`.
* In `LeagueMatchHandler.finalize_match()`, write the box score and key events to `match_logs`.
* Increment participant player stats dynamically:
  - Increment goals for goalscoring players.
  - Increment assists for assisting players.
  - Increment clean sheets for players in squads that conceded 0 goals.
  - Increment MOTM awards for the designated player.
  - Update `average_rating`.

### C. Redesigned League Hub (`league_cog.py`)
* The main dashboard displays active season/matchday metadata: `"🟢 Season [N] - Matchday [X]/[Y] Active"`.
* Sub-Views:
  - **`[ 📊 Standings ]`**: Displays the current league table.
  - **`[ 👟 Player Stats ]`**: Renders three distinct leaderboards (Top Scorers, Top Assists, Clean Sheets) for the current active season.
  - **`[ 📺 Match Center ]`**: Displays a select menu listing the completed fixtures. Selecting a fixture renders a rich "Match Log / Box Score" embed containing the timeline and stats.

### D. Discord Permissions
* Modify thread creation / setup in `execute_league_match` and `auto_sim_expired_fixtures` to check and adjust permission overwrites if the bot has permission management, setting `add_reactions=True` for `@everyone`.

---

## NSS Match Engine — Highlight-Driven State Machine (v2_simulator.py)

### Architecture

The live-streaming match engine (`packages/match_engine/match_engine/v2_simulator.py`) uses a **Markov-chain state machine** with 6 discrete phases. Only `[VISIBLE]` phases yield events to the Discord handler.

```
MIDFIELD (Hidden) ──┬──▸ BUILD_UP (Hidden) ──▸ ATTACK [Visible] ──▸ SCORING_OPP [Visible]
                    │                 │                                    │
                    │                 └──▸ COUNTER_ATTACK [Visible] ──────┘
                    │
                    └──▸ SET_PIECE [Visible] ──▸ SCORING_OPP [Visible]
```

### Phase Transition Table

| Phase | Visibility | Roll Logic | Success → | Fail → |
|-------|-----------|------------|-----------|--------|
| `MIDFIELD` | Hidden | Mid vs Mid + Momentum | `BUILD_UP` (own) | `BUILD_UP` (opp) |
| `BUILD_UP` | Hidden | Passing vs Defense | `ATTACK` | `COUNTER_ATTACK` (opp) |
| `ATTACK` | Visible | Creativity vs Defense | `SCORING_OPP` | `MIDFIELD` |
| `SCORING_OPP` | Visible | Shooting vs GK | Goal→`MIDFIELD`, Save→`SET_PIECE`, Miss→`MIDFIELD` |
| `SET_PIECE` | Visible | Set piece roll | `SCORING_OPP` (corner) | `MIDFIELD` (cleared) |
| `COUNTER_ATTACK` | Visible | Speed vs Defense | `SCORING_OPP` | `MIDFIELD` |

### Probability Formula

```
chance = base_chance + (attacker_stat - defender_stat) / 100 + momentum * 0.05 + stagnation * 0.05
```

### Momentum System

* Goal: `+3` to scorer, `-2` to conceder
* Save: `+1` to defending team
* Decay: `-0.5` every 10 in-game minutes
* Capped at `±10` internally, mapped to `±100` for Discord display

### Stagnation Counter

Anti-stall mechanism: increments when a phase fails to reach `SCORING_OPP`, adds `stagnation * 0.05` to subsequent attack rolls, resets to 0 on any shot.

### Thread Safety

* Each match instantiates its own `random.Random()` — zero global random state
* `CommentaryEngine.get_commentary()` accepts an optional `rng` parameter

### Output Contract

All yielded event dicts contain: `minute`, `type`, `score_update`, `actor`, `team` (+optional `assister` on GOALs). Compatible with `IMatchOutputHandler` in `battle_cog.py`.

---

## 7. Friendly Match System (Player vs Player)

### A. Database Schema Extensions
We define two tables in `supabase/migrations/011_friendly_matches.sql`:

1. **`match_locks`**:
   - `discord_id` (BIGINT, PK) — Enforces that a player is in at most one active match at a time.
   - `lock_type` (TEXT CHECK IN ('friendly', 'league', 'bot')) — The type of match keeping the player locked.
   - `created_at` (TIMESTAMPTZ DEFAULT NOW())
2. **`friendly_match_logs`**:
   - `id` (UUID, PK) — Unique match log identifier.
   - `home_discord_id` (BIGINT REFERENCES players)
   - `away_discord_id` (BIGINT REFERENCES players)
   - `home_score` (INTEGER), `away_score` (INTEGER)
   - `box_score` (JSONB) — Full statistics breakdown.
   - `key_events` (JSONB) — Serialized chronological match events timeline.
   - `played_at` (TIMESTAMPTZ DEFAULT NOW())

### B. Command Flow & Interactions

```
Challenger: /battle friendly [Opponent]
  │
  ├─► Check Registration & match_locks for BOTH players
  │     (If locked: Return ephemeral error)
  │
  ├─► Send Ephemeral: "Challenge issued!"
  └─► Post Channel Invitation + ChallengeView (Accept / Decline)
        │
        ├──► Timeout (60s) or Decline
        │      Edit message to "timed out / declined", disable buttons
        │
        └──► Opponent clicks Accept
               ├─► Delete/Edit Invitation message
               ├─► Spawns Public Thread: "🤝 {Club1} vs {Club2} – Friendly"
               ├─► Insert locks for BOTH users in match_locks table
               ├─► Start stream_match() inside the thread
               │     (Streams events with 1-2s delay)
               ├─► Match Ends (90')
               │     ├─► Write box score/key events to friendly_match_logs
               │     ├─► Remove locks from match_locks table
               │     └─► Mention both managers in thread
               └─► Wait 120 seconds -> Archive & Lock thread
```

### C. Lock & Log Management
- Before starting, the bot runs:
  `SELECT discord_id FROM match_locks WHERE discord_id IN (challenger_id, opponent_id)`
- On Accept:
  `INSERT INTO match_locks (discord_id, lock_type) VALUES (challenger_id, 'friendly'), (opponent_id, 'friendly')`
- On Finish:
  `DELETE FROM match_locks WHERE discord_id IN (challenger_id, opponent_id)`
- Final log entry:
  `INSERT INTO friendly_match_logs (home_discord_id, away_discord_id, home_score, away_score, box_score, key_events) VALUES (...)`

---

## 20. Global LP & Divisions System Technical Plan

### A. Database Additions
- **`global_divisions` Table**:
  - `id` SERIAL PRIMARY KEY
  - `name` TEXT UNIQUE NOT NULL
  - `min_lp` INTEGER NOT NULL
  - `bot_ovr_min` INTEGER NOT NULL
  - `bot_ovr_max` INTEGER NOT NULL
  - `win_coins` INTEGER NOT NULL
- **`players` Table Modification**:
  - ADD COLUMN `global_lp` INTEGER DEFAULT 0 NOT NULL CHECK (global_lp >= 0)

### B. Logic Integration
1. **Division Lookup Flow**:
   - Query all divisions in `global_divisions` order by `min_lp` descending.
   - Match player's `global_lp` to find the highest threshold reached.
2. **Dynamic Bot Battle Math**:
   - Calibrate bot opponent rating randomly: `opp_rating = random.randint(bot_ovr_min, bot_ovr_max)`
   - Apply reward scaling atomically to `players` table:
     - **Win**: `global_lp = global_lp + 15`, `coins = coins + win_coins`, `league_points = league_points + 3`
     - **Draw**: `global_lp = global_lp + 5`, `coins = coins + (win_coins / 3)`, `league_points = league_points + 1`
     - **Loss**: `global_lp = max(0, global_lp - 10)`, `coins = coins + 15`, `league_points = league_points + 0`

---

## 21. Squad Pitch Graphic Generation Technical Plan

### A. Pitch Generator Module (`apps/discord_bot/core/pitch_generator.py`)
- **Rendering**: PIL (Pillow) image library.
- **Inputs**: `formation_name: str`, `players: list[dict | None]`.
- **Outputs**: `discord.File` containing the bytes of the PNG squad graphic.
- **Drawing Detail**:
  1. Opens the base image from `assets/pitch.png`. If it does not exist, draws a fallback green field with lines.
  2. For each slot, determines relative coordinate `(x_pct, y_pct)` from the formation configuration.
  3. Maps to absolute pixel positions.
  4. Draws a dark semi-transparent rectangle box.
  5. Computes rating color (Gold: 80+, Silver: 70-79, Bronze/White: <70).
  6. Draws OVR and Player Name using `Roboto-Bold.ttf` and `Roboto-Regular.ttf`.
  7. Serializes to `io.BytesIO` and returns `discord.File(fp=bytes_io, filename="squad_pitch.png")`.

### B. Squad Cog Integration (`apps/discord_bot/cogs/squad_cog.py`)
- Update `build_hub_embed()` to omit the text-based Starting XI list, and set the embed's image URL to `attachment://squad_pitch.png`.
- In `SquadCog.squad`, generate the pitch file and send it as the `file` argument.
- In `SquadHubView`, `SquadFormationView`, and `SquadSwapView`, whenever returning back to the Hub or confirming a formation/swap, regenerate the pitch graphic, and edit the message passing the new file in the `attachments=[new_pitch_file]` parameter to update the image component.

---

## 22. Roster Grid Graphic Generation Technical Plan

### A. Roster Grid Generator Module (`apps/discord_bot/core/pitch_generator.py`)
* Add `async def generate_roster_grid(cards: list[dict]) -> discord.File:`
* Dimensions: 605x450 pixels.
* Canvas background: Slate dark `(18, 22, 28, 255)`.
* Card Layout: 4 columns, 2 rows.
* Margins & Spacing:
  * Horizontal spacing: 15 pixels.
  * Vertical spacing: 20 pixels.
  * Left/Right margin: 20 pixels.
  * Top/Bottom margin: 25 pixels.
  * Card size: 130x190 pixels.
* Drawing logic for each card:
  1. Rounded rectangle with fill `(28, 34, 46, 255)`.
  2. Border outline (2px) matching card rarity:
     * Legendary: `(255, 215, 0, 255)` (Gold)
     * Epic: `(163, 73, 164, 255)` (Purple)
     * Rare: `(0, 162, 232, 255)` (Blue)
     * Common: `(192, 192, 192, 255)` (Silver/Gray)
  3. Draw rating + position (e.g., `85 ST`) at top centered horizontally using `Roboto-Bold.ttf`. Text color matches rarity color-coding.
  4. Draw player name centered horizontally and vertically using `Roboto-Regular.ttf` (white, truncated to 12 chars).
  5. Draw level (e.g., `Lvl 5`) and card ID (e.g., `#12`) at the bottom using `Roboto-Regular.ttf` (subtle gray colors).
* Output: Serialized via `io.BytesIO` as PNG and returned as `discord.File(fp=output, filename="roster_grid.png")`.

### B. UI & Cog Integration (`apps/discord_bot/cogs/squad_cog.py` & `squad_embeds.py`)
* **`roster_embed()`**: Remove the `add_field` calls for player details. Keep title and pagination metadata in the description, and call `embed.set_image(url="attachment://roster_grid.png")`.
* **`SquadHubView.on_full_roster`**: Before launching `SquadRosterView`, slice the first 8 cards, call `await generate_roster_grid(sliced_cards)`, and send it via `interaction.edit_original_response(embed=roster_view.get_embed(), view=roster_view, attachments=[roster_file])`.
* **`SquadRosterView.on_prev` / `on_next`**: Defer, update page, slice page cards, generate new roster grid image, and call `await interaction.edit_original_response(embed=self.get_embed(), view=self, attachments=[new_roster_file])`.

---

## 23. Pre-Launch Hardening Architecture

### A. Trust Boundary Policy
* All coin/stat/roster mutations go through Supabase RPCs with `SELECT … FOR UPDATE` on affected rows.
* Client-supplied prices (`p_sale_value`) are **never** trusted.
* `match_locks` is checked in every roster-mutation RPC and in cog middleware (`assert_not_in_match`).

### B. RPC Inventory (Post-Hardening)

| RPC | Purpose |
|-----|---------|
| `sync_training_energy` | Regen training energy (+25/hr), reset daily drill counter |
| `process_stat_drill` | Atomic stat drill with costs and OVR recalc |
| `process_agent_sale` | Server-priced sale with full lock checks |
| `recalculate_card_ovr` | Shared weighted OVR from stats + playstyles + potential |
| `swap_squad_players` | Atomic bench swap with GK slot rule |
| `set_formation_and_assignments` | Atomic formation + XI replace |
| `allocate_skill_point` | Atomic skill spend + recalc |
| `claim_evolution_reward` | Atomic evolution claim + stat cap |
| `register_new_player` | Idempotent guard on `discord_id` |

### C. UI Patterns
* **Dropdown rebuild**: `apps/discord_bot/core/select_helpers.py` — set `default=True` on selected option after every select callback.
* **View timeouts**: all hub views implement `on_timeout` disabling children.
* **Pitch assets**: `Path(__file__).resolve().parents[3] / "assets"` — no hardcoded OS paths.

### D. Migrations
* `015_hardening_schema.sql` — `league_members`, training energy columns, constraints
* `016_hardening_rpcs.sql` — RPC rewrites and new functions
* `019_match_runs.sql` — durable `match_runs` table, fixture-level active-run lock, `match_history.fixture_id` idempotency

### F. Match Restart Recovery (v1)
* **`match_runs`** row created at kickoff (one DB write): `sim_seed`, frozen `squad_snapshot`, Discord thread IDs.
* **League**: interrupted runs fast-forward via seeded `collect_match_events`; rewards applied before `is_played`; unique active run per fixture.
* **Bot / Friendly**: interrupted runs abandoned on boot; thread notice + DM; no rewards (energy not spent at kickoff).
* **Boot**: `on_ready` → `recover_interrupted_matches()` replaces blind `match_locks` wipe.
* **No mid-match checkpoints** in v1 (performance); true commentary resume deferred.

### E. Design Decisions (v1.0.0)
* AC-07 async training slots: **deprecated** in favor of AC-10 stat drills (spec note only).
* GK required in slot 1: **enforced**.
* League matches require 11 assigned players: **enforced**.
* Season-end coin payouts: **deferred** to v1.1.







