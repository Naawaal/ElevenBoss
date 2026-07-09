# ElevenBoss — v2.0 Patch Notes

Hey Managers!

## Audit Remediation (US-38 follow-up)

Security and fairness hardening from the full codebase audit — mostly invisible, but it protects your progress and coins.

### What changed
- **Economy idempotency** — match payouts, daily login, and other coin grants can no longer double-apply under retry or lag (ledger + balance stay in sync).
- **Atomic match locks** — you cannot start two bot, league, or friendly matches at once by double-tapping.
- **Career stats** — wins, LP, and match counts update atomically after bot and league matches (no lost progress under concurrency).
- **Match XP safety** — duplicate XP grants on the same match result are blocked at the database layer.
- **Contract renewal & evolution cancel** — fees now flow through the same audited economy pipe as everything else.
- **Admin-only RPCs** — season prize distribution, entry-fee sweeps, season aging, and scouting pool inserts are no longer callable with a public API key (bot server uses service role only).
- **Removed legacy training RPC** — old direct coin-deduction path retired.
- **UX fixes** — `/leaderboard` is guild-only; formation changes blocked mid-match; bot match errors no longer leak raw server text in public channels.

### For server operators
- Ensure `SUPABASE_KEY` on the bot is the **service role** key (not anon).
- Migration **047** must be applied before deploying this bot build.

---

## Stat Drills Hotfix

Stat drills were failing for all managers immediately after the age system shipped.

### What changed
- **Fixed:** age-based XP multipliers now read correctly from game config.
- **Action:** drills work again under **`/development` → Stat Drills**.

---

## Player Age & Lifecycle (US-31 — Phase A)

Your squad now ages over time — plan around youth development and veteran decline.

### What changed
- **Date of birth** is stored on every player card; age updates from DOB (shown on `/player-profile` with lifecycle phase: Youth → Early Prime → Late Prime → Veteran → Retiring).
- **Match & drill XP** scale with age — youth earn more, veterans less.
- **Weekly aging** runs every **Monday 00:00 UTC**: veterans lose PAC/PHY (and PAS/DEF at 33+), players get a retirement warning at **35**, and auto-retire at **36** (removed from your starting XI).
- **Contract renewal** blocked at age **35+**; agent sale offers factor in age and potential.

### Age XP multipliers

| Phase | Ages | Match & drill XP |
|-------|------|------------------|
| Youth | ≤21 | ×1.50 |
| Early Prime | 22–26 | ×1.20 |
| Late Prime | 27–30 | ×1.00 |
| Veteran | 31–34 | ×0.70 |
| Retiring | 35+ | ×0.40 |

Training Ground bonus (+0 to +4 flat drill XP) stacks on top — see Club Facilities below.

---

## Youth Academy Intake (US-32 — Phase B)

Every season brings fresh prospects — rebuild without relying only on daily packs.

### What changed
- **3 youth prospects** (default) arrive each **Monday 00:00 UTC** for every manager (ages 16–19).
- **L1 Youth Academy baseline:** OVR 50–65, POT 72–82.
- **Higher Youth Academy levels** (`/store` → Club Facilities) raise intake OVR/POT ceilings and add a small **gem prospect** chance from L2 upward.
- New intake players join your **roster** — they are **not** auto-assigned to your starting XI.
- You'll get a **DM** listing the new prospects when DMs are enabled.

---

## Club Facilities (US-33 — Phase C)

Invest coins to improve your academy and training ground over time.

### What changed
- **`/store` → Club Facilities** — upgrade **Youth Academy** (better weekly intake) or **Training Ground** (flat drill XP bonus).
- **Youth Academy:** L1 is the baseline band above; higher levels widen OVR/POT ceilings up to roughly **56–69 OVR / 72–94 POT** at L5, with rising gem-prospect odds.
- **Training Ground:** **L1 +0 … L5 +4** flat bonus drill XP (shown on the Stat Drills hub).
- **Costs:** 750 / 2,000 / 5,000 / 12,000 coins per level (same all divisions).
- **Level 1 is free** — upgrades are optional; max **1 upgrade per UTC week**.
- **L2** requires **5** career matches; **L4** requires **20**.

---

## Scouting Pool / Regen Market (US-34 — Phase D)

When star players retire, youth regens hit the global market.

### What changed
- Veterans **75+ OVR** who retire each season spawn a **youth regen** on the scouting market (same position, ages 16–19).
- **`/marketplace` → Search Market** — browse and sign available regens for coins.
- **Sign cost** is roughly **40% above** what you'd receive selling a similar player to an agent.
- Listings appear after the **Monday 00:00 UTC** season aging batch (retirements feed the pool).

---

## Monday 00:00 UTC — weekly batch

Several systems fire at the same minute each Monday:

