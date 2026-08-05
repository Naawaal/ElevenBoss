# UI Contracts: Feature 054 — Instant PvP Backfill and Ghost Managers

**Branch**: `054-instant-pvp-backfill` | **Date**: 2026-08-05

## Discord UI & Presentation Specifications

### 1. Queue Status Embeds

#### Search Initial State (0–5s)
```text
🏟️ ElevenBoss Matchmaking

🔎 Finding Your Opponent...

Searching for:
1. 🟢 Live manager
2. 👻 Ghost manager snapshot
3. 🤖 Ranked AI backfill

Estimated start: under 10 seconds
Current phase: Live manager search

[Cancel Search]
```

#### Search Expanded State (5–10s)
```text
🏟️ ElevenBoss Matchmaking

🔎 Expanding Search Range...

No close live manager found yet.
Checking wider divisions before selecting a ghost opponent.

Estimated start: under 5 seconds

[Cancel Search]
```

---

### 2. Match Start Badges & Embeds

#### Live Human Opponent Found
```text
🟢 LIVE MANAGER MATCH

⚔️ Thunder FC vs Kathmandu Kings

Division: Professional (1,420 LP)
Opponent OVR: 82.4

Both managers are live in this stadium!
Full Ranked rewards and rivalry updates apply.
```

#### Ghost Manager Opponent Found
```text
👻 GHOST MANAGER MATCH

⚔️ Thunder FC vs Kathmandu Kings (Snapshot)

Division: Professional
Opponent OVR: 82.4
Snapshot Age: 9 hours ago

Facing a frozen squad & tactics snapshot from a real manager.
The opponent team is AI-controlled.
Reduced Ranked rewards apply (0.85x coins, 0.90x XP, 0.75x pos LP).
```

#### Ranked AI Backfill Opponent Found
```text
🤖 RANKED AI BACKFILL MATCH

⚔️ Thunder FC vs Professional Division XI

Division: Professional
Opponent OVR: 81.8 (Calibrated)

No eligible human or ghost opponent was available.
Ranked AI backfill simulation initiated.
Reduced Ranked rewards apply (0.70x coins, 0.75x XP, 0.50x pos LP).
```

---

### 3. Match History Entry Contract

Each match record presented in `/battle` -> Match History displays:

- **Mode Badge**: `🟢 LIVE`, `👻 GHOST (9h ago)`, or `🤖 RANKED AI`
- **Result & Score**: `WIN 2-1` / `LOSS 0-1`
- **LP Delta**: `+15 LP (Ghost Multiplier)` / `+20 LP (Live)`
- **Opponent Name**: Real manager name for Live & Ghost; Calibrated XI name for AI.
