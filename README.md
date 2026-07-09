# ElevenBoss ⚽

ElevenBoss is a Discord-native football (soccer) manager game. Managers register a club, build a squad, play bot and league matches, develop players, and compete on division and global ladders.

---

## Project architecture

```text
ElevenBoss/
├── apps/discord_bot/          # Discord bot (cogs, views, DB/RPC wiring)
│   ├── main.py
│   ├── cogs/                  # Slash commands and hub flows
│   ├── core/                  # economy_rpc, match_rewards, scheduler jobs
│   ├── middleware/            # Registration guard, match locks
│   └── db/                    # Supabase async client
├── packages/                  # Pure Python game logic (no Discord, no DB IO)
│   ├── economy/
│   ├── player_engine/
│   ├── match_engine/
│   ├── leagues/
│   └── gacha/
├── supabase/migrations/       # Schema and RPCs (source of truth)
├── tests/                     # Unit and wiring tests
└── scripts/                   # Ops tools (economy sim, backfills)
```

**Hub commands**

| Command | Purpose |
|---------|---------|
| `/register` | Onboarding |
| `/squad` | Formation and lineup |
| `/battle` | Bot matches, friendlies, league fixtures |
| `/league` | Season registration and standings |
| `/development` | Drills, fusion, evolutions, skill points, claim rewards |
| `/store` | Daily login, energy refills, free pack |
| `/marketplace` | Agent sales, scouting |
| `/profile`, `/player-profile` | Club and card views |
| `/leaderboard` | Division, global LP, season standings |
| `/club-finances` | Wage forecast |
| `/admin` | Bot owner league configuration (DM) |

**Progression and economy pipes**

- Coins and energy: RPC `apply_club_economy` via [`apps/discord_bot/core/economy_rpc.py`](apps/discord_bot/core/economy_rpc.py)
- Match XP: `process_match_result` + `apply_card_xp` via [`apps/discord_bot/core/match_xp.py`](apps/discord_bot/core/match_xp.py)
- Formulas: [`packages/player_engine/player_engine/progression.py`](packages/player_engine/player_engine/progression.py)

---

## Local setup

### 1. Environment

Create `.env` at the repo root:

```env
DISCORD_TOKEN=your_discord_bot_token
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_service_role_key
DATABASE_URL=postgresql://...   # optional — ops scripts and migration apply
GUILD_ID=                       # optional — guild-scoped command sync for dev
```

Use the **service role** key on the trusted bot server only. Never expose it in client-side code.

### 2. Install and run

```bash
pip install -r requirements.txt
python -m apps.discord_bot.main
```

### 3. Database migrations

1. Add a new file under `supabase/migrations/NNN_name.sql`
2. Apply locally (e.g. `scratch/apply_migration_NNN.py` with `DATABASE_URL`)
3. Verify: `psql $DATABASE_URL -f supabase/scripts/verify_required_schema.sql`
4. Wire bot changes that depend on new RPCs/columns

### 4. Tests

```bash
pytest tests/ -q
```

CI runs the same on push/PR via [`.github/workflows/pytest.yml`](.github/workflows/pytest.yml).

---

## Documentation

- SDD: [`.specify/specs/v1.0.0/spec.md`](.specify/specs/v1.0.0/spec.md)
- Player-facing changes: [`change_log.md`](change_log.md)
- Agent rules: [`AGENTS.md`](AGENTS.md)
