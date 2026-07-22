# ElevenBoss v1.0.0 ? Technical Plan (`plan.md`)

**Feature**: Core Game Loop ? v1.0.0 Initial Release
**Status**: Implemented (US-30+ shipped; see `change_log.md` for incremental releases)
**Depends On**: `spec.md` v1.0.0

**Related architecture**: Database scalability & command responsiveness — [`specs/038-db-scalability-performance/`](../../../specs/038-db-scalability-performance/spec.md) (US-43). Hub Wave 2 (squad / league / profile) — [`specs/039-hub-hot-path-wave2/`](../../../specs/039-hub-hot-path-wave2/spec.md) (US-44). Hub Wave 3 (marketplace / leaderboard) — [`specs/040-hub-hot-path-wave3/`](../../../specs/040-hub-hot-path-wave3/spec.md) (US-45). Phase gates: cache → hub RT cuts → idempotent UX → multi-instance job ownership; no premature Redis/sharding/`asyncpg`.

---

## 1. Repository Structure

```
ElevenBoss/
??? apps/
?   ??? discord_bot/
?       ??? __init__.py
?       ??? main.py
?       ??? cogs/
?       ?   ??? __init__.py
?       ?   ??? onboarding_cog.py    # /register command + guard check
?       ?   ??? squad_cog.py
?       ?   ??? match_cog.py
?       ?   ??? player_cog.py
?       ?   ??? profile_cog.py
?       ??? core/                    # Internal app-layer utilities (may import discord)
?       ?   ??? __init__.py
?       ?   ??? thread_manager.py    # Thread lifecycle: create, dispatch UI, cleanup
?       ??? embeds/
?       ?   ??? __init__.py
?       ?   ??? onboarding_embeds.py # Welcome, confirmation, recruitment, final embeds
?       ?   ??? gacha_embeds.py
?       ?   ??? match_embeds.py
?       ?   ??? common_embeds.py
?       ??? middleware/
?       ?   ??? guard.py             # ensure_registered() ? prompts /register (no auto-create)
?       ??? db/
?           ??? client.py
??? packages/
?   ??? match_engine/
?   ?   ??? pyproject.toml
?   ?   ??? match_engine/
?   ?       ??? __init__.py
?   ?       ??? models.py
?   ?       ??? simulator.py
?   ??? economy/
?   ?   ??? pyproject.toml
?   ?   ??? economy/
?   ?       ??? __init__.py
?   ?       ??? models.py
?   ?       ??? calculator.py
?   ??? gacha/
?   ?   ??? pyproject.toml
?   ?   ??? gacha/
?   ?       ??? __init__.py
?   ?       ??? models.py
?   ?       ??? generator.py
?   ?       ??? data/player_names.json
?   ??? leagues/
?   ?   ??? pyproject.toml
?   ?   ??? leagues/
?   ?       ??? __init__.py
?   ?       ??? models.py
?   ?       ??? calculator.py
?   ??? energy/
?       ??? pyproject.toml
?       ??? energy/
?           ??? __init__.py
?           ??? models.py
?           ??? calculator.py
??? supabase/
?   ??? migrations/
?       ??? 001_initial_schema.sql
?       ??? 002_indexes.sql
??? .specify/
?   ??? memory/constitution.md
?   ??? specs/v1.0.0/
?       ??? spec.md
?       ??? plan.md
?       ??? tasks.md
??? pyproject.toml
??? requirements.txt
??? .env
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
- **Algorithm**: mean rating -> normal distribution modifier (?15%) -> compare -> scoreline

### `economy`
- `level_up_cost(current_level: int) -> int`: `round((level ** 1.5) * 100 / 10) * 10`
- `rarity_rating_cap(rarity: str) -> int`: Common=75, Rare=84, Epic=90, Legendary=99
- No DB calls ? pure business rules only.

### `gacha`
- `generate_pack(n: int = 5) -> GachaPack`
  - Weighted rarity: Common 60%, Rare 30%, Epic 10% (Epic max; no Legendary from packs)
  - Names from bundled `data/player_names.json`
- `generate_starter_squad() -> StarterSquad` *(used exclusively by onboarding)*
  - Returns a guaranteed 11-player squad with strict positional composition:
    - **1 GK** ? Common rarity, position `GK`.
    - **4 DEF** ? Common rarity, position `DEF`.
    - **4 MID** ? Common rarity, position `MID`.
    - **2 FWD** ? Common rarity, position `FWD`.
    - **1 Marquee** ? Rare (80% chance) or Epic (20% chance) rarity. Position drawn proportionally from non-GK slots (`DEF/MID/FWD`). Replaces the Common card in that positional slot.
  - Total card breakdown: **10 Common + 1 Rare/Epic = 11 cards**.
  - Cards are ordered: `[GK, DEF?4, MID?4, FWD?2]` ? the Marquee card occupies index 0 of the returned list (surfaced as Captain), regardless of its position, for display purposes. The squad assignment maps by position, not index order.

**New Pydantic Model** (add to `packages/gacha/gacha/models.py`):
```python
class StarterSquad(BaseModel):
    marquee: GachaPlayer           # Rare or Epic ? the Captain
    youth: list[GachaPlayer]       # Exactly 10 Common players

    @property
    def all_players(self) -> list[GachaPlayer]:
        """Full 11-player list: [marquee] + youth, ordered GK?DEF?MID?FWD."""
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

- `intents = discord.Intents.default()` ? NO `MESSAGE_CONTENT` intent
- All commands via `app_commands.Group` or `@app_commands.command`
- All commands `defer(ephemeral=True)` immediately

---

## 18. Progression & Energy Rebalance (US-35)

**Design reference:** `.specify/specs/v1.0.0/rebalance_proposal.md`

**Shipped follow-up (001-fix-match-xp-energy):** Bot/league match XP restored via `apply_card_xp` SECURITY DEFINER (048/049 verify). Passive display uses `energy_regen_per_min = 0.25` (1 per 4 minutes; ~6h 40m empty?full). Friendlies remain no XP / no energy.

### A. Migration (Supabase)

- Add a new numbered migration `supabase/migrations/NNN_progression_energy_rebalance.sql` that:
  - Updates `game_config` seed defaults:
    - `energy_regen_per_min` ? `0.25` (1 per 4 minutes)
    - `match_energy_bot` ? `15`
    - `drill_basic_xp` ? `50`
    - `drill_advanced_xp` ? `120`
  - Adds new config keys:
    - `evolution_cooldown_hours` (default `6`)
    - `evolution_max_active` (default `4`)
  - Updates RPC `start_player_evolution` to read `evolution_cooldown_hours` and `evolution_max_active` from `game_config`.
  - Extends schema guard / `verify_required_schema.sql` requirements if new RPC signature/keys are required.

### B. Bot code changes

- Replace all hardcoded energy cost strings in:
  - `apps/discord_bot/cogs/battle_cog.py` (battle hub + match ticket embeds)
  - `apps/discord_bot/cogs/development_cog.py` (drill and evolution menus)
  - `apps/discord_bot/cogs/store_cog.py` (refill copy)
- Ensure drill XP previews in `/development` use the same base XP values as the RPC (`drill_basic_xp`, `drill_advanced_xp`) so UI matches results.

### C. Ops tuning validation (no Discord command)

- Operators validate rebalance values via Supabase `game_config` queries or `scratch/check_migration_046.py` ? no `/debug` slash command.

### D. Test plan

- Unit tests:
  - Extend `tests/test_economy_flows.py` and/or add a small new test file to assert:
    - downtime math for regen rates (derived minutes-to-regain X energy)
    - drill XP diminishing returns remain monotonic with level
- Manual smoke:
  - `/battle hub` shows the correct energy cost for bot matches (matches actual deduction)
  - `/development` drill preview XP matches post-drill result
  - Evolution hub cooldown text reflects config-driven cooldown


### `middleware/guard.py` ? Registration Gatekeeper

Unregistered users are blocked from executing core gameplay commands (such as `/match play`, `/store`, `/squad view`, etc.) by a middleware check:
- **`ensure_registered(interaction: discord.Interaction) -> bool`**: Implemented using discord.py's `@app_commands.check` decorator on commands/cogs.
- **Verification Logic**: Queries the `players` table using the user's `discord_id`.
- **Response**: If unregistered, intercepts the interaction and returns an ephemeral error embed directing them to run `/register`. It returns `False`, blocking execution. No database rows are created during this check.

### Squad Junction Queries & Slot Assignment

Managing the Starting 11 and squad configuration uses junction table queries against Supabase:
- **Fetching the Starting 11**: Retrieved via a joined query between `squad_assignments` and `player_cards` (specifically, `.select("position_slot, player_cards(*)")`), filtering by the user's `discord_id`.
- **Updating a Squad Slot**:
  1. **Conflict Resolution**: To avoid violating the composite `PRIMARY KEY` or `UNIQUE` constraints (e.g., if a player card is already assigned to a different slot), the command first runs a `DELETE` query on `squad_assignments` targeting the user's `discord_id` and the chosen `player_card_id`.
  2. **Assignment Update**: An `UPSERT` operation is performed on `squad_assignments` containing `discord_id`, `position_slot`, and `player_card_id` to assign the player to the new slot.


