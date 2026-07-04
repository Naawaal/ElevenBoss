# ElevenBoss v1.0.0 — Implementation Tasks (`tasks.md`)

**Feature**: Core Game Loop — v1.0.0 Initial Release
**Status**: Pending Implementation Approval
**Depends On**: `plan.md` v1.0.0

> Tasks are strictly ordered. Do not begin a task group until all tasks in the preceding group are complete.

---

## Task Group 1: Monorepo Directory Scaffolding ← START HERE

### T1.1 — Create `apps/discord_bot` directory tree
```powershell
New-Item -ItemType Directory -Force -Path `
  "apps\discord_bot\cogs", `
  "apps\discord_bot\core", `
  "apps\discord_bot\embeds", `
  "apps\discord_bot\middleware", `
  "apps\discord_bot\db"
"" | Set-Content "apps\discord_bot\__init__.py"
"" | Set-Content "apps\discord_bot\cogs\__init__.py"
"" | Set-Content "apps\discord_bot\core\__init__.py"
"" | Set-Content "apps\discord_bot\embeds\__init__.py"
```

### T1.2 — Create five packages under `packages/`
```powershell
$packages = @("match_engine","economy","gacha","leagues","energy")
foreach ($pkg in $packages) {
    New-Item -ItemType Directory -Force -Path "packages\$pkg\$pkg"
    "" | Set-Content "packages\$pkg\$pkg\__init__.py"
    "" | Set-Content "packages\$pkg\$pkg\models.py"
}
New-Item -ItemType Directory -Force -Path "packages\gacha\gacha\data"
```

### T1.3 — Create `pyproject.toml` for each package
(Repeat for each package, changing `name`.)
```toml
# packages/<name>/pyproject.toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "<name>"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["pydantic>=2.0.0"]
```

### T1.4 — Install all packages as editable installs
```bash
pip install -e packages/match_engine
pip install -e packages/economy
pip install -e packages/gacha
pip install -e packages/leagues
pip install -e packages/energy
```
**Verify**: `pip list | findstr /i "match economy gacha leagues energy"` — all 5 must appear.

### T1.5 — Install production dependencies
```bash
pip install "discord.py>=2.7.0" "supabase>=2.0.0" "pydantic>=2.0.0" "apscheduler>=3.10.0" "python-dotenv>=1.0.0"
pip freeze > requirements.txt
```

### T1.6 — Create migrations directory
```powershell
New-Item -ItemType Directory -Force -Path "supabase\migrations"
```

---

## Task Group 2: Database Schema

### T2.1 — Write `supabase/migrations/001_initial_schema.sql`
```sql
CREATE TABLE IF NOT EXISTS players (
    discord_id      BIGINT PRIMARY KEY,
    username        TEXT NOT NULL,
    club_name       TEXT NOT NULL DEFAULT '',
    manager_name    TEXT NOT NULL DEFAULT '',
    coins           INTEGER NOT NULL DEFAULT 500 CHECK (coins >= 0),
    energy          INTEGER NOT NULL DEFAULT 100,
    max_energy      INTEGER NOT NULL DEFAULT 100,
    division        TEXT NOT NULL DEFAULT 'Grassroots'
                      CHECK (division IN ('Grassroots','Amateur','Semi-Pro','Professional','Elite','Legendary')),
    league_points   INTEGER NOT NULL DEFAULT 0,
    goal_difference INTEGER NOT NULL DEFAULT 0,
    matches_played  INTEGER NOT NULL DEFAULT 0,
    wins            INTEGER NOT NULL DEFAULT 0,
    draws           INTEGER NOT NULL DEFAULT 0,
    losses          INTEGER NOT NULL DEFAULT 0,
    last_claim_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS player_cards (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id    BIGINT NOT NULL REFERENCES players(discord_id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    position    TEXT NOT NULL CHECK (position IN ('GK','DEF','MID','FWD')),
    rarity      TEXT NOT NULL CHECK (rarity IN ('Common','Rare','Epic','Legendary')),
    base_rating INTEGER NOT NULL,
    level       INTEGER NOT NULL DEFAULT 1,
    overall     INTEGER NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS squads (
    discord_id BIGINT PRIMARY KEY REFERENCES players(discord_id) ON DELETE CASCADE,
    formation  TEXT NOT NULL DEFAULT '4-4-2',
    gk         UUID REFERENCES player_cards(id),
    slot_1     UUID REFERENCES player_cards(id),
    slot_2     UUID REFERENCES player_cards(id),
    slot_3     UUID REFERENCES player_cards(id),
    slot_4     UUID REFERENCES player_cards(id),
    slot_5     UUID REFERENCES player_cards(id),
    slot_6     UUID REFERENCES player_cards(id),
    slot_7     UUID REFERENCES player_cards(id),
    slot_8     UUID REFERENCES player_cards(id),
    slot_9     UUID REFERENCES player_cards(id),
    slot_10    UUID REFERENCES player_cards(id),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS match_history (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    player_id       BIGINT NOT NULL REFERENCES players(discord_id),
    result          TEXT NOT NULL CHECK (result IN ('win','draw','loss')),
    my_rating       NUMERIC(5,2) NOT NULL,
    opponent_rating NUMERIC(5,2) NOT NULL,
    goals_for       INTEGER NOT NULL,
    goals_against   INTEGER NOT NULL,
    coins_earned    INTEGER NOT NULL,
    points_earned   INTEGER NOT NULL,
    played_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### T2.2 — Write `supabase/migrations/002_indexes.sql`
```sql
CREATE INDEX IF NOT EXISTS idx_player_cards_owner ON player_cards(owner_id);
CREATE INDEX IF NOT EXISTS idx_match_history_player ON match_history(player_id);
CREATE INDEX IF NOT EXISTS idx_players_division ON players(division);
```

### T2.3 — Write `supabase/migrations/003_rpc_functions.sql`
```sql
CREATE OR REPLACE FUNCTION regen_energy_tick()
RETURNS void LANGUAGE sql AS $$
  UPDATE players SET energy = LEAST(energy + 2, max_energy) WHERE energy < max_energy;
$$;
```

### T2.4 — Apply migrations via Supabase Dashboard SQL Editor
Execute files 001, 002, 003 in order. Verify all 4 tables and 1 function exist.

### T2.5 — (Existing DB only) Add `club_name` and `manager_name` columns via migration

**File**: `supabase/migrations/004_add_club_fields.sql`
```sql
-- Only needed if players table already exists from a prior migration.
-- Safe to skip if running fresh from 001_initial_schema.sql.
ALTER TABLE players
  ADD COLUMN IF NOT EXISTS club_name    TEXT NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS manager_name TEXT NOT NULL DEFAULT '';
```
Apply via Supabase Dashboard SQL Editor. Verify columns appear in the Table Editor before proceeding.

---

## Task Group 3: Pure Package Logic

### T3.1 — `packages/energy/energy/calculator.py`
Implement: `apply_regen_tick()`, `ticks_to_full()`, `minutes_to_full()`.

### T3.2 — `packages/economy/economy/calculator.py`
Implement: `level_up_cost()`, `rarity_rating_cap()`, `compute_new_overall()`.

### T3.3 — `packages/gacha/gacha/generator.py` + `data/player_names.json`

**Part A**: Implement `generate_pack(n=5)` with weighted rarity draws. Create names JSON with 100+ first/last names.

**Part B**: Implement `generate_starter_squad() -> StarterSquad`:

```python
from __future__ import annotations
import random
from .models import GachaPlayer, GachaPack, StarterSquad, RARITY_RATING_RANGES

# Positional blueprint for the 10 Common youth players
_YOUTH_POSITIONS: list[str] = ["GK", "DEF", "DEF", "DEF", "DEF", "MID", "MID", "MID", "MID", "FWD", "FWD"]
# The Marquee slot replaces one non-GK position
_MARQUEE_POSITIONS: list[str] = ["DEF", "DEF", "MID", "MID", "MID", "FWD"]  # weighted towards MID/FWD

def _make_player(position: str, rarity: str, names: dict[str, list[str]]) -> GachaPlayer:
    lo, hi = RARITY_RATING_RANGES[rarity]
    return GachaPlayer(
        name=f"{random.choice(names['first'])} {random.choice(names['last'])}",
        position=position,
        rarity=rarity,
        base_rating=random.randint(lo, hi),
        overall=random.randint(lo, hi),  # level 1: overall == base_rating
    )

def generate_starter_squad() -> StarterSquad:
    """
    Generates a guaranteed 11-player squad for onboarding:
    - 1 Marquee: Rare (80%) or Epic (20%), non-GK position.
    - 10 Youth: All Common, covering the full 4-4-2 formation blueprint.
    Returns a StarterSquad where youth list has the Marquee's positional slot
    replaced by the Marquee card itself (youth keep Common coverage for all other slots).
    """
    names = _load_names()

    # 1. Draw Marquee rarity and position
    marquee_rarity = random.choices(["Rare", "Epic"], weights=[80, 20], k=1)[0]
    marquee_position = random.choice(_MARQUEE_POSITIONS)
    marquee = _make_player(marquee_position, marquee_rarity, names)

    # 2. Build 10 Common youth players covering ALL 11 positional slots,
    #    then remove ONE card matching the Marquee's position so the total is 10.
    full_common_positions = list(_YOUTH_POSITIONS)  # 11 slots including GK
    # Remove Marquee's position from one slot (first match)
    full_common_positions.remove(marquee_position)
    # Now we have 10 positions for Common youth
    youth = [_make_player(pos, "Common", names) for pos in full_common_positions]

    return StarterSquad(marquee=marquee, youth=youth)
```

**Verify**: Call `generate_starter_squad()` in a Python REPL. Assert:
- `len(squad.all_players) == 11`
- Exactly 1 GK, 4 DEF, 4 MID, 2 FWD in `squad.all_players`
- `squad.marquee.rarity in ("Rare", "Epic")`
- All youth rarity == `"Common"`

### T3.4 — `packages/match_engine/match_engine/simulator.py`
Implement: `simulate_match(MatchInput) -> MatchResult` with Gaussian rating modifier.

### T3.5 — `packages/leagues/leagues/calculator.py`
Implement: `compute_promotions_relegations(entries) -> PromotionResult`.

---

## Task Group 4: Supabase Client

### T4.1 — `apps/discord_bot/db/client.py`
Implement async singleton using `supabase.acreate_client()` reading from `.env`.

---

## Task Group 5: Registration Guard Middleware

### T5.1 — `apps/discord_bot/middleware/guard.py`

Implement `ensure_registered(interaction: discord.Interaction) -> bool` as an `app_commands` check.

**Behaviour**:
- Query `players` table for `interaction.user.id`.
- If row **exists** → return `True` (allow command through).
- If row **does not exist** → send ephemeral embed: *"You don't have a club yet! Run `/register` to get started."* → return `False` (block command).
- **Critical**: This function MUST NOT insert any database rows. Account creation is exclusively the domain of `OnboardingCog`.

```python
async def ensure_registered(interaction: discord.Interaction) -> bool:
    db = await get_client()
    result = await db.table("players").select("discord_id") \
        .eq("discord_id", interaction.user.id).maybe_single().execute()
    if result.data is None:
        await interaction.response.send_message(
            embed=error_embed("You don't have a club yet! Run `/register` to get started."),
            ephemeral=True
        )
        return False
    return True
```

Add `@app_commands.check(ensure_registered)` to every cog command **except** `/register`.

---

## Task Group 6: ThreadManager Core Module

### T6.1 — `apps/discord_bot/core/thread_manager.py`

Implement the `ThreadManager` class with the following methods:

```python
from __future__ import annotations
import asyncio
import logging
import discord
from discord.ext import commands

logger = logging.getLogger(__name__)

class ThreadManager:
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def create_onboarding_thread(
        self,
        interaction: discord.Interaction,
        owner_id: int,
    ) -> discord.Thread:
        """
        Creates a private thread (or public fallback) off the invocation channel.
        Sends the initial welcome embed + WelcomeView into the thread.
        Returns the created Thread object.
        """
        channel = interaction.channel
        # Prefer private thread; fall back to public if guild lacks PRIVATE_THREADS
        thread_type = discord.ChannelType.private_thread
        if not isinstance(channel, discord.TextChannel) or \
           "PRIVATE_THREADS" not in interaction.guild.features:
            thread_type = discord.ChannelType.public_thread

        thread: discord.Thread = await channel.create_thread(
            name=f"⚽ ElevenBoss — Welcome, {interaction.user.display_name}!",
            type=thread_type,
            auto_archive_duration=60,
            reason="ElevenBoss onboarding wizard",
        )
        return thread

    async def delete_thread_after(
        self,
        thread: discord.Thread,
        delay_seconds: int,
        *,
        countdown_message: discord.Message | None = None,
    ) -> None:
        """
        Counts down on countdown_message (if provided), then deletes the thread.
        """
        if countdown_message and delay_seconds > 0:
            for remaining in range(delay_seconds, 0, -1):
                try:
                    await countdown_message.edit(
                        content=f"🕐 This setup room closes in **{remaining}s**..."
                    )
                    await asyncio.sleep(1)
                except discord.HTTPException:
                    break
        try:
            await thread.delete()
        except discord.HTTPException:
            logger.warning("Failed to delete onboarding thread %s", thread.id)

    def check_owner(
        self, interaction: discord.Interaction, owner_id: int
    ) -> bool:
        """Validates that the interacting user is the thread owner."""
        return interaction.user.id == owner_id
```

**Verify**: Unit-testable in isolation (all discord objects are injected, not fetched internally).

---

## Task Group 7: Onboarding Cog — UI Components & Flow

### T7.1 — `apps/discord_bot/embeds/onboarding_embeds.py`

Implement the following embed factory functions (all return `discord.Embed`):
- `welcome_thread_embed(username: str) -> discord.Embed` — Initial thread embed with game branding.
- `club_confirmation_embed(club_name: str, manager_name: str) -> discord.Embed` — Confirmation step.
- `recruitment_embed(step_text: str) -> discord.Embed` — Generic recruitment animation frame embed (reused for all 7 animation steps).
- `marquee_reveal_embed(player: GachaPlayer) -> discord.Embed` — Full-screen Captain card reveal (name, position, rarity ✨, overall rating, flavour text: *"Your club's Captain"*).
- `registration_complete_embed(marquee: GachaPlayer, club_name: str, manager_name: str) -> discord.Embed` — Final summary embed. Must include:
  - Marquee card summary.
  - Body text: *"You've signed **[marquee.name]** to lead your club, alongside 10 youth academy prospects! Your starting 11 has been auto-assigned in a 4-4-2 and is ready for the pitch."*
  - Footer: *"Use `/match play` to kick off, or `/squad view` to inspect your squad."*

### T7.2 — `ClubSetupModal` (`discord.ui.Modal`)

Implement inside `apps/discord_bot/cogs/onboarding_cog.py`:

```python
class ClubSetupModal(discord.ui.Modal, title="Set Up Your Club"):
    club_name = discord.ui.TextInput(
        label="Club Name",
        placeholder="e.g. FC Midnight",
        max_length=32,
        required=True,
    )
    manager_name = discord.ui.TextInput(
        label="Manager Name",
        placeholder="e.g. Sir Alex",
        max_length=24,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        # Store values on the modal instance for the calling View to read
        self.submitted_club = self.club_name.value
        self.submitted_manager = self.manager_name.value
        await interaction.response.defer()  # Deferred — View reads values and sends confirmation
```

### T7.3 — `WelcomeView` (`discord.ui.View`)

Single **"Begin Setup →"** button. On click:
1. Validates `thread_manager.check_owner(interaction, owner_id)` — if False, respond ephemeral.
2. Presents `ClubSetupModal`.
3. On modal submit, sends `ConfirmationView`.

```python
class WelcomeView(discord.ui.View):
    def __init__(self, owner_id: int, thread_manager: ThreadManager) -> None:
        super().__init__(timeout=3600)  # 60-minute view timeout
        self.owner_id = owner_id
        self.thread_manager = thread_manager

    async def on_timeout(self) -> None:
        # Disable all buttons; thread auto-archives via Discord
        for item in self.children:
            item.disabled = True

    @discord.ui.button(label="Begin Setup →", style=discord.ButtonStyle.primary, emoji="⚽")
    async def begin(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self.thread_manager.check_owner(interaction, self.owner_id):
            await interaction.response.send_message(
                "This setup wizard belongs to another player.", ephemeral=True
            )
            return
        modal = ClubSetupModal()
        await interaction.response.send_modal(modal)
        await modal.wait()
        # Present confirmation
        view = ConfirmationView(self.owner_id, self.thread_manager, modal.submitted_club, modal.submitted_manager)
        await interaction.followup.send(
            embed=club_confirmation_embed(modal.submitted_club, modal.submitted_manager),
            view=view
        )
        self.stop()
```

### T7.4 — `ConfirmationView` (`discord.ui.View`)

Two buttons: ✅ **"Confirm Club"** and ✏️ **"Edit Details"**.

- **Edit**: Re-presents `ClubSetupModal`, updates stored values, re-sends `ConfirmationView`.
- **Confirm**: Calls `_run_recruitment_animation()` coroutine.

### T7.5 — Recruitment Animation coroutine

Implement `_run_recruitment_animation(message, thread, club_name, manager_name, owner_id)` as a standalone `async def` in `onboarding_cog.py`:

```python
ANIMATION_STEPS = [
    (0.0,  "🔎 Scouting the transfer market for your Marquee signing..."),
    (1.5,  "📋 Reviewing elite player dossiers..."),
    (1.5,  "🤝 Initiating contract negotiations..."),
    (1.5,  "❌ Rejected! Agent demands too high. Moving on..."),
    (2.0,  "🤝 New target found. Making an offer..."),
    (1.5,  "⏳ Waiting for a response..."),
    (2.0,  "✅ SIGNED! Your club's Captain has arrived!"),
]

async def _run_recruitment_animation(
    message: discord.Message,
    thread: discord.Thread,
    club_name: str,
    manager_name: str,
    owner_id: int,
    thread_manager: ThreadManager,
    db: AsyncClient,
    user: discord.Member | discord.User,
) -> None:
    # Phase 1: Run animation steps
    for delay, text in ANIMATION_STEPS:
        if delay > 0:
            await asyncio.sleep(delay)
        await message.edit(embed=recruitment_embed(text), view=None)

    # Phase 2: Generate full 11-player starter squad (pure package logic, no discord)
    squad = generate_starter_squad()          # returns StarterSquad
    marquee = squad.marquee                   # Rare/Epic Captain
    all_players = squad.all_players           # 11 ordered GK->DEF->MID->FWD

    # Phase 3: Show Marquee Reveal embed (Captain spotlight)
    await asyncio.sleep(0.5)
    await message.edit(embed=marquee_reveal_embed(marquee))
    await asyncio.sleep(2.5)

    # Phase 4: Execute atomic Supabase transaction (all 11 players + squad slots)
    cards_payload = [
        {
            "name":        p.name,
            "position":    p.position,
            "rarity":      p.rarity,
            "base_rating": p.base_rating,
            "overall":     p.base_rating,   # level 1
        }
        for p in all_players
    ]
    await db.rpc("register_new_player", {
        "p_discord_id":   owner_id,
        "p_username":     str(user),
        "p_club_name":    club_name,
        "p_manager_name": manager_name,
        "p_cards":        cards_payload,     # JSON array of 11 card dicts
    }).execute()

    # Phase 5: Send Registration Complete embed and schedule thread deletion
    countdown_msg = await thread.send(
        embed=registration_complete_embed(marquee, club_name, manager_name)
    )
    await thread_manager.delete_thread_after(thread, delay_seconds=10, countdown_message=countdown_msg)
```

### T7.6 — `supabase/migrations/005_register_rpc.sql`

Create the atomic registration stored procedure (called in T7.5). This version accepts a **JSON array of 11 player cards** and populates all squad slots in one transaction:

```sql
CREATE OR REPLACE FUNCTION register_new_player(
    p_discord_id    BIGINT,
    p_username      TEXT,
    p_club_name     TEXT,
    p_manager_name  TEXT,
    p_cards         JSONB   -- Array of 11 objects: {name, position, rarity, base_rating, overall}
                            -- Ordered: [GK, DEF×4, MID×4, FWD×2]
) RETURNS void LANGUAGE plpgsql AS $$
DECLARE
    v_card_ids   UUID[] := ARRAY[]::UUID[];
    v_card       JSONB;
    v_new_id     UUID;
BEGIN
    -- 1. Create the player account
    INSERT INTO players (discord_id, username, club_name, manager_name)
    VALUES (p_discord_id, p_username, p_club_name, p_manager_name);

    -- 2. Insert all 11 player cards, collecting UUIDs in order
    FOR v_card IN SELECT * FROM jsonb_array_elements(p_cards)
    LOOP
        INSERT INTO player_cards (owner_id, name, position, rarity, base_rating, overall)
        VALUES (
            p_discord_id,
            v_card->>'name',
            v_card->>'position',
            v_card->>'rarity',
            (v_card->>'base_rating')::INTEGER,
            (v_card->>'overall')::INTEGER
        )
        RETURNING id INTO v_new_id;
        v_card_ids := array_append(v_card_ids, v_new_id);
    END LOOP;

    -- 3. Create squad row and populate all 11 slots with the collected UUIDs
    --    Array index: 1=GK, 2=DEF1, 3=DEF2, 4=DEF3, 5=DEF4,
    --                 6=MID1, 7=MID2, 8=MID3, 9=MID4, 10=FWD1, 11=FWD2
    INSERT INTO squads (
        discord_id, formation,
        gk,
        slot_1, slot_2, slot_3, slot_4,
        slot_5, slot_6, slot_7, slot_8,
        slot_9, slot_10
    ) VALUES (
        p_discord_id, '4-4-2',
        v_card_ids[1],                              -- GK
        v_card_ids[2], v_card_ids[3],              -- DEF
        v_card_ids[4], v_card_ids[5],              -- DEF
        v_card_ids[6], v_card_ids[7],              -- MID
        v_card_ids[8], v_card_ids[9],              -- MID
        v_card_ids[10], v_card_ids[11]             -- FWD
    );
END;
$$;
```

> [!IMPORTANT]
> The `p_cards` JSONB array **must** be passed in positional order `[GK, DEF×4, MID×4, FWD×2]`. The `StarterSquad.all_players` property guarantees this ordering via the `["GK","DEF","MID","FWD"]` sort key.

Apply via Supabase Dashboard SQL Editor. Verify function appears in Database → Functions.

### T7.7 — Wire `OnboardingCog` and `ThreadManager` into `main.py`

```python
# In main.py on_ready or setup_hook:
thread_manager = ThreadManager(bot)
bot.thread_manager = thread_manager  # Attach to bot for cog access

# Add to COGS list:
"apps.discord_bot.cogs.onboarding_cog"
```

---

## Task Group 8: Supabase Client

### T8.1 — `apps/discord_bot/db/client.py`
Implement async singleton using `supabase.acreate_client()` reading from `.env`.

---

## Task Group 9: Remaining Discord Cogs

### T9.1 — `apps/discord_bot/embeds/common_embeds.py`
Implement `error_embed()`, `success_embed()`.

### T9.2 — `apps/discord_bot/cogs/profile_cog.py` (US-08)
`/profile`: Check guard → fetch player row → build stat embed including `club_name` and `manager_name`.

### T9.3 — `apps/discord_bot/cogs/gacha_cog.py` (US-02)
`/gacha claim`: Guard check → cooldown check → `generate_pack()` → insert cards + update timestamp (transactional).

### T9.4 — `apps/discord_bot/cogs/squad_cog.py` (US-03)
`/squad view`, `/squad set-formation`, `/squad set-player`. All with guard check.

### T9.5 — `apps/discord_bot/cogs/match_cog.py` (US-05)
`/match play`: Guard check → energy check → squad fetch → `simulate_match()` → transactional stat update.

### T9.6 — `apps/discord_bot/cogs/player_cog.py` (US-06)
`/player level-up <player_id>`: Guard check → cost check → cap check → transactional level/coin update.

---

## Task Group 10: APScheduler Jobs

### T10.1 — Energy regen job (every 5 minutes)
```python
async def energy_regen_job() -> None:
    db = await get_client()
    await db.rpc("regen_energy_tick", {}).execute()
```

### T10.2 — Weekly league reset job (Monday 00:00 UTC)
Fetch all players → group by division → `compute_promotions_relegations()` → bulk UPDATE divisions → reset points/GD → send DMs.

---

## Task Group 11: Bot Entrypoint

### T11.1 — `apps/discord_bot/main.py`
Wire bot, scheduler, cog loading (including `onboarding_cog`), `ThreadManager` instantiation, `on_ready` → `tree.sync()`.
Register jobs: energy regen `interval minutes=5`, league reset `cron day_of_week=mon hour=0`.

---

## Task Group 12: Smoke Test

### T12.1 — Start the bot
```bash
python -m apps.discord_bot.main
```

### T12.2 — Manual verification checklist

| Command / Action | Expected |
|---|---|
| `/gacha claim` (unregistered) | Ephemeral: "You don't have a club yet! Run `/register`" |
| `/register` (new user) | Ephemeral link to new thread; thread created in channel |
| Click **"Begin Setup →"** | `ClubSetupModal` appears |
| Submit Modal | Confirmation embed with ✅ / ✏️ buttons |
| Click **"Edit Details"** | Modal re-opens with prior values |
| Click **"Confirm Club"** | Animation begins; 7 message edits play sequentially |
| Animation completes | Signed player card embed appears |
| Registration complete | Countdown embed shown; thread deleted after 10s |
| `/register` (already registered) | Ephemeral: already registered message |
| `/profile` (after registration) | Shows Club Name + Manager Name in embed |
| `/gacha claim` (after registration) | 5 cards reveal embed |
| `/gacha claim` (immediate) | Cooldown timer embed |
| `/match play` (squad full, energy ok) | Result embed with score |
| `/player level-up <id>` | Level up success |
| Other user clicks wizard button | Ephemeral: "This setup wizard belongs to another player." |

---

## Task Group 13: Constitution Compliance Audit

- [ ] No `packages/` module imports `discord`
- [ ] `thread_manager.py` is in `apps/discord_bot/core/`, NOT in `packages/`
- [ ] `ensure_registered` guard does NOT insert database rows
- [ ] All financial writes use transactions or RPC (including `register_new_player` stored procedure)
- [ ] All commands `defer(ephemeral=True)` immediately (or `send_modal()` for `/register`)
- [ ] All handlers have `try/except` with `logger.exception()`
- [ ] `ThreadManager.check_owner()` called before every wizard button handler
- [ ] All cross-module data is Pydantic `BaseModel`
- [ ] `from __future__ import annotations` in every `.py` file
- [ ] No orphaned threads possible: all error paths call `delete_thread_after()`
