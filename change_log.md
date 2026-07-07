# ElevenBoss — v2.0 Patch Notes

Hey Managers!

## Match Loop Hardening (US-29)

Bot and friendly matches now use the same economy and XP systems as league play.

### What changed
- **Bot matches** cost **20** ⚡ action energy (was 10 legacy energy) and pay coins through the audited economy ledger.
- **Per-card match XP** on bot and friendly matches — no more flat +15 XP for everyone.
- **Friendly matches** grant match XP to both managers' squads; winners earn friendly match coins.
- **Free pack** claims from `/store` are atomic — a failed insert no longer burns your 22h cooldown.
- **Matchday reminders** send at most one DM per manager per matchday (no hourly spam).
- Removed leftover debug logging and dead UI stubs from production code.

---

# ElevenBoss — v2.0 Patch Notes (archive)

Hey Managers!

## League Season Launch UX (US-28)

Season starts now look and feel like a real competition kickoff.

### What changed
- **Season kickoff** — role ping plus plain text: `{League}: Season N is Live!`, `/league hub` CTA, and season length.
- **Two locked threads** created at season start:
  - **League Journal** — official standings (pinned, edited after each match) + compact result lines.
  - **MatchDay** — live commentary, pitch visuals, match results with role ping, and end-of-matchday standings tables.
- Members **cannot post** in either thread (bot-only, read-only gallery).
- **Legacy seasons** (started before this update) keep the old single journal until the season ends.

---

## League Economy Balance (US-27)

League rewards are tuned so seasonal play stays exciting without flooding the economy.

### What changed
- **Entry fee** charged when a season starts (default **1,500** coins at Grassroots, scales by division). **Refunded** when you complete the season; managers who can't pay are not added to the roster.
- **Auto-sim matches** earn **50%** of normal league match coins (season prizes unchanged — play live when you can).
- **Retuned rewards:** lower per-match coins (250–400 win by division), smaller season prize pool (3,500 base), matchday milestone bonus 100 coins.
- **Registration requirements:** at least **10** career matches and a club **7** days old (shown in `/league hub` during registration).

---

## Immersive League Mode (US-26)

The guild seasonal league is now a proper competitive loop — separate from weekly Division Rank points.

### What changed
- **`/league hub`** shows your position, form, next opponent, and matchday countdown.
- **Season standings** come from fixtures only; **Division Rank Points** on `/profile` are from **bot battles** (weekly reset).
- League match **coins and XP** use the economy v2 / match XP pipes (league 1.25× XP multiplier).
- **League Journal** posts lineup pitches, live tickers, live table updates, and post-match GG/Poke buttons.
- **Opponent Scout** button in the hub (H2H, avg OVR).
- **Season-end prizes** distributed automatically when admins end a season.
- **Trophy cabinet** on `/profile` for past season finishes.
- Admins: **Open Registration**, **Configure Season** (size/duration/OVR cap), **Pause/Resume**.
- **Lineup familiarity** — keeping the same starting XI across matchdays builds a small team rating bonus; heavy rotation applies a penalty.
- **Matchday milestones** — hit the point threshold in a matchday (default 6 pts) for bonus coins.
- **Matchday reminders** — DM ~6 hours before your fixture window closes if you have an unplayed match.

---

This update overhauls player growth, unifies action energy, and rebuilds the club economy around auditable database flows. Here is what changed and where to find it in-game.

---

### Dynamic XP and level-ups
- Match XP scales with performance (goals, assists, MOTM, result, match type).
- Player level is derived from total XP via `level_from_xp` — no manual level-up button that bumps stats.
- XP curve: base grows per level (see `packages/player_engine/player_engine/progression.py`).

### Skill points and customization
- **+3 skill points** per level gained.
- Spend points under `/development` → **Allocate Skills** (or from `/player-profile` when points are available).
- Allocation respects POT caps and daily pacing (15 points/card/day during the pacing window).

### Claiming level rewards
- Level-up DMs notify you when retroactive rewards are pending.
- DMs disabled? Use **Claim Level Rewards** in the `/development` hub.

### Card fusion (fodder training)
- Sacrificing fodder grants **fusion XP** to the target (not direct stat bumps).
- **200 coins** per fusion; max **3 fusions/club/day**.

---

## Player Evolutions