### `core/thread_manager.py` ? Thread Lifecycle Module

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
  ??? ThreadManager.create_onboarding_thread()
        ??? Thread created; WelcomeView ("Begin Setup ?" button) sent
              ??? [User clicks Begin Setup]
                    ??? ClubSetupModal presented
                          ??? [User submits Modal]
                                ??? ConfirmationView ("Confirm" / "Edit" buttons) sent
                                      ??? [Edit] ? re-present ClubSetupModal
                                      ??? [Confirm]
                                            ??? Animation loop (7 message.edit() steps)
                                                  ??? gacha.generate_starter_squad()
                                                        ??? Returns: StarterSquad
                                                        ?     .marquee  ? 1? Rare/Epic (Captain)
                                                        ?     .youth    ? 10? Common (positional guarantee)
                                                        ??? Supabase RPC register_new_player():
                                                              1. INSERT players row
                                                              2. INSERT 11 player_cards rows
                                                                 ?? collect returned UUIDs
                                                              3. INSERT squads row with formation='4-4-2'
                                                              4. INSERT 11 squad_assignments rows
                                                                 mapping to slots 1-11
                                                                   ??? Marquee Reveal embed
                                                                         (Captain stats displayed)
                                                                           ??? Twin-embed Registration Complete
                                                                                 (Captain stats + 10 youth list)
                                                                                   ??? delete_thread_after(delay=10)
```

### Error Recovery

- Any uncaught exception at any wizard step ? catch in cog ? `thread_manager.delete_thread_after(thread, 15)` with error embed.
- View `on_timeout` (60-min inactivity) ? disable all buttons; thread auto-archives via Discord.

### APScheduler Jobs
- Energy regen: `"interval", minutes=5` ? Bulk UPDATE on `players` table
- League reset: `"cron", day_of_week="mon", hour=0` ? Compute promotions, bulk UPDATE, send DMs

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
| `ThreadManager` in `apps/core/` (not `packages/`) | Needs `discord.Thread` ? Constitution forbids discord imports in packages |
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
* **Public Thread Creation:** Create a public thread on the ticket message: `await message.create_thread(name=f"??? {home_team} vs {away_team} - Live", auto_archive_duration=60)`.
* **Fallback Channel Handling:** If thread creation is unsupported (e.g. DMs, missing permissions), catch the exception, log a warning, and fall back to streaming events inside the parent channel.
* **Commentary Stream:** Send the initial kickoff message inside the thread (or channel if fallback) and run the live commentary loop:
  * Iterate through `MatchEvent` list. For each event, edit the commentary message with a 5-event live-scroll history.
  * Pause for `asyncio.sleep(1.5)` between events (`2.0` on full time).
* **Press Conference Summary:** Upon completion, send a separate "Post-Match Press Conference" embed in the thread showing stats (Possession, Shots, MOTM) and rewards.
* **Rename & Archive Cleanup:** Edit the thread name to display the final score (e.g. `?? {home_team} {score} {away_team}`). Schedule a background task (`asyncio.create_task`) that sleeps for 180 seconds and then locks and archives the thread (`await thread.edit(locked=True, archived=True)`).

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
* **`calculate_level(xp)`**: Returns the level given current XP based on the exponential curve: `floor(100 ? 1.12^(L?1))` per level step. *(v1.9: use `progression.level_from_xp` with `L_MAX` cap.)*
* **`progression.py`** *(v1.9)*: XP curve, fusion/match/drill XP formulas, skill-point math, drill catalog, level gates.
* **`roll_dynamic_potential(age, recent_ratings)`**: Calculates dynamic potential improvements for young players (age 16-21).
* **`calculate_contract_renewal_cost(ovr, config)`**: Computes coin renewal fees.

---

## 10. ElevenBoss v1.4 Architecture (Live Stadium V2 ? Dynamic Match Engine)

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
* **`TrainingSubView`, `EvolutionsSubView`, `SkillsSubView`**: Independent UI Views containing navigation buttons `[?? Back to Hub]` that use `interaction.response.edit_message` to transition seamlessly between screens without generating separate messages.
* **Timeout and security**: Explicit 15-minute timeout on all views.

### B. Cross-cog Route integration
* **`player_cog.py` / `/player-profile`**:
  * Button `[Start Evolution]` spawns the `EvolutionsSubView` directly, pre-filtered for the selected player ID.
  * Button `[Allocate Skill Points]` spawns the `SkillsSubView` directly, pre-filtered for the selected player ID. *(v1.9 ? US-23; shown only when `skill_points > 0`.)*

---

## 12. ElevenBoss v1.6 Architecture (Unified Marketplace Dashboard)

### A. Marketplace Dashboard views (`marketplace_cog.py`)
* **`MarketplaceHubView`**: The central panel presenting buttons for Sell Player, Search Market, and My Listings.
* **`SellPlayerSubView`**: In-place replacement view containing the player select dropdown, confirm button, and `[?? Back to Market]` button using `interaction.response.edit_message`.
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
  * Clicking `[ ?? Bot Battle ]` in the Hub edits the message to inform the user and programmatically launches the `run_bot_battle` simulation routine.
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
* **`AdminHubView`**: Primary options panel (`?? Announcements`, `?? Switch Server`).
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
  - `update_ticker(...)`: Edit scoreboard / **Goal Scroll** (max 10) / momentum / ticker (rolling ~5); HALF_TIME ticker line is `--- HALF TIME ---`.
  - `finalize_match(...)`: Post-match stats and rewards summary.
* **`StandardMatchHandler`**: Handles standard bot battles, spawning a unique dynamic thread and archiving it.
* **`LeagueMatchHandler`**: Handles league fixtures, directing output to the centralized Journal thread, utilizing message edits for live-scrolling commentary (rolling 5 events), and disabling views.
* **Bot/AI XIs**: `match_engine.build_bot_match_squad(target_ovr, rng)` ? 11 named cards (no ?Opponent Striker? stubs).
* **Transition floor**: `_probability_floor` locked at 5%; possession ticks also on set-piece and counter steals.

### C. Sequential Auto-Simulation
* **`auto_sim_expired_fixtures(...)`**: Scans for expired matches, resolves/creates the journal thread, and runs matches sequentially using the match engine (`run_league_match_simulation`) to avoid rate-limiting.
* **`resolve_bot_guild(...)`** (`apps/discord_bot/core/guild_resolver.py`): Cache-first guild lookup with `fetch_guild` fallback; distinguishes confirmed unreachable (NotFound/Forbidden) from transient 429/5xx.
* **`pause_season_if_guild_unreachable(...)`**: Sets `league_seasons.status = paused` for active/registration seasons when the bot cannot reach the guild; deduped logging per process boot.
* **`on_guild_remove`**: Pauses active/registration seasons for the departed guild via `pause_seasons_for_guild`.
* **`safe_defer(...)`** (`apps/discord_bot/core/view_helpers.py`): Interaction defer with 429 backoff; used by `ensure_registered` and surfaced via `@tree.error` for uncaught command failures.

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
* The main dashboard displays active season/matchday metadata: `"?? Season [N] - Matchday [X]/[Y] Active"`.
* Sub-Views:
  - **`[ ?? Standings ]`**: Displays the current league table.
  - **`[ ?? Player Stats ]`**: Renders three distinct leaderboards (Top Scorers, Top Assists, Clean Sheets) for the current active season.
  - **`[ ?? Match Center ]`**: Displays a select menu listing the completed fixtures. Selecting a fixture renders a rich "Match Log / Box Score" embed containing the timeline and stats.

### D. Discord Permissions
* Modify thread creation / setup in `execute_league_match` and `auto_sim_expired_fixtures` to check and adjust permission overwrites if the bot has permission management, setting `add_reactions=True` for `@everyone`.

---

## NSS Match Engine — Highlight-Driven State Machine (v2 + v3 dual-run)

### Live path (production)

- **Default**: NSS **v2** via `stream_match` / `collect_match_events` (`v2_simulator.py`).
- **Dual-run**: `match_runs.engine_version` pin (`nss_v2` | `nss_v3`); flags `match_engine_v3_bot|league|friendly` (default off).
- **v3**: `packages/match_engine/match_engine/v3/` — `SimulationEngine.step` / digests / DecisionInbox; Discord adapters `stream_match_v3` / `collect_match_events_v3`.
- **Settlement**: unchanged (economy / `process_match_result` / fatigue) — engine version does not fork reward pipes.
- **Dixon-Coles**: offline calibration only (`match_engine.calibration.dixon_coles_harness`) — never Discord.

See feature pack: `specs/041-match-engine-v3/`.

### Architecture (v2_simulator Markov core — still the sporting loop under v3 Phase 0)

```
MIDFIELD (Hidden) ?????? BUILD_UP (Hidden) ??? ATTACK [Visible] ??? SCORING_OPP [Visible]
                    ?                 ?                                    ?
                    ?                 ???? COUNTER_ATTACK [Visible] ???????
                    ?
                    ???? SET_PIECE [Visible] ??? SCORING_OPP [Visible]
