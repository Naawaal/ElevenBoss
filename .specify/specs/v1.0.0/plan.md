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
    gk            UUID REFERENCES player_cards(id),
    slot_1        UUID REFERENCES player_cards(id),
    slot_2        UUID REFERENCES player_cards(id),
    slot_3        UUID REFERENCES player_cards(id),
    slot_4        UUID REFERENCES player_cards(id),
    slot_5        UUID REFERENCES player_cards(id),
    slot_6        UUID REFERENCES player_cards(id),
    slot_7        UUID REFERENCES player_cards(id),
    slot_8        UUID REFERENCES player_cards(id),
    slot_9        UUID REFERENCES player_cards(id),
    slot_10       UUID REFERENCES player_cards(id),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

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
- `ensure_registered` guard on all non-registration commands: **responds with prompt embed, does NOT create accounts**
- All commands `defer(ephemeral=True)` immediately

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
                                                                 and gk/slot_1..slot_10 set to
                                                                 the 11 collected UUIDs
                                                                 (ordered GK→DEF→MID→FWD)
                                                                   └─► Marquee Reveal embed
                                                                         (Captain stats displayed)
                                                                           └─► Registration Complete embed
                                                                                 ("[Name] + 10 youth, 4-4-2 ready")
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
