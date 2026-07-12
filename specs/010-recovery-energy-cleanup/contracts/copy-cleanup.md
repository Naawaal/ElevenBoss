# Contract: Player-facing pointer cleanup

**Feature**: `010-recovery-energy-cleanup`

## Required string updates

| Location | From (intent) | To (intent) |
|----------|---------------|-------------|
| `embeds/profile_embeds.py` `L0_EMPTY` | Build Hospital in the Store | Build/manage via `/profile` → Manage Hospital |
| `core/api_errors.py` injured Recovery | `/store` → Club Facilities or `/profile` | `/profile` → Manage Hospital |
| `cogs/development_cog.py` injured messages | Store facilities Hospital | `/profile` Manage Hospital |
| `core/injury_rpc.py` overflow DM | Store → Club Facilities → Hospital | `/profile` → Manage Hospital |
| `change_log.md` | Advertise Store Hospital + `/club-finances` | Profile-only Hospital; finances via `/profile`; note Recovery 5⚡ + energy max 120 |
| `development_cog.py` energy display | Hardcoded `/100` | Dynamic `/{max_energy}` (120) |
| Recovery preview defaults | Fallback 10 | Fallback **5** |

## Must not change

- Morale `…/100` in `player_cog.py`
- Hospital RPC error keys (only human copy paths that mention Store)
