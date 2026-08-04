# Contract: Battle hub surfaces

**Feature**: `053-pvp-matchmaking-rivalries`  
**Surface**: Existing `/battle` group only — **no** new top-level slash.

## Commands (compat)

| Command | Behavior when PvP enabled | Rollback (flag off) |
|---------|---------------------------|---------------------|
| `/battle hub` | Redesigned arena embed + buttons | Legacy Bot Battle + Friendly tip |
| `/battle bot` | Compatibility guidance → AI Practice / hub | Legacy bot battle |
| `/battle friendly` | Unchanged sandbox + block checks | Unchanged |

## Hub embed (PvP on)

Must show: manager name, Global Division, Global LP, Action Energy, short Ranked blurb.

Buttons:

| Button | Action |
|--------|--------|
| Find Opponent | `join_pvp_queue` → search embed |
| Friendly Challenge | Existing invite flow (`/battle friendly` or modal/picker equivalent) |
| AI Practice | Practice match path (`run_type=practice`) |
| Rivalries | Rivalries view (slice 2; placeholder OK in slice 1) |
| Match History | Mode-labeled history (PvP / Practice / Friendly / League) |

## Queue UX

1. Searching embed: division, LP, XI OVR, current widening bands, elapsed seconds, “No energy spent”, Cancel.
2. Timeout (~60s): Continue Search | AI Practice | Cancel — **never** auto-AI.
3. Opponent Found: both clubs + division/LP/OVR → “Opening the stadium…” (join = consent; no second ready).

## Defer

All hub button handlers `defer` immediately before RPC/DB work.
