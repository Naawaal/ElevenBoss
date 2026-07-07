# ElevenBoss ⚽

ElevenBoss is a Discord-native football (soccer) manager game. Players build a squad, configure tactical formations, simulate league matches, earn currency, level up players, and climb division leagues.

---

## 🗂️ Project Architecture

This project is structured as a Python monorepo using local editable package bindings:

```text
ElevenBoss/
├── apps/
│   └── discord_bot/               # Discord Gateway Application Layer
│       ├── main.py                # Bot Entrypoint
│       ├── cogs/                  # App slash commands
│       │   ├── onboarding_cog.py  # /register + setup wizard thread
│       │   ├── store_cog.py         # /store — daily login, energy refill, free pack
│       │   ├── squad_cog.py       # /squad-view, /squad-set-player, /squad-set-formation
│       │   ├── match_cog.py       # /match-play
│       │   ├── player_cog.py      # /player-level-up
│       │   └── profile_cog.py     # /profile
│       ├── core/                  # Scheduler & Thread Managers
│       ├── embeds/                # Embed designers
│       ├── middleware/            # Registration guard check
│       └── db/                    # Supabase async client
├── packages/                      # Pure Python core logic (No Discord or DB dependencies)
│   ├── energy/                    # Energy regen and recovery calculations
│   ├── economy/                   # Level-up calculations and rating caps
│   ├── gacha/                     # Pack opening and starter squad generator
│   ├── match_engine/              # Match outcomes simulation
│   └── leagues/                   # Division promotions/relegations
└── supabase/
    └── migrations/                # Database migrations
```

---

## 🚀 Local Setup Instructions

Follow these instructions to run the ElevenBoss server locally:

### 1. Environment Configuration
Create a `.env` file at the root of the workspace using the following format:
```env
DISCORD_TOKEN=your_discord_bot_token
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_api_service_key
```

### 2. Dependency Setup
We use editable installs (`pip install -e`) to bind the core packages into the local virtual environment. Run the following:
```bash
# 1. Install packages in editable mode
pip install -e packages/match_engine
pip install -e packages/economy
pip install -e packages/gacha
pip install -e packages/leagues
pip install -e packages/energy

# 2. Install production dependencies
pip install -r requirements.txt
```

### 3. Database Schema Setup
Execute the SQL files inside the `supabase/migrations/` directory against your Supabase SQL Editor in the following order:
1. `001_initial_schema.sql` (Creates tables: `players`, `player_cards`, `squads`, `squad_assignments`, `match_history`)
2. `002_indexes.sql` (Creates search performance indexes)
3. `003_rpc_functions.sql` (Creates `regen_energy_tick()` function)
4. `005_register_rpc.sql` (Creates `register_new_player(...)` atomic transaction RPC)

### 4. Running the Bot
Once your database and environment variables are ready, start the bot:
```bash
python -m apps.discord_bot.main
```
This launches the bot, registers the scheduled jobs, and synchronizes the application commands tree.