```

### Phase Transition Table

| Phase | Visibility | Roll Logic | Success ? | Fail ? |
|-------|-----------|------------|-----------|--------|
| `MIDFIELD` | Hidden | Mid vs Mid + Momentum | `BUILD_UP` (own) | `BUILD_UP` (opp) |
| `BUILD_UP` | Hidden | Passing vs Defense | `ATTACK` | `COUNTER_ATTACK` (opp) |
| `ATTACK` | Visible | Creativity vs Defense | `SCORING_OPP` | `MIDFIELD` |
| `SCORING_OPP` | Visible | Shooting vs GK | Goal?`MIDFIELD`, Save?`SET_PIECE`, Miss?`MIDFIELD` |
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
* Capped at `?10` internally, mapped to `?100` for Discord display

### Stagnation Counter

Anti-stall mechanism: increments when a phase fails to reach `SCORING_OPP`, adds `stagnation * 0.05` to subsequent attack rolls, resets to 0 on any shot.

### Thread Safety

* Each match instantiates its own `random.Random()` ? zero global random state
* `CommentaryEngine.get_commentary()` accepts an optional `rng` parameter

### Output Contract

All yielded event dicts contain: `minute`, `type`, `score_update`, `actor`, `team` (+optional `assister` on GOALs). Compatible with `IMatchOutputHandler` in `battle_cog.py`.

---

## 7. Friendly Match System (Player vs Player)

### A. Database Schema Extensions
We define two tables in `supabase/migrations/011_friendly_matches.sql`:

1. **`match_locks`**:
   - `discord_id` (BIGINT, PK) ? Enforces that a player is in at most one active match at a time.
   - `lock_type` (TEXT CHECK IN ('friendly', 'league', 'bot')) ? The type of match keeping the player locked.
   - `created_at` (TIMESTAMPTZ DEFAULT NOW())
2. **`friendly_match_logs`**:
   - `id` (UUID, PK) ? Unique match log identifier.
   - `home_discord_id` (BIGINT REFERENCES players)
   - `away_discord_id` (BIGINT REFERENCES players)
   - `home_score` (INTEGER), `away_score` (INTEGER)
   - `box_score` (JSONB) ? Full statistics breakdown.
   - `key_events` (JSONB) ? Serialized chronological match events timeline.
   - `played_at` (TIMESTAMPTZ DEFAULT NOW())

### B. Command Flow & Interactions

```
Challenger: /battle friendly [Opponent]
  ?
  ??? Check Registration & match_locks for BOTH players
  ?     (If locked: Return ephemeral error)
  ?
  ??? Send Ephemeral: "Challenge issued!"
  ??? Post Channel Invitation + ChallengeView (Accept / Decline)
        ?
        ???? Timeout (60s) or Decline
        ?      Edit message to "timed out / declined", disable buttons
        ?
        ???? Opponent clicks Accept
               ??? Delete/Edit Invitation message
               ??? Spawns Public Thread: "?? {Club1} vs {Club2} ? Friendly"
               ??? Insert locks for BOTH users in match_locks table
               ??? Start stream_match() inside the thread
               ?     (Streams events with 1-2s delay)
               ??? Match Ends (90')
               ?     ??? Write box score/key events to friendly_match_logs
               ?     ??? Remove locks from match_locks table
               ?     ??? Mention both managers in thread
               ??? Wait 120 seconds -> Archive & Lock thread
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
* All coin/stat/roster mutations go through Supabase RPCs with `SELECT ? FOR UPDATE` on affected rows.
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
| `allocate_skill_point` | Atomic skill spend + recalc + POT cap (v1.9) |
| `apply_card_xp` | **v1.9** ? single XP pipeline; level sync + skill point grant |
| `claim_pending_level_rewards` | **v1.9** ? retroactive catch-up claim |
| `claim_evolution_reward` | Atomic evolution claim + stat cap |
| `register_new_player` | Idempotent guard on `discord_id` |

### C. UI Patterns
* **Dropdown rebuild**: `apps/discord_bot/core/select_helpers.py` ? set `default=True` on selected option after every select callback.
* **View timeouts**: all hub views implement `on_timeout` disabling children.
* **Pitch assets**: `Path(__file__).resolve().parents[3] / "assets"` ? no hardcoded OS paths.

### D. Migrations
* `015_hardening_schema.sql` ? `league_members`, training energy columns, constraints
* `016_hardening_rpcs.sql` ? RPC rewrites and new functions
* `019_match_runs.sql` ? durable `match_runs` table, fixture-level active-run lock, `match_history.fixture_id` idempotency

### F. Match Restart Recovery (v1)
* **`match_runs`** row created at kickoff (one DB write): `sim_seed`, frozen `squad_snapshot`, Discord thread IDs.
* **League**: interrupted runs fast-forward via seeded `collect_match_events`; rewards applied before `is_played`; unique active run per fixture.
* **Bot / Friendly**: interrupted runs abandoned on boot; thread notice + DM; no rewards (energy not spent at kickoff).
* **Boot**: `on_ready` ? `recover_interrupted_matches()` replaces blind `match_locks` wipe.
* **No mid-match checkpoints** in v1 (performance); true commentary resume deferred.

### G. Evolution Lifecycle (v1)
* **`active_evolutions`** extended with `status` (`active`/`completed`/`cancelled`), `matches_played`, `owner_id`, history retained on claim.
* **RPCs**: `start_player_evolution`, `cancel_player_evolution` (100 coin fee), `tick_evolution_match_progress`, `get_evolution_hub_status`; claim marks `completed` instead of delete.
* **Club pacing (v1.1+)**: max active evolutions and cold-start cooldown from `game_config` (`evolution_max_active`, `evolution_cooldown_hours` seeded **6**); replacement bypass after cancel. Migration **073** aligns `get_evolution_hub_status` with the same keys as `start_player_evolution` (removes hardcoded 10h / 10×OVR hub drift).
* **Start cost**: **25 action energy** + **`evolution_start_flat` + `evolution_start_ovr_mult` × OVR** coins (defaults 500 + 5×OVR; ledger source `evolution_start`).
* **UI**: Club Evolution Command Center in `/development` → Evolutions; progress bars on profile; Start button gated by hub `can_start`.
* **Friendly matches** now tick evolution progress via `tick_evolution_match_progress`.

### H. Evolution Club Limits Migration (023)
* **Column**: `players.last_evolution_started_at TIMESTAMPTZ` ? stamped only on cold starts.
* **`start_player_evolution`**: atomic slot cap, cooldown/replacement logic, resource deduction, ledger write.
* **`get_evolution_hub_status`**: single RPC for hub slot/cooldown/energy/cost display.

### E. Design Decisions (v1.0.0)
* AC-07 async training slots: **deprecated** in favor of AC-10 stat drills (spec note only).
* GK required in slot 1: **enforced**.
* League matches require 11 assigned players: **enforced**.
* Season-end coin payouts: **deferred** to v1.1.

---

## 24. Dynamic Player Leveling System (v1.9 ? US-23)

### A. Problem & Root Cause
* **Symptom:** Profile shows XP progress (`get_xp_progress` in `player_cog.py`) but `skill_points` never increase.
* **Cause:** `process_match_result` writes `xp` only; no RPC syncs `level` or grants skill points. `train_with_fodder` mutates a legacy `level` column independently. `process_stat_drill` grants direct `+1` stat bypassing the level system.
* **Fix:** Single atomic pipeline `apply_card_xp` ? all XP sources funnel through it.

### B. Constants (`packages/player_engine/player_engine/progression.py`)

| Constant | Value | Notes |
|----------|-------|-------|
| `L_MAX` | 100 | Hard level cap |
| `POINTS_PER_LEVEL` | 3 | Skill points per level gained |
| `LEVEL_CURVE_BASE` | 100.0 | Existing `GameConfig` |
| `LEVEL_CURVE_EXPONENT` | 1.12 | Existing `GameConfig` |
| `FUSION_DAILY_LIMIT` | 3 | Per club per UTC day |
| `FUSION_XP_BASE` | 50 | Fusion formula constant |
| `FUSION_XP_LEVEL_MULT` | 8 | ? sacrifice level |
| `FUSION_XP_OVR_MULT` | 2 | ? sacrifice overall |

**XP curve (selected milestones):**

| Level | Cumulative XP | Next level cost | Skill pts earned |
|-------|---------------|-----------------|------------------|
| 1 | 0 | 100 | 0 |
| 5 | 477 | 157 | 12 |
| 10 | 1,475 | 277 | 27 |
| 25 | 11,806 | 1,517 | 72 |
| 50 | 214,176 | 25,803 | 147 |
| 100 | 62,143,660 | ? | 297 |

### C. Pure Logic Package (`packages/player_engine/`)

**New module: `progression.py`**

| Function | Purpose |
|----------|---------|
| `xp_needed_for_level(level)` | `floor(BASE ? EXP^(L?1))` |
| `cumulative_xp_for_level(level)` | Sum of costs to reach L |
| `level_from_xp(xp, l_max=100)` | Wraps `calculate_level` with cap |
| `xp_progress(xp)` | `(level, in_level, needed)` ? move from `player_cog.py` |
| `skill_points_earned_for_level(level)` | `(level ? 1) ? POINTS_PER_LEVEL` |
| `fusion_xp_reward(sacrifice_level, sacrifice_ovr)` | Pure fusion XP |
| `match_xp_reward(minutes, rating, match_type, goals, assists, motm, result)` | Composes `training_engine.calculate_match_development_xp` + bonuses |
| `drill_xp_reward(tier, player_level)` | Base XP ? diminishing returns |

**Extend: `evolution_tracks.py`** ? add `min_player_level` per track.

**Extend: `progression_gates.py`** ? `can_allocate_skill_point(overall, potential, stat, position, stats, playstyles)` for UI preview + RPC mirror.

**New module: `drill_catalog.py`** ? tier definitions, `min_level`, `xp_base`, drill_id ? tier mapping.

**Exports:** Add to `player_engine/__init__.py` public API.

### D. Database Schema (`025_player_level_system.sql`)

```sql
-- player_cards extensions
ALTER TABLE player_cards
  ADD COLUMN IF NOT EXISTS skill_points_earned INT NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS skill_points_spent  INT NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS last_level_up_at   TIMESTAMPTZ;

-- Backfill earned from existing available balance
UPDATE player_cards SET skill_points_earned = skill_points
WHERE skill_points_earned = 0 AND skill_points > 0;

-- One-time level sync from xp
UPDATE player_cards SET level = <sql_level_from_xp(xp)>;

CREATE TABLE pending_level_rewards (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  club_id        BIGINT NOT NULL REFERENCES players(discord_id),
  player_id      UUID NOT NULL REFERENCES player_cards(id) ON DELETE CASCADE,
  missing_points INT NOT NULL CHECK (missing_points > 0),
  claimed        BOOLEAN NOT NULL DEFAULT FALSE,
  notified       BOOLEAN NOT NULL DEFAULT FALSE,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  claimed_at     TIMESTAMPTZ,
  UNIQUE (player_id)
);

CREATE TABLE fusion_daily_log (
  club_id     BIGINT NOT NULL REFERENCES players(discord_id),
  fusion_date DATE NOT NULL DEFAULT CURRENT_DATE,
  count       INT NOT NULL DEFAULT 0,
  PRIMARY KEY (club_id, fusion_date)
);
```

**Guard block:** Extend `verify_required_schema.sql` with new columns/tables.

### E. SQL Helper Functions (in migration 025)

```sql
CREATE OR REPLACE FUNCTION public.level_from_xp(p_xp INT) RETURNS INT;
CREATE OR REPLACE FUNCTION public.cumulative_xp_for_level(p_level INT) RETURNS INT;
CREATE OR REPLACE FUNCTION public.xp_needed_for_level(p_level INT) RETURNS INT;
```

Mirror Python formulas exactly (tested in `tests/test_progression.py`).

### F. Core RPC: `apply_card_xp`

```sql
CREATE OR REPLACE FUNCTION public.apply_card_xp(
  p_card_id   UUID,
  p_xp_amount INT,
  p_source    TEXT
) RETURNS JSONB;
```

**Algorithm (single transaction, `FOR UPDATE` on card):**
1. Read `xp`, `level`, `skill_points_earned`.
2. `v_old_level := level_from_xp(xp)`.
3. If `v_old_level >= L_MAX`: set `xp_wasted := p_xp_amount`, skip XP add.
4. Else: `v_new_xp := LEAST(xp + p_xp_amount, cumulative_xp_for_level(L_MAX))`.
5. `v_new_level := level_from_xp(v_new_xp)`.
6. `v_levels_gained := v_new_level - v_old_level`.
7. `v_points := v_levels_gained * POINTS_PER_LEVEL`.
8. UPDATE card: `xp`, `level`, `skill_points += v_points`, `skill_points_earned += v_points`, `last_level_up_at`.
9. INSERT `player_xp_log`.
10. RETURN JSON summary.

### G. RPC Refactors

| RPC | Change |
|-----|--------|
| `process_match_result` | Per card: compute XP in bot or SQL, call `apply_card_xp` instead of raw `xp += N` |
| `process_stat_drill` | Deduct costs; call `apply_card_xp` with drill XP; remove direct stat `+1` |
| `train_with_fodder` | Check `fusion_daily_log` cap; DELETE fodder; `apply_card_xp(target, fusion_xp, 'fusion')`; remove `level+1` / stat bump |
| `allocate_skill_point` | Add POT ceiling check; increment `skill_points_spent`; decrement `skill_points` |
| `start_player_evolution` | Reject if `card.level < track.min_player_level` |
| `claim_pending_level_rewards` | **New** ? atomic idempotent claim for `p_owner_id` |

### H. Discord Bot Integration

| File | Changes |
|------|---------|
| `player_cog.py` | Import `xp_progress` from package; rename button to "Allocate Skill Points"; level-up notification after match |
| `development_cog.py` | Drill tier UI (locked options); fusion XP preview; post-fusion level-up embed |
| `tasks/level_reward_notifier.py` | **New** ? on `on_ready`, DM clubs with unclaimed `pending_level_rewards` |
| `views/level_reward_claim.py` | **New** ? `ClaimAllLevelRewardsView` with idempotent button |

**Level-up notification flow:**
* Match/drill/fusion RPC returns `levels_gained > 0` ? ephemeral embed: "?? {name} reached Level {N}! +{pts} skill points ? [Allocate Now]".

**Retroactive DM embed:**
* Title: `?? Level-Up Rewards Available!`
* Body: per-player lines `? {name} ? Level {L} ? {missing} skill points`
* Button: `Claim All` ? `claim_pending_level_rewards` ? edit embed to success, disable button.

### I. Match XP Formula

```
base = calculate_match_development_xp(minutes, rating)   # training_engine, clamp 1?20
type_mult = {friendly: 0.8, bot: 1.0, league: 1.25}
bonuses = goals?5 + assists?3 + (15 if motm) + result_bonus
match_xp = clamp(floor(base ? type_mult) + bonuses, 1, 35)
```

### J. Drill Catalog

| drill_id | Tier | min_level | xp_base |
|----------|------|-----------|---------|
| pac_sprint, sho_finishing, pas_distribution, dri_dribble, def_tackling, phy_strength | basic | 1 | 25 |
| *(future intermediate IDs)* | intermediate | 10 | 60 |
| *(future advanced IDs)* | advanced | 25 | 120 |
| *(future elite IDs)* | elite | 50 | 200 |

*v1.9 ships with basic tier for all six existing drills; intermediate+ IDs added in follow-up or same migration if catalog expanded.*

### K. Evolution Level Gates

| track_id | min_player_level |
|----------|------------------|
| pace_boost | 5 |
| shooting_star | 10 |
| def_wall | 8 |

### L. Anti-Exploit Checklist

| Threat | Mitigation |
|--------|------------|
| XP past L100 | Clamp to `cumulative_xp_for_level(100)` |
| Double skill points | Only `apply_card_xp` grants on `levels_gained` |
| Fusion spam | `fusion_daily_log` max 3/day |
| Drill stat bypass | Remove stat mutation from `process_stat_drill` |
| Skill over POT | `allocate_skill_point` POT check |
| Double retroactive claim | `claimed` flag + `FOR UPDATE` |
| `skill_points` drift | `skill_points = skill_points_earned - skill_points_spent` invariant in allocate/claim RPCs |

### M. Implementation Phases

| Phase | Deliverable |
|-------|-------------|
| **0** | SDD docs (this section + spec US-23 + tasks) |
| **1** | `progression.py` + tests; migration 025 schema + SQL helpers + `apply_card_xp` |
| **2** | Refactor `process_match_result`, `process_stat_drill`, `train_with_fodder` |
| **3** | POT-aware `allocate_skill_point`; evolution level gates |
| **4** | UI: gating, fusion preview, profile buttons, level-up notifications |
| **5** | `pending_level_rewards` backfill + DM claim flow |
| **6** | `verify_required_schema.sql`; integration tests |

### N. Test Plan

**`tests/test_progression.py`:**
* XP curve matches existing `test_calculate_level` thresholds
* Level capped at 100; excess XP wasted
* Fusion XP monotonic in sacrifice level/OVR
* Drill diminishing returns
* `skill_points_earned_for_level(10) == 27`

**`tests/test_progression_caps.py` (extend):**
* `can_allocate_skill_point` rejects at POT

**Manual smoke:**

| # | Action | Expected |
|---|--------|----------|
| 1 | Play bot match | XP applied; level-up grants 3 skill points |
| 2 | Run basic drill | XP + soft-capped `+1` mapped attribute (036); pot/99 blocks boost only |
| 3 | Fuse bench card | Keeper gains XP; sacrifice deleted |
| 4 | Allocate skill point at POT | Rejected |
| 5 | Claim retroactive DM | Points credited once |
| 6 | 4th fusion same day | Rejected |

### O. Design Decisions (v1.9)
* Coin `/player level-up` (US-06): **deprecated** ? redirect to `/development`.
* Direct stat drills (pre-024 uncapped): **replaced** by XP drills + skill allocation; **036** restores modest soft-capped `+1` alongside XP.
* Legacy `level` column: **kept** but always synced from `xp` (no independent increments).
* Daily match XP cap: **deferred** ? curve is slow enough; revisit if grinding emerges.
* Async training slots (AC-07): remain deprecated; stat drills are instant RPC actions.

---

## 25. Progression Hardening (v1.9.1 ? US-24)

### A. Audit-Driven Fixes

| Finding | Severity | Fix (migration 027) |
|---------|----------|---------------------|
| `club_id` stale on `pending_level_rewards` | Critical | Claim by `player_cards.owner_id`; sync `club_id` |
| DM blocked ? `notified` anyway | High | Notifier: notify only on success; claim via `/development` hub |
| 297 pt veteran spike | High | Scale unclaimed: 75%, cap 18/player |
| No allocation pacing | High | 15 pts/card/day for 30 days post-deploy |
| Match XP grind | Medium | 100 match XP/card/day via `player_xp_log` sum |
| 20 drills ? one player | Medium | `player_drill_daily_log` max 5/card/day |
| allocate post-update raise | Low | Pre-check POT before stat mutation |

### B. Constants (SQL + `progression.py`)

| Constant | Value |
|----------|-------|
| `RETRO_SCALE_PCT` | 75 |
| `RETRO_MAX_PER_PLAYER` | 18 |
| `ALLOCATION_DAILY_CAP` | 15 |
| `ALLOCATION_PACING_UNTIL` | deploy date + 30 days (UTC) |
| `MATCH_XP_DAILY_CAP` | 100 |
| `DRILL_PER_PLAYER_DAILY_CAP` | 5 |

### C. Schema Additions (`027_progression_hardening.sql`)

```sql
ALTER TABLE player_cards
  ADD COLUMN daily_alloc_count INT NOT NULL DEFAULT 0,
  ADD COLUMN alloc_reset_date DATE;

CREATE TABLE player_drill_daily_log (
  card_id    UUID NOT NULL REFERENCES player_cards(id) ON DELETE CASCADE,
  drill_date DATE NOT NULL DEFAULT CURRENT_DATE,
  count      INT NOT NULL DEFAULT 0,
  PRIMARY KEY (card_id, drill_date)
);
```

**One-time data fix:**
```sql
UPDATE pending_level_rewards pr
SET club_id = c.owner_id,
    missing_points = LEAST(18, GREATEST(1, (missing_points * 75) / 100))
FROM player_cards c
WHERE c.id = pr.player_id AND NOT pr.claimed;
```

### D. RPC Changes

* **`claim_pending_level_rewards`:** Join `player_cards`; credit when `owner_id = p_owner_id`; update `club_id`.
* **`allocate_skill_point`:** Reset/increment `daily_alloc_count`; enforce pacing window; pre-check POT; then mutate.
* **`apply_card_xp`:** If `p_source = 'match_simulation'`, clamp `p_xp_amount` to remaining daily match allowance.
* **`process_stat_drill`:** Upsert `player_drill_daily_log`; reject if count > 5.
* **`count_unclaimed_level_rewards(p_owner_id)`:** Helper for bot UI.

### E. Bot Changes

* **`player_cog.py`:** *(no claim slash command ? use development hub fallback).*
* **`development_cog.py`:** `DevelopmentHubView` shows **Claim Level Rewards** when pending count > 0.
* **`level_reward_notifier.py`:** Group by `player_cards.owner_id`; do not mark notified on DM failure.
* **`level_reward_claim.py`:** Pending check via `count_unclaimed_level_rewards` RPC.

### F. Test Plan

* `tests/test_progression_hardening.py` ? retro scale formula, cap constants exported.
* Manual: claim after ownership sync; 16th allocation in pacing window rejected; 6th drill on same card rejected.

### G. Implementation Phases

| Phase | Deliverable |
|-------|-------------|
| 0 | SDD US-24 + this section + tasks T20 |
| 1 | Migration 027 + verify script |
| 2 | Package constants + tests |
| 3 | Bot development hub claim + notifier fix |

---

## 26. Economy v2 Foundation (US-25)

### A. Schema (`028_economy_foundation.sql`)

| Object | Purpose |
|--------|---------|
| `game_config` | Hot-reloadable economy tunables (`key` ? `value_json`) |
| `players.action_energy` | Unified action pool (max 100) |
| `players.action_energy_updated_at` | Lazy regen timestamp |
| `players.last_daily_login` | UTC date of last login claim |
| `players.login_streak` | Consecutive login days |
| `economy_ledger.idempotency_key` | UNIQUE ? replay-safe mutations |
| `economy_ledger.reason_meta` | JSONB audit context |
| `agent_sale_daily_log` | Per-club daily agent sale counter |
| `energy_refill_daily_log` | Per-club daily refill counter (max 3) |

**Seed `game_config` keys:** `economy_v2_enabled`, `match_bot_win`, `match_bot_draw`, `match_bot_loss`, `match_friendly_win`, `match_league_win_min`, `match_league_win_max`, `daily_login_base`, `daily_login_streak_bonus`, `daily_login_streak_cap`, `agent_sale_daily_cap`, `drill_basic_flat`, `drill_basic_ovr_mult`, `drill_basic_energy`, `drill_basic_xp`, `drill_advanced_flat`, `drill_advanced_ovr_mult`, `drill_advanced_energy`, `drill_advanced_xp`, `evolution_start_flat`, `evolution_start_ovr_mult`, `evolution_start_energy`, `fusion_coins`, `energy_regen_per_min`, `energy_max`, `energy_refill_amount`, `energy_refill_costs` (JSON array), `match_energy_bot`, `match_energy_friendly`, `match_energy_league`.

### B. Core RPCs

| RPC | Signature | Role |
|-----|-----------|------|
| `get_game_config` | `(TEXT) ? JSONB` | Read config with default fallback |
| `sync_action_energy` | `(BIGINT) ? JSONB` | Lazy regen; returns current/max |
| `apply_club_economy` | `(BIGINT, BIGINT, INT, TEXT, TEXT, JSONB) ? JSONB` | Single coin+energy write path + ledger |
| `claim_daily_login` | `(BIGINT) ? JSONB` | Daily coin faucet with streak |
| `purchase_energy_refill` | `(BIGINT) ? JSONB` | Escalating coin sink for +50 energy |

**Refactored RPCs:** `process_stat_drill`, `start_player_evolution`, `train_with_fodder`, `process_agent_sale` ? call `sync_action_energy` + `apply_club_economy` or read `get_game_config`.

### C. Package Layer

| File | Role |
|------|------|
| `packages/economy/economy/flows.py` | Pure `drill_cost`, `match_reward`, `daily_budget` for tests/sim |
| `packages/economy/economy/config.py` | Extend `GameConfig` with v2 defaults mirroring seed rows |
| `tests/test_economy_flows.py` | Archetype budget assertions |
| `scripts/simulate_economy.py` | 30-day supply simulation |

### D. Bot Integration

| File | Changes |
|------|---------|
| `apps/discord_bot/core/economy_rpc.py` | Helpers: `apply_match_economy`, `sync_action_energy`, `format_energy_status` |
| `battle_cog.py` | Replace direct `players.update` coin/energy with `apply_club_economy`; idempotency = `match_run_id` |
| `development_cog.py` | Action energy display; drill cost from package |
| `profile_cog.py` | Unified energy + gems label |
| `economy_cog.py` | Remove misleading wage warning; show gems |
| `store_cog.py` | `/store` hub ? daily login + energy refill |
| `main.py` | Load `store_cog` |

### E. Match Reward Formulas (v2)

```
bot_win   = floor(match_bot_win ? division.win_coins / 100)
bot_draw  = match_bot_draw
bot_loss  = match_bot_loss
league    = lerp(match_league_win_min, match_league_win_max, division_tier_index / 5)
friendly  = match_friendly_win if win else 0
```

### F. Migration Rollout

1. Apply `028` + extend `verify_required_schema.sql`
2. Deploy bot with v2 RPC wiring (`economy_v2_enabled = true` in seed)
3. Monitor via `economy_ledger` SQL or `scripts/simulate_economy.py` for 7 days
4. Optional: `scripts/soft_rebalance_coins.py` if p95 > 250k (not auto-run)

### G. Implementation Phases

| Phase | Deliverable |
|-------|-------------|
| 0 | SDD US-25 + tasks |
| 1 | Migration 028 + verify |
| 2 | `flows.py` + tests + simulate script |
| 3 | `battle_cog` + sink RPC refactors |
| 4 | UI + `store_cog` + rollout flag |

---

## 25. League Economy Hardening (US-27)

**Audit source:** [`.specify/specs/v1.0.0/league-economy-calibration.md`](league-economy-calibration.md)  
**Depends on:** US-26 (migration 032), US-25 (`apply_club_economy` pipe)

### A. Problem Statement

| ID | Gap | Severity |
|----|-----|----------|
| E1 | Auto-sim grants full match coins with 0 energy | High |
| E2 | `entry_fee_coins` in `config_json` never charged | High |
| E3 | Triple faucet (match + prize + milestone) untuned | Medium |
| E4 | No join eligibility (alt/smurf) | Medium |

Champion injection today: **~7,150 coins/season** (Grassroots). Target after US-27: **~3,900 net** (manual champion).

### B. Schema & RPC (`033_league_economy_calibration.sql`)

**`game_config` seed / UPDATE defaults:**

```sql
INSERT INTO game_config (key, value_json) VALUES
  ('league_entry_fee_coins', '1500'),
  ('league_entry_fee_per_division', '250'),
  ('league_auto_sim_coin_mult', '0.5'),
  ('league_join_min_matches', '10'),
  ('league_join_min_account_days', '7')
ON CONFLICT (key) DO UPDATE SET value_json = EXCLUDED.value_json;

-- Retune existing keys (see AC-27d)
UPDATE game_config SET value_json = '3500' WHERE key = 'league_season_prize_pool_base';
-- ... participation, milestone, match_league_win_min/max
```

**New RPC: `charge_league_entry_fees(p_season_id UUID) ? JSONB`**

- Reads `league_seasons.config_json.entry_fee_coins` OR global `league_entry_fee_coins`.
- Per human in `league_participants`: `fee = base + tier ? per_division` from `players.division`.
- Calls `apply_club_economy(-fee, 0, 'league_entry', idempotency_key, meta)`.
- Returns `{charged: [...], skipped: [{player_id, reason}]}`.
- **Called from bot** after bulk `league_participants` insert (or inline in single RPC if we refactor season start).

**Extend `distribute_season_prizes`:**

- After prize loop, refund active humans: `apply_club_economy(+fee, 0, 'league_entry_refund', ...)`.
- Store original fee in `league_participants` or derive from ledger `league_entry` row.

**Optional column (preferred over ledger lookup):**

```sql
ALTER TABLE league_participants
  ADD COLUMN IF NOT EXISTS entry_fee_paid INTEGER NOT NULL DEFAULT 0;
```

Enables refund without scanning ledger. Guard in migration + `verify_required_schema.sql`.

### C. Pure Logic (`packages/economy/economy/flows.py`)

```python
def league_entry_fee(division: str, cfg: EconomyConfig) -> int:
    tier = league_division_tier(division)
    return cfg.league_entry_fee_coins + tier * cfg.league_entry_fee_per_division

def league_match_coins_adjusted(
    result: str, division: str, *, auto_sim: bool, cfg: EconomyConfig
) -> int:
    base = league_match_coins_for_result(result, division, cfg)  # extract draw/loss
    if auto_sim:
        return int(base * cfg.league_auto_sim_coin_mult)
    return base
```

Extend `EconomyConfig` + `DEFAULTS` with new keys. Update `scripts/simulate_league_economy.py` scenarios (manual vs auto-sim, entry fee net).

### D. Bot Integration

| File | Change |
|------|--------|
| `league_rewards.py` | `coin_mult` param when `deduct_energy=False`; read `league_auto_sim_coin_mult` from `get_game_config` |
| `league_cog.py` | Join gate in `player_register_league`; hub embed shows fee + requirements |
| `admin_cog.py` | After season start participant insert ? `charge_league_entry_fees`; surface skipped list in embed |
| `economy_rpc.py` | Helper `charge_league_entry` / `refund_league_entry` wrappers (thin) |

**Auto-sim path:** `run_league_match_simulation(..., active_player_id=None)` already sets `deduct_energy=False` ? pass `auto_sim=True` into `apply_league_human_rewards`.

**Registration vs season start:** Fee charged at **season start** (participant lock-in), not `league_members` roster signup ? avoids charging players who never get a season.

### E. Tests

| File | Coverage |
|------|----------|
| `tests/test_economy_flows.py` | `league_entry_fee`, `league_match_coins_adjusted` pure math |
| `tests/test_league_economy.py` (new) | Entry fee idempotency, auto-sim mult, champion net ? target |
| `scripts/simulate_league_economy.py` | Post-calibration table + manual vs auto-sim columns |

### F. Rollout Phases

| Phase | Deliverable | Exit criteria |
|-------|-------------|---------------|
| **0** | SDD US-27 + tasks (this section) | spec/plan/tasks aligned |
| **1** | Migration `033` + verify schema | `verify_required_schema.sql` passes |
| **2** | `flows.py` + simulate script + unit tests | `pytest tests/test_economy_flows.py tests/test_league_economy.py` green |
| **3** | RPC entry charge + refund in `distribute_season_prizes` | Scratch apply + manual RPC smoke |
| **4** | Bot wiring (rewards mult, gates, hub/admin copy) | Manual: register gate, start season debit, auto-sim half coins |
| **5** | `change_log.md` player-facing notes | Ship |

### G. Monitoring (ops ? no code)

Weekly ledger queries per calibration doc ?7. Yellow/red triggers ? edit `game_config` only.

### H. Out of Scope (US-27)

- OVR cap enforcement at match start (separate hardening ticket)
- Gems / card prizes / season XP lump sum
- Promotion-relegation prize pools
- `league_energy` separate bar

---

## 26. League Season Announcement & Dual Threads (US-28)

**Depends on:** US-26 (league mode), migration `034_league_season_threads.sql`

### A. Schema (`league_seasons` columns)

| Column | Type | Purpose |
|--------|------|---------|
| `announcement_message_id` | BIGINT NULL | Kickoff message in league channel |
| `journal_thread_id` | BIGINT NULL | Official standings thread |
| `matchday_thread_id` | BIGINT NULL | Live commentary thread |
| `journal_standings_message_id` | BIGINT NULL | Edited standings embed |
| `thread_format` | TEXT DEFAULT `'legacy'` | `'dual_v2'` for new seasons |

### B. Modules

| File | Role |
|------|------|
| `apps/discord_bot/core/league_announcement.py` | Banner embed + `background.png` file |
| `apps/discord_bot/core/league_journal.py` | `create_season_threads`, `resolve_season_threads`, `archive_season_threads`, journal posts |
| `apps/discord_bot/cogs/admin_cog.py` | Season start announcement + thread bootstrap; season end archive |
| `apps/discord_bot/cogs/battle_cog.py` | `LeagueMatchHandler` dual-thread routing |
| `apps/discord_bot/cogs/league_cog.py` | `send_league_announcement` files + return message |

### C. Thread creation

One thread per anchor message (Discord limit). Flow: announcement ? anchor ? Journal thread; anchor ? MatchDay thread; both `locked=True`, `auto_archive_duration=10080`.

### D. Legacy

`thread_format='legacy'` seasons use `guild_config.league_updates_thread_id` until complete.

---

## 27. Match Loop Hardening & Dead Code Removal (US-29)

**Audit source:** Jul 2026 codebase audit (bot/friendly regressions vs US-23/US-25, RPC schema drift, scheduler/UX gaps).  
**Depends on:** US-23, US-25, US-26 (`league-mode-design.md`), US-28 (migration 034 applied).

### A. Problem Statement

| ID | Gap | Severity | Root cause |
|----|-----|----------|------------|
| H1 | Bot matches bypass `apply_club_economy` | **P0** | `battle_cog.execute_bot_battle` never migrated when league path was wired in US-26 |
| H2 | Bot matches use flat `p_xp_amount: 15` | **P0** | Same ? `build_process_match_result_rpc` only called from `league_rewards.py` |
| H3 | Friendly matches skip match XP | **P1** | Only `tick_evolution_match_progress` called; no `process_match_result` |
| H4 | `process_match_result` SELECTs `initial_potential`, `recent_match_ratings` | **P0** | RPC updated in 021/025/026; columns never added in migrations |
| H5 | Store gacha non-atomic | **P1** | `store_cog` UPDATE then INSERT without RPC |
| H6 | `/battle bot`, `/battle friendly` missing defer | **P0** | Slash handlers skip defer; hub button path defers |
| H7 | Matchday reminder spam | **P1** | Hourly job, no sent-flag |
| H8 | Debug `debug-*.log` in cogs | **P1** | Leftover agent instrumentation |
| H9 | Legacy economy fallback code | **P2** | `league_rewards.py` v2=false branch; inline bot coin math |
| H10 | Dead `energy_regen_job` | **P2** | `regen_energy_tick` no-op since migration 028 |
| H11 | `verify_required_schema.sql` incomplete | **P1** | Missing `process_match_result`, 034 columns, `recent_match_ratings` |
| H12 | `test_training.py` broken import | **P2** | Imports removed `training` module at repo root |

**Intentional (not bugs):** Weekly `league_points` reset + `players.division` promotions (bot ladder only). Guild seasons use `league_fixtures` ? see `league-mode-design.md`. **Real confusion:** bot matches also write `global_lp` (Bronze/Silver ladder) alongside `league_points` (Grassroots ladder); profile copy must distinguish them.

### B. Target Architecture

```
???????????????????????????????????????????????????????????????????
?                     Match conclusion (all types)                 ?
?????????????????????????????????????????????????????????????????
? Match type  ? Economy pipe         ? XP pipe                    ?
?????????????????????????????????????????????????????????????????
? bot         ? apply_match_economy    ? build_process_match_result ?
?             ? idempotency=run_id   ? match_type='bot'           ?
? friendly    ? (none ? sandbox)       ? (none ? sandbox)           ?
?             ? friendly_match_logs    ? no economy/XP/stats        ?
? league      ? league_rewards.py ?    ? league_rewards.py ?        ?
?????????????????????????????????????????????????????????????????
                              ?
                              ?
              RPC process_match_result(p_xp_amounts, p_card_ratings)
                              ?
                              ?
                    apply_card_xp (per card, daily cap)
```

**Refactor strategy:** `apply_bot_match_rewards()` lives in `apps/discord_bot/core/match_rewards.py` (parallel to `league_rewards.py`). **Jul 2026 update:** friendly matches reverted to US-18 sandbox ? no `apply_friendly_human_rewards`; post-match writes `friendly_match_logs` only.

### C. Schema & RPC (`035_match_result_schema_fix.sql`)

```sql
-- 1. Missing column for rating history (potential boost logic in RPC)
ALTER TABLE public.player_cards
  ADD COLUMN IF NOT EXISTS recent_match_ratings JSONB NOT NULL DEFAULT '[]'::jsonb;

-- 2. Fix process_match_result: use base_potential instead of initial_potential
--    DROP old overloads first; recreate body with:
--      SELECT age, potential, base_potential, recent_match_ratings ...
--      v_init_pot := COALESCE(v_init_pot, v_pot);  -- v_init_pot from base_potential

-- 3. Atomic daily pack
CREATE OR REPLACE FUNCTION public.claim_daily_pack(p_club_id BIGINT) RETURNS JSONB ...

-- 4. Matchday reminder dedup
CREATE TABLE IF NOT EXISTS public.league_matchday_reminders (
    season_id UUID NOT NULL REFERENCES league_seasons(id) ON DELETE CASCADE,
    matchday INTEGER NOT NULL,
    player_id BIGINT NOT NULL REFERENCES players(discord_id) ON DELETE CASCADE,
    reminded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (season_id, matchday, player_id)
);
-- RLS: SELECT/INSERT for anon, authenticated, service_role (same pattern as 030)
```

Extend `verify_required_schema.sql`:

| Entry | Reason |
|-------|--------|
| `column:player_cards.recent_match_ratings` | RPC dependency |
| `column:league_seasons.announcement_message_id` | US-28 bot dependency |
| `function:process_match_result` | All match XP |
| `function:claim_daily_pack` | Store atomic claim |
| `table:league_matchday_reminders` | Reminder dedup |
| RLS policies for `league_matchday_reminders` | Data API access |

### D. Bot Integration

| File | Change |
|------|--------|
| `apps/discord_bot/core/match_rewards.py` | `apply_bot_match_rewards()` only (friendly sandbox ? no payout helper) |
| `apps/discord_bot/cogs/battle_cog.py` | Bot path: defer at command entry; call `match_rewards`; remove direct `players.update` coins/energy; remove flat XP; remove debug log block |
| `apps/discord_bot/cogs/battle_cog.py` | Friendly path: defer; **no** economy/XP/stats; `friendly_match_logs` + `complete_run` only |
| `apps/discord_bot/cogs/store_cog.py` | Replace UPDATE+INSERT with `claim_daily_pack` RPC |
| `apps/discord_bot/cogs/onboarding_cog.py` | Defer before DB on `/register` new-user path |
| `apps/discord_bot/cogs/league_cog.py` | Remove debug log; add `@app_commands.check(ensure_registered)` on hub |
| `apps/discord_bot/core/league_journal.py` | Remove `_DEBUG_LOG` |
| `apps/discord_bot/cogs/development_cog.py`, `squad_cog.py` | Remove debug log helpers |
| `apps/discord_bot/core/league_rewards.py` | Delete `economy_v2_enabled == false` coin/energy fallback |
| `apps/discord_bot/core/scheduler_jobs.py` | Reminder dedup insert; remove or repurpose `energy_regen_job` |
| `apps/discord_bot/main.py` | Drop `energy_regen_job` schedule if removed |
| `README.md` | `/store` for gacha; remove `gacha_cog` |
| `change_log.md` | Bot energy 20?, per-card XP, friendly XP |

### E. Bot Match Reward Flow (reference implementation)

```python
# match_rewards.py ? pseudocode
async def apply_bot_match_rewards(db, *, player_row, cards, result_str, ...):
    v2 = await economy_v2_enabled(db)
    await sync_action_energy(db, player_id)
    coins = compute_bot_match_coins(result_str, division_win_coins, v2=v2)
    energy = match_energy_cost("bot", v2=v2)
    await apply_match_economy(db, player_id, coins, energy, "bot", run_id, result_str)
    # Weekly ladder stats only (NOT guild season):
    await db.table("players").update({
        "league_points": ..., "global_lp": ..., "goal_difference": ...,
        "matches_played": ..., "wins": ..., "draws": ..., "losses": ...,
    }).eq("discord_id", player_id).execute()
    await db.table("match_history").insert({...}).execute()
    xp_payload = build_process_match_result_rpc(cards, match_type="bot", ...)
    await db.rpc("process_match_result", xp_payload).execute()
```

**Energy/coins** go through RPC; **ladder stat columns** remain direct UPDATE (display/ladder only, not economy pipe ? same pattern as `league_rewards` career W/D/L).

### F. Dead Code Removal Checklist

| Remove | Location | Replacement |
|--------|----------|-------------|
| `debug-74c668.log` writes | `battle_cog`, `league_cog`, `league_journal` | None |
| `debug-4aa967.log` writes | `development_cog`, `squad_cog` | None |
| `p_xp_amount: 15` | `battle_cog` | `build_process_match_result_rpc` |
| Direct coin/energy UPDATE | `battle_cog` bot path | `apply_match_economy` |
| `tick_evolution_match_progress` alone | friendly path | inside `process_match_result` |
| v2=false economy fallback | `league_rewards.py` | assume v2 always on |
| `energy_regen_job` + no-op RPC call | `scheduler_jobs`, `main.py` | lazy `sync_action_energy` only |
| "Ranked (Soon)" disabled button | `battle_cog` ArenaHubView | delete until feature exists |
| `gacha_cog` README entry | `README.md` | `store_cog` |

**Keep (not dead):** `weekly_league_reset_job` (bot Division Rank ladder), `global_lp` / `global_divisions` (separate cosmetic progression track), `league-mode-design.md` dual-system model.

### G. Tests

| File | Coverage |
|------|----------|
| `tests/test_match_loop_hardening.py` (new) | `build_process_match_result_rpc` for bot/friendly types; bot coin helper with v2 |
| `tests/test_match_xp.py` | Extend if needed for match_type multipliers |
| `tests/test_economy_flows.py` | Bot energy cost 20, friendly winner coins |
| `tests/test_training.py` | Fix import: `from training.training.engine import ...` or delete if redundant |
| `tests/test_league_announcement.py` | Unchanged |

### H. Rollout Phases

| Phase | Deliverable | Exit criteria |
|-------|-------------|---------------|
| **0** | SDD US-29 (this section + spec + tasks) | Docs approved before code |
| **1** | Migration `035` + verify schema | `verify_required_schema.sql` passes on fresh DB |
| **2** | `match_rewards.py` + `process_match_result` fix in migration | Unit tests green |
| **3** | `battle_cog` bot + friendly wiring + defer fixes | Grep: no flat XP 15, no coin UPDATE in bot path |
| **4** | `store_cog` RPC + reminder dedup + debug removal | Manual smoke: pack claim, one matchday DM |
| **5** | Dead code purge + README + `change_log.md` | Full `pytest tests/` (incl. fixed training test) |

### I. Manual Smoke (post-deploy)

| # | Action | Expected |
|---|--------|----------|
| 1 | `/battle bot` via slash (not just hub button) | Responds within 3s; deducts 20?; coins in ledger |
| 2 | Play bot match to completion | Per-card XP varies; no flat 15 in logs |
| 3 | `/battle friendly` challenge + play | Free ? no energy; no coins/XP/stats; result in `friendly_match_logs` |
| 4 | `/store` claim pack | 5 cards; double-click does not burn cooldown on failure |
| 5 | League matchday within 6h | One DM per manager per matchday |
| 6 | Monday 00:00 UTC (or admin trigger) | `league_points` reset; `global_lp` unchanged |
| 7 | `pytest tests/ -q` | All pass including `test_training` |

### J. Out of Scope (US-29)

- Per-card `match_rating` from live stats (team average remains ? ponytail ceiling documented in `match_xp.py`)
- Merging `global_lp` and `players.division` into one ladder
- Pydantic v2 `ConfigDict` migration (separate hygiene ticket)
- Ranked PvP mode implementation

---

## 28. League Points Integration & `/leaderboard` (US-30)

### Implementation summary

| Layer | Deliverable |
|-------|-------------|
| `packages/leagues` | `match_points.py`, `weekly_tiers.py`, `leaderboard_format.py` |
| Migration `039` | `weekly_rank_rewards`, `best_weekly_*` columns, `claim_weekly_rank_tier` RPC |
| `leaderboard_cog.py` | `/leaderboard` ? Division / Global LP / Season tabs |
| `competitive_display.py` | Post-match reward formatters |
| `battle_cog.py` | LP display fix, league coin fix, consolidated imports |
| `scheduler_jobs.py` | Rank snapshot DMs before weekly reset |
| `league_cog.py` | Auto `distribute_season_prizes` on natural season complete |

See `spec.md` US-30 for acceptance criteria.

---

## 28. League Points Integration & `/leaderboard` (US-30)

**Packages:** `match_points.py`, `weekly_tiers.py`, `leaderboard_format.py` in `packages/leagues/`.

**Migration 039:** `weekly_rank_rewards`, `players.best_weekly_pts` / `best_weekly_rank`, `game_config` tier keys, RPC `claim_weekly_rank_tier`.

**Apps:** `leaderboard_cog.py` (3-tab ephemeral hub), `competitive_display.py`, `view_helpers.edit_ephemeral_hub_message`, battle_cog display fixes, profile `/leaderboard` link, scheduler weekly snapshot DMs, auto `distribute_season_prizes` on natural season end.

---

## 29. Player Age & Lifecycle (US-31 ? Phase A)

### Architecture

| Concern | Source of truth |
|---------|-----------------|
| Live age | `player_cards.date_of_birth` ? `card_age_from_dob()` / `effective_card_age()` |
| Cached age | `player_cards.age` refreshed weekly + on match RPC |
| XP multipliers | `packages/player_engine/age_manager.py` + `game_config` `age_xp_mult_*` keys |
| Decline / retirement | RPC `process_season_aging` (Monday 00:00 UTC, before league reset); curve PAC/PHY≥31 (−2 at ≥35), PAS/DEF/DRI≥33, SHO≥35; `retire_player_card` auto-promotes same-role reserve or sets `players.squad_invalid` (cleared on promote→11 or `/squad` save) |

### Migration 041 (+ 053 retirement lifecycle fixes)

- Columns: `date_of_birth`, `is_retired`, `retirement_notified_at`, `retired_at`; **053** adds `players.squad_invalid`
- RPCs: `card_age_from_dob`, `card_xp_age_multiplier`, `retire_player_card`, `process_season_aging` (053 replaces aging/retire/set_formation bodies)
- Updated: `register_new_player`, `claim_daily_pack`, `renew_contract` (block 35+), `process_match_result`, `process_stat_drill` (age XP), `compute_agent_offer` + `process_agent_sale` (age/potential)

### Packages

| Module | Role |
|--------|------|
| `age_manager.py` | Lifecycle phases, XP multipliers, decline rules, contract gate |
| `player_factory.py` | Unified `create_player_card()` ? `CreatedPlayerCard` with DOB, archetype `role`, deterministic True OVR balance |
| `archetypes.py` | Positional archetype catalog + `roll_archetype` (migration 051 persists `role`) |
| `progression.py` | Optional `age` on `match_xp_reward` / `drill_xp_reward` |
| `gacha/pack_configs.py` | Named pack mixes (`standard` 60/30/8/2); no live secondary SKUs in v1 |

### Bot wiring

| File | Change |
|------|--------|
| `card_payload.py` | `card_rpc_payload()`, `effective_card_age()` |
| `match_xp.py` | Age-aware match XP payload |
| `development_cog.py` | Age-aware drill XP preview |
| `player_cog.py` | Lifecycle display + retirement warning |
| `marketplace_cog.py` | Age-aware offers, filter `is_retired` |
| `scheduler_jobs.py` + `main.py` | `season_aging_job` cron Monday 00:00 UTC |

### Deferred (Phase B/C)

- **Phase B:** flat youth intake at academy L1 ? **shipped in migration 042**
- **Phase C:** Youth Academy + Training Ground under `/store` (migration 043)

See `spec.md` US-31 / US-32 for acceptance criteria.

---

## 30. Youth Academy Intake (US-32 — Phase B + 015 holding)

### Migration 042 (baseline)

- Table `youth_intake_log (owner_id, intake_week)` — idempotency + notification tracking
- RPC `process_youth_intake(p_owner_id, p_cards JSONB)` — insert cards, no squad slots
- RPC `current_intake_week()` — Monday UTC week key
- `game_config`: `youth_intake_count` (3), `youth_intake_academy_level` (1)

### Migration 060 (holding phase)

- `player_cards.in_academy`, `academy_progress`, `academy_seated_at`
- `process_youth_intake` seats into free academy slots; partial-seat + skip when full
- Daily `process_daily_academy_growth` + age-out promote/release
- Promote / release RPCs; senior soft cap via `senior_roster_cap`
- Hybrid scouting: `dispatch_youth_scout` / `finalize_youth_scout_report` / `sign_youth_scout_prospect`
- Primary UI: `/profile` → **Manage Academy** (see `specs/015-youth-academy/`)

### Packages

| Module | Role |
|--------|------|
| `youth_intake.py` / `gacha` | Intake generation scaled by YA level |
| `player_engine/youth_math.py` | Academy daily points / ready / age-out |
| `economy/facility_effects.py` | Slot caps + scout cost/hours |

### Bot wiring

| File | Role |
|------|------|
| `youth_intake_notifier.py` | Batch humans, seating RPC, DM embed |
| `academy_hub.py` / `academy_embeds.py` | Manage Academy hub |
| `academy_growth_job.py` | Daily growth + age-out / scout-ready DMs |
| `scheduler_jobs.py` | `youth_intake_job` + `academy_growth_job` |

---

## 31. Club Facilities (US-33 — Phase C + Manage Academy)

### Migration 043

- Columns on `players`: `youth_academy_level`, `training_ground_level`, `facility_last_upgrade_at`
- RPC `upgrade_club_facility(p_owner_id, p_facility_key, p_expected_cost)`
- RPC `training_ground_xp_bonus(p_level)` ? flat +0?+4 drill XP
- Updated `process_stat_drill` ? age multiplier + training ground bonus

### Packages

| Module | Role |
|--------|------|
| `economy/facility_effects.py` | Costs, TG bonus, academy tier table |

### Bot wiring

| File | Role |
|------|------|
| `views/store_facilities.py` | Facilities sub-hub under `/store` |
| `development_cog.py` | TG level in drill XP preview |
| `youth_intake_notifier.py` | Reads `youth_academy_level` for intake |
| `economy_cog.py` | Read-only facility levels on `/club-finances` |

---

## 32. Scouting Pool / Regen Market (US-34 ? Phase D)

### Migration 044

- Table `scouting_pool_players` ? unclaimed regen listings with `list_price`, `source_card_id`
- RPCs: `insert_scouting_pool_player`, `purchase_scouting_player`
- `game_config`: `regen_ovr_threshold` (75), `scouting_pool_max_active` (50)

### Packages

| Module | Role |
|--------|------|
| `regen_pool.py` | `generate_regen_from_retired()` + `regen_rarity_for_ovr()` (≥85 Epic/Rare 50/50; 80–84 Rare/Common 60/40; 75–79 Common/Rare 80/20) |
| `scouting_market.py` | `scouting_purchase_price()` (~1.4? agent offer) |

### Bot wiring

| File | Role |
|------|------|
| `regen_pool_job.py` | Post-aging spawn from recently retired 75+ OVR |
| `marketplace_cog.py` | Search Market UI + purchase flow |
| `scheduler_jobs.py` | `regen_pool_job` Monday 00:00 UTC |

**Terminology:** Division Rank (`league_points`), Global LP (`global_lp`), Season Pts (fixtures) ? never "league pts" without qualifier.

## 23. Energy Cost Visibility (US-36)

### A. UI Standardization Updates
- **Embed Footers:** Update the rror_embed, success_embed, and specific hub embeds (ArenaHubView, DevelopmentHubView, Match Ticket) in pps/discord_bot/embeds/common_embeds.py (or directly within the cogs) to append ? Energy cost applies to the mbed.set_footer() text when rendering an actionable view that requires energy.
- **Button Labels:** 
  - In attle_cog.py (ArenaHubView): Update the Bot Battle button label to include ?.
  - In development_cog.py (TrainingSubView, EvolutionsSubView): Ensure the Start Drill and Start Evolution buttons clearly feature the ? emoji.
  
### B. Backend Synchronization
- Ensure that the text components in development_cog.py and attle_cog.py continue to query get_game_config_int(db, \
match_energy_bot\, ...) or get_game_config_int(db, \drill_basic_energy\, ...) so that the explicit text descriptions match the actual database configuration.


---

## 33. Profile Finance & Hospital Hub (US-40)

**Design:** `specs/003-profile-finance-hospital/`

| File | Role |
|------|------|
| `profile_cog.py` | `show_profile` + `ProfileHubView` (Manage Hospital / Finances / Club Stats) |
| `embeds/profile_embeds.py` | Finance + hospital summary formatters |
| `views/store_facilities.py` | `HospitalPanelView` `origin=profile|facilities` + Upgrade on panel |
| `economy_cog.py` | Shared finances embed for `/profile` Finances (slash `/club-finances` removed in 010) |
| `squad_cog.py` | `show_squad_hub` shared with profile Club Stats |

No new migration/RPC/slash command. Hospital math remains US-39 / migration 050.

---

## 34. Mentor Transfusion (US-41)

**Design:** `specs/006-mentor-transfusion/`

| Piece | Role |
|-------|------|
| `packages/player_engine/mentor_math.py` | 5 SP → 1 MP → 500 XP; eligibility; headroom; preview |
| `supabase/migrations/052_mentor_transfusion.sql` | `mentor_transfer_log` + `transfer_mentor_xp` → `apply_card_xp(..., 'mentor_transfer')` |
| `development_cog.py` | Allocate Skills mentor branch (target → amount → confirm) |
| `player_cog.py` | Mentor Ready profile copy |
| `api_errors.py` | Manager-facing mentor reject copy |

Daily cap: 3 transfers/club/UTC day. No coins/energy. No new slash command.

---

## 35. Active Fatigue Recovery (US-39 extension / 009)

**Design:** `specs/009-fatigue-recovery/`

| Piece | Role |
|-------|------|
| `packages/player_engine/fatigue.py` | `passive_recovery_amount`, `apply_recovery_session`, TG-aware `apply_passive_recovery` |
| `supabase/migrations/054_fatigue_recovery.sql` | `process_recovery_session` + TG-scaled `process_daily_recovery` + `game_config` seeds |
| `development_cog.py` | Training Drills: Recovery Session vs skill drills |
| `api_errors.py` | Fully rested / injured recovery copy |
| `scheduler_jobs.py` | Existing `daily_recovery_job` (unchanged caller) |

Recovery is **instant** (no async drill jobs). +40 fatigue, 0 XP, 0 coins, Basic-drill energy, shares drill caps. Passive = `15 + TG×5`. Bench +15 unchanged. No Store physio SKU. No new slash command.