- **Season aging** — stat decline, retirement warnings, auto-retire at 36 (feeds regen listings).
- **Youth intake** — 3 prospects per manager (independent of aging).
- **Regen scouting pool** — new Search Market listings from that week's retirements.
- **Weekly league reset** — division promotions/relegations and Division Rank reset (separate from age).

---

## Friendly Matches — Free Sandbox (US-18)

Friendly matches are now pure sparring — no cost, no grind rewards.

### What changed
- **No action energy** required to challenge or play a friendly match.
- **No coins, card XP, or career record updates** — your profile stats stay untouched.
- **League registration** still requires **bot matches** only; friendlies do not count toward the career-match gate.
- Match results are still saved in isolated `friendly_match_logs` for history.

---

## Evolution Slot Fix (legacy clubs)

Some managers who started evolutions **before the 3-slot club limit** could show **7/3 slots used** and could not start new tracks.

### What changed
- **Database cleanup** — excess active evolution tracks are auto-cancelled down to **3 per club** (keeps tracks with the most match progress, then the newest).
- **Legacy row repair** — old evolution rows get normalized so match progress (`0/3` bars) ticks correctly again.
- **Clearer hub message** — if you're still over the limit before cleanup runs, the Evolution hub explains what to do.

---

## League Points & `/leaderboard` (US-30)

Competitive points finally have a home — three clear tracks, one command.

### What's new
- **`/leaderboard`** — tabbed rankings hub:
  - **Division Rank** — weekly bot-battle ladder (promo/releg zones, division filter, pagination)
  - **Global LP** — persistent cross-server prestige rank
  - **Season** — guild fixture standings (same data as `/league hub`)
- **Weekly tier rewards** — earn **6 / 12 / 18** Division Rank pts in a week to unlock Bronze / Silver / Gold coin tiers (claim on `/leaderboard` → Division tab).
- **Clear post-match labels** — bot battles show **Division Rank** + **Global LP**; league matches show **Season Pts** and real economy v2 coins (no more misleading "+3 league pts" or hardcoded 150-coin display).
- **`/profile`** shows weekly tier progress and links to `/leaderboard`.
- **Monday reset** DMs include your final weekly rank; season end auto-distributes prizes.

### Three tracks (don't mix them up)
| Track | From | Resets |
|-------|------|--------|
| Division Rank | Bot battles | Weekly (Monday UTC) |
| Global LP | Bot battles | Never |
| Season Pts | Guild league fixtures | Per season |

---

## Audit Hardening (US-38)

Follow-up fixes from the security/economy audit — no player-facing feature changes, tighter fairness guards.

### What changed
- **Evolution POT gate** — starting or claiming an evolution now projects stat rewards against your POT ceiling (same rules as skill allocation). Partial rewards are clamped with a clear message.
- **Match XP cap race** — daily match XP per card is checked under a row lock, so concurrent matches cannot overshoot the 100 XP/day cap.
- **Economy idempotency** — duplicate coin ledger keys replay cleanly instead of erroring on retry.
- **Development hub UX** — buttons disable while a drill, evolution, skill allocation, or reward claim is processing (fewer double-click errors).
- **League economy** — re-verified with `simulate_league_economy.py`: champion gross injection **~5,480 coins**/season (additive faucet by design; no duplicate payout bug).

---

## Match Loop Hardening (US-29)

Bot and league matches use economy v2 and per-card match XP. Friendlies are a free sandbox (see US-18 above).

### What changed
- **Bot matches** cost **20** ⚡ action energy (was 10 legacy energy) and pay coins through the audited economy ledger.
- **Per-card match XP** on bot and league matches — no more flat +15 XP for everyone.
- **Friendly matches** spend no energy and grant **no coins, XP, or career record updates**.
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

*Final drill XP includes the age multiplier and Training Ground bonus (hub preview shows the total).*

**Daily caps:** 5 drills per player card, 20 drills per club (UTC day).

---

## Economy v2 (US-25)

### Match coin rewards (examples)
- **Bot:** win scales with division (base 200 × division multiplier); draw **100**; loss **50**.
- **League:** win **300–500** by server division tier; draw is one-third of win.
- **Friendly:** no coin rewards (free sandbox).

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
| `/player-profile` | Card stats, age/lifecycle phase, contract renewal, evolutions |
| `/store` | Daily login, energy refills, **Club Facilities** upgrades |
| `/development` | Stat drills (age + TG bonus), fusion, evolutions, skills, claim rewards |
| `/marketplace` | **Search Market** (regens), **Sell Player** (agent, 10/day) |
| `/club-finances` | Wallet, wage forecast, facility level summary |
| `/profile` | Club resources, records, weekly tier progress |
| `/battle how-it-works` | Match engine transparency |

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