- Up to **3 active evolutions** at once.
- **10-hour cooldown** on cold starts (replacement starts after a cancel bypass cooldown).
- Start cost: **25 Action Energy** + **500 + (5 × player OVR) coins**.
- Minimum player levels per track (e.g. Shooting Star requires level 10).

---

## Unified Action Energy

- **One pool:** `Action Energy` (max **100**) replaces separate match and training energy.
- **Regen:** **+1 energy every 6 minutes** (synced when you open hubs or run actions).
- **Costs:**
  - Bot match: **20** energy
  - Friendly match: **15** energy
  - League match: **10** energy
  - Basic drill: **10** energy
  - Advanced drill (player level 10+): **15** energy
  - Evolution start: **25** energy

### Where to refill and claim daily bonus
- Use **`/store`** — not `/development`.
- **Claim Daily Login:** once per UTC day; base **100 coins** + streak bonus (up to **+50**).
- **Buy Energy Refill:** **+50** energy; costs **200 / 400 / 600** coins for your 1st–3rd refill each day.

---

## Training Drills (coin + energy sinks)

Drills grant **XP only** (skill points come from leveling).

| Tier | Gate | Coins | Energy | XP (base) |
|------|------|-------|--------|-----------|
| Basic | Player level 1+ | 100 + 2×OVR | 10 | 30 |
| Advanced | Player level 10+ | 300 + 3×OVR | 15 | 80 |

**Daily caps:** 5 drills per player card, 20 drills per club (UTC day).

---

## Economy v2 (US-25)

### Match coin rewards (examples)
- **Bot:** win scales with division (base 200 × division multiplier); draw **100**; loss **50**.
- **League:** win **300–500** by server division tier; draw is one-third of win.
- **Friendly:** win **150** coins (XP only for losers).

All match coin and energy changes are applied atomically via `apply_club_economy` and logged in `economy_ledger`.

### Agent sales
- Sell bench players via `/marketplace` → agent offer formula unchanged.
- **Max 10 agent sales per club per day** (anti-inflation cap).

### Gems
- `tokens` display as **Gems** in profile/finances UI; earn/spend paths are minimal in v2.0 (display groundwork).

### Ops note (not player-facing)
- Economy tunables live in the `game_config` database table. No `/economy` admin slash commands.

---

## Daily progression caps (US-24)

| Cap | Limit |
|-----|-------|
| Match XP per card | 100/day |
| Drills per card | 5/day |
| Drills per club | 20/day |
| Skill allocation (pacing window) | 15 points/card/day |
| Fusions per club | 3/day |
| Agent sales per club | 10/day |
| Energy refills per club | 3/day |

Retroactive level rewards were scaled (75%, cap 18 per player) for veterans with unclaimed rows.

---

## Command quick reference

| Command | Purpose |
|---------|---------|
| `/store` | Daily login bonus + energy refills |
| `/development` | Drills, fusion, evolutions, skill allocation, claim level rewards |
| `/profile` | Coins, gems, action energy, records |
| `/club-finances` | Wallet + wage forecast (wages not auto-deducted) |
| `/marketplace` | Sell to agent (10/day cap) |
| `/battle how-it-works` | How NSS uses zone OVR, stats, and variance |

---

## Match engine transparency (NSS v2.1)

### What changed
- **Post-match possession and shots** are now counted from the live simulation (midfield duels + shots on goal), not random numbers.
- **Zone strengths** (GK / DEF / MID / ATT) appear in the post-match press conference.
- **Morale** and **PlayStyles** apply at kickoff; **PAS / DRI / SHO / PAC** influence the matching phase rolls.
- **Touchline** Attack/Defend now shifts home momentum as well as attack focus.
- Stronger squads win more often at +10 OVR (~75%+); large gaps (+30) remain dominant.

### How to read your result
- Use `/battle how-it-works` for the full breakdown.
- A better squad improves odds — it does not guarantee every match. Upsets are part of the design.

### Dev note: interval xG engine (future)
The repo also contains an interval-based xG engine (`packages/match_engine/match_engine.py`) with fatigue, substitutions, and five tactic presets. It is **not** wired to Discord yet. A future upgrade could run that engine for score generation while keeping the NSS highlight commentary layer on top — estimated 1–2 weeks of integration work.

---

Good luck on the pitch! Share feedback in your server or with the dev team.
