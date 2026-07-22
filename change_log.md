# ElevenBoss — v2.0 Patch Notes

Hey Managers!

## Evolution claim fix

If a player finished an evolution track while still in your starting XI, **Claim** could fail with `CARD_STATE: state_conflict`. That’s fixed — you can claim the reward (stat boost / skill point) without benching them first.

---

## Training Drills — tangible attribute payoff

Skill drills still cost energy and coins and still grant **XP**, and now also attempt **+1** to the attribute you’re training (e.g. Finishing → +1 SHO):

- If the attribute is already maxed or the boost would push overall past potential, you still get the XP — you’ll just see a clear “attribute blocked” note
- Skill points are **not** spent by drills; Allocate Skills stays the way you spend SP
- Daily drill caps are unchanged (20/club, 5/card)

---

## Integrity lock (marketplace & economy)

Under the hood we finished the remaining game-integrity checklist:

- Transfer buy/sell stays **one winner** on races; you still can’t buy your own listing; busy cards stay unlistable
- Every coin faucet and sink is now on an internal registry (no shadow coin writers)
- Background jobs (payroll, listing expiry, league wake, recovery, …) are catalogued so restarts don’t double-pay

You shouldn’t notice new buttons — just fewer “paid twice / sold twice” failure modes.

---

## League pause & downtime

If the bot can’t reach your server mid-season, the league **pauses** instead of inventing forfeits:

- Remaining matchday windows **extend** when play resumes (downtime doesn’t eat your deadline)
- Play is blocked while paused — you’ll see a clear “season paused” message (not “ask an admin”)
- Season prizes and standings still settle **once** when the season ends — restarts don’t double-pay

Leaving Discord mid-season still does **not** delete your club; the assistant keeps the table going.

---

## Match integrity (settle once)

Bot and league matches now **save your result before** the Discord summary posts. If the bot restarts mid-match:

- Rewards already applied stay applied — the run is marked **complete** (not abandoned)
- Matches that never paid out are abandoned cleanly so you can play again
- League play locks **both** managers so neither can start another match at the same time

Friendly matches are unchanged (no coins/XP).

---

## Game integrity: clubs & players

Two integrity updates keep busy or quiet clubs from double-booking themselves — without wiping your progress.

### Soft club status (Inactive / Abandoned)

Your club is still yours after a long quiet spell — **nothing is deleted**, and `/register` never creates a second club.

- **Inactive** (~30 days without play) or **Abandoned** (~90 days): you can still train, recover, use the store, and manage your squad
- **New league registration** needs an **Active** club — play a match, run a drill, or claim a store bonus first, then tap **Register** again
- Double-tap Register is safe (already seated stays already seated)
- Leaving the Discord server mid-season still does **not** wipe your club

### Busy player cards

Cards now share one rulebook across Development, Marketplace, Squad, Hospital, and Academy:

- **Listed**, **Hospital**, **Evolving**, **Academy**, or **Retired** cards can’t take conflicting actions (e.g. drill / start evolution / list / XI swap while busy)
- **Match lock** still blocks roster and development changes until the match ends
- **Injured** players (even if not hospitalized) still can’t be transfer-listed or agent-sold
- Fatigue alone does **not** block listing
- Cancel listing / discharge / claim or cancel evolution still work when you’re in that busy state (unless you’re match-locked)

Stale hub buttons show clearer block reasons instead of failing silently.

---

## Evolution Start button & cost display

- **Start New Evolution** cooldown now matches the live **6-hour** rule (hub no longer used an old 10-hour clock that kept the button grey too long)
- Start cost copy shows **`25 energy + 500+5×OVR coins`** (not the outdated `10×OVR` line)
- Slot limit / readiness still come from live club config — button stays grey only when you are truly blocked (cooldown or full slots)

---

## Autonomous League Admin (League Time only)

Guild seasonal leagues run **without Discord admin babysitting**:

- Admins configure only **`/admin` → Server Settings → League Time** (IANA timezone + daily local resolution hour)
- Changes apply from the **next** season — active seasons keep frozen deadlines
- Unconfigured servers default to **UTC @ 00:00** (league still runs)
- Registration, matchdays, settlement, and promotion are handled by the internal lifecycle engine
- Emergency recovery is operator/internal only — not a Discord admin menu

---

## League Lifecycle Rulebook V1 (pilot)

Guild seasonal leagues are moving to a **21-day autonomous cycle** behind a per-server cutover flag:

- **48h registration → 24h prep → 14 daily matchdays → 24h settlement → 72h offseason**
- Your server sets an **IANA timezone + daily resolution hour**; deadlines freeze for that season and show in your local Discord time
- Miss a deadline? The **assistant manager** uses your saved lineup — only illegal squads forfeit (double illegal = 0–0, **0 points**)
- Living Dynamics/legacy seasons finish under old rules; after cutover, new seasons use the V1 rulebook only

Admins: `/admin` → **Server Settings → League Time** (IANA timezone + daily resolution hour). Lifecycle is fully autonomous — Discord admins cannot start/stop/pause/advance seasons.

---

## Free pack: Top.gg vote required

The **Vote & Claim Free Pack** button in `/store` now requires a recent **Top.gg** vote before granting your 5-card pack.

- Vote on Top.gg, then click the button again to verify and claim
- Pack cooldown is **12 hours** (was 22h) — aligned with Top.gg’s vote window
- If vote verification is temporarily unavailable, your pack is **not** claimed — try again shortly

---

## Bot match XP clarity

After a bot match, Rewards now show **match XP**:

- **`+N across XI`** when starters gained XP
- **`0 — daily cap reached (100/player)`** when your XI already hit today’s match-XP limit

Coins and LP still pay out after the cap — only card XP stops until UTC reset.

---

## Daily packs: Epic is the max

Free daily packs no longer drop **Legendary**.

- Mix: **Common ~60% · Rare ~30% · Epic ~10%** (5 cards; vote on Top.gg + 12-hour claim cooldown)
- **Legendary** cards you already own stay as-is
- Special thank-you / event Legendaries are unchanged (not from packs)

---

## Legendary thank-you gift (supporters)

Seven early supporters get a **one-time Legendary** gift for the Recover update:

- **DM** with player preview + **Claim** button (when DMs are open)
- Fallback: `/development` → **Claim Legendary Gift**
- **Legendary** · OVR **75–85** · POT **90–95** · claim once only

---

## Recover on `/development` (hub)

Fitness rest moved out of Training Drills so skill training and recovery aren’t mixed anymore.

### What changed
- New hub button: **`/development` → 💚 Recover**
- Pick **1–3** tired players, confirm the total energy cost, then restore fitness instantly
- **Training Drills** are **skill-only** again (XP + coins) — no Recovery Session option there

### Costs & results
- **`+40` fatigue** per selected player (capped at 100; config: `fatigue_recovery_session`)
- **`5⚡` action energy per player** (config: `fatigue_recovery_energy`) — so 3 players = **15⚡**
- **0 XP · 0 coins** — Recover is fitness only
- Does **not** use daily drill slots (club or per-card)

### Who you can recover
- Healthy club roster players with fatigue **below 100%**
- **Excluded:** injured, in Hospital, fully rested (100%), academy, retired, transfer-listed, or in an active evolution
- Injured players still go through **`/profile` → Manage Hospital**

### How to use it
1. `/development` → **💚 Recover**
2. Select 1–3 players (fatigue % shown)
3. Continue → check the confirm summary (names + total ⚡)
4. Confirm → fitness updates; hub refreshes

---

## Stability polish (v1 prep)

Small trust fixes while we harden the bot before calling v1.0.0 done:

- **Hospital / Academy / Transfer Board** — when there’s nothing to pick, you get clear empty text and Back/filter controls (no mystery missing dropdown).
- **Development hub** — evolutions are described as **stat boosts** (not playstyles).
- **`/profile` rankings** — clearer labels for the three ladders: **Global LP**, weekly **Division Rank** (bot), and guild **Season Pts** (`/league hub`).
- Under-the-hood: leftover debug logging removed; evolution cooldown mirror aligned with the live 6h config seed; Force End under automation schedules the next Monday registration slot (no same-day surprise reopen).

---

## League Automation (feature-flagged)

When automation is on, your server’s league runs itself — registration opens, the season starts, matchdays settle daily, then registration opens again. No more waiting on an admin to click Start every cycle.

### Status
**Off by default** (`league_automation_enabled`). Optional per-server override on `/admin`. Seasons that already started manually stay on the old flow until they finish.

### What you’ll notice when it’s on
- **Announce pings** in the league channel when registration opens, a season starts, or not enough managers signed up
- **48h registration** with a countdown on **`/league hub`** — register there like today
- Enough managers at close → season starts on **League Dynamics** pacing (midnight UTC deadlines)
- Too few managers → fail message + **fresh registration next Monday ~00:05 UTC**
- Each day after midnight, unplayed fixtures auto-sim and you get a matchday digest (Manager of the Matchday coins still pay once via the Journal)

### For admins
Set **League announce channel** + **mention role** once in `/admin`. While automation owns the guild: **Pause / Force End** stay available; Open Registration & Start Season are hidden.

---

## League Dynamics (feature-flagged)

Shorter seasons, a shared midnight UTC deadline, seasonal divisions, and a daily Manager of the Matchday shout-out — when ops flips the switch. **Existing seasons keep today’s pacing until they finish.**

### Status
**Off by default** (`league_dynamics_enabled`). While off, leagues work like they do now (rolling windows + 10-minute auto-sim). Automation (above) uses Dynamics seating/windows when it starts a season.

### When enabled (next season start)
- **14-day** seasons with **8 clubs per Seasonal Division** (bot fill keeps tables full)
- Each matchday **hard-closes at 00:00 UTC**; unplayed fixtures auto-sim shortly after (**~00:05 UTC**)
- **9+ managers** → automatic Seasonal Division 2+ (you only compete within your tier)
- Season end: **top 2 promote / bottom 2 relegate** between adjacent divisions
- **Manager of the Matchday**: biggest *manual* win that day → **+2,000 coins** (tunable) + a line in the League Journal — auto-sims don’t count

### Where to look
**`/league hub`** — deadline countdown and your **Seasonal Division** label (this is separate from Weekly Rank on your club profile)

### What stays the same
- Dual Journal + MatchDay threads
- No new slash commands — still `/league hub` to play and check the table
- Weekly Division Rank ladder (bot matches / Monday reset) is unchanged

---

## Contract & Wage System (feature-flagged)

Your Starting XI now has a real **weekly wage bill** — still forecast-only until ops flips the switch. When payroll is enabled, unpaid wages create soft pressure (debt + strikes), not club wipeouts.

### Status
**Off by default** (`wages_payroll_enabled`). While off, `/profile` → Finances keeps today’s promise: estimated XI wages are shown as ***(not auto-deducted)***.

### Where to look
**`/profile` → Finances**

| When flag is off | When flag is on |
|------------------|-----------------|
| XI wage bill + paying-player count | Same bill (what Monday will charge) |
| “Not auto-deducted” copy | Debt, strikes, last payroll, next run (**Monday 00:05 UTC**) |
| — | XI contract alerts (grace / past grace) |

### Payroll (when enabled)
- Bills **Starting XI only** (bench, academy, and reserves are not paid in v1)
- Runs every **Monday 00:05 UTC**
- Coins leave via the normal economy pipe (you’ll see the deduction on Finances)

### Can’t pay?
We never silently skip and we don’t fire-sale your stars.

1. Partial pay → remaining amount becomes **debt** and you gain a **strike**
2. Full clean pay → debt and strikes clear
3. **≥2 strikes** — friendlies blocked (league & bot still OK so you can earn)
4. **≥3 strikes** — new Transfer Board listings and youth scouting blocked (**Sell to Agent** still works)

Recover by earning coins (league/bot, daily login `/store`), shrinking an expensive XI, or clearing debt on the next paid Monday.

### Contracts that matter
- Renew still costs coins on **`/player-profile`**
- After expiry you get a **7-day grace** (playable, with a warning)
- **Past grace** — that player cannot start in the XI until you renew or replace them
- Age **≥35** renewals stay blocked (retirement path)
- **No auto-release** and **no morale hits** in this version

### Ops soft-launch
For a lighter first week, set `wages_payroll_bill_scale` to **0.5** (half bill). Default scale is **1.0**.

---

## Transfer Market — Player-to-Player Trading

You can now trade players with other managers on a global **buy-it-now** board. No auctions, no bidding wars — list a price, or buy instantly.

### Where to go
**`/marketplace`**

| Button | What it does |
|--------|----------------|
| **💰 Sell to Agent** | Instant NPC buyout (quick cash; still capped at 10/day) |
| **🔍 Search Market** | **Regen Scouting** (system prospects) **or** **Transfer Board** (other clubs’ players) |
| **📋 My Listings** | List / cancel your own players for human buyers |

### Selling on the Transfer Board
1. **My Listings → List Player**
2. Choose a healthy **reserve** (not in XI, not training/evolving, not injured or in academy)
3. Set a coin price inside the shown fair-value range (about **0.75×–2.5×** agent value)
4. Confirm — up to **5** active listings at once

If nobody buys within **72 hours**, the listing expires and the card returns to you. Cancel anytime before it sells.

### Buying
1. **Search Market → Transfer Board**
2. Filter by **position** and preset **OVR / age / potential** bands → **Apply**
3. Select a player → **Buy Now** → confirm

You pay the **full** listed price. You can’t buy your own listing. If someone else gets there first, you’ll see a clear “already sold” message and keep your coins.

### Tax
On every completed player-to-player sale:
- **Seller receives 90%** of the listed price  
- **10% market tax** is removed from the economy  

Example: list at **10,000** → buyer pays **10,000**, seller gets **9,000**.

### Still available
- **Sell to Agent** — fast liquidation when the board is quiet  
- **Regen Scouting** — sign retirement regens (system listings, not other managers)

---

## League Intensity — Fatigue & Hospital Rebalance

Match fitness and injuries now scale with your **Division Rank** (updated Mondays with promotions/relegations).

| Intensity | Divisions | Match drain feel | Daily recovery | Hospital (Moderate base) |
|-----------|-----------|------------------|----------------|--------------------------|
| **Low** | Grassroots, Amateur | Light | Strong (+35 base + TG) | Shorter clocks |
| **Medium** | Semi-Pro, Professional | Rotation starts to matter | Mid | Mid |
| **High** | Elite, Legendary | Deep squad demanded | Tighter | Longer — Hospital upgrades shine |

Check **`/store` → Club Facilities → Hospital** for your intensity header, and injured players on **`/profile`** for return-date math (base vs facility bonus). Competitive match tickets warn if starters are under **30%** fatigue.

**Migration fairness:** Open hospital stays were recalculated (never made longer). Uninjured squads got a one-time fatigue floor of **50** so you can feel the new drain curve immediately.

Soft-lock “emergency fillers” are **not** in this patch — we’re monitoring whether they’re still needed after the forgiving lower tiers.

---

## Youth Academy — Manage Academy

Youth prospects now train in the academy before they join your senior club. Upgrade YA still matters — and you finally have a place to *run* it.

### Where to go
**`/profile` → Manage Academy** — slots, prospect list, Ready badges, next free intake, promote / release / scout. Upgrade YA level still lives under **`/store` → Club Facilities**. No new slash command.

### Holding phase
- **Monday intake** (00:00 UTC) seats into free academy slots — **not** your starting XI.
- Slots by YA level: **L1 = 4 · L2 = 5 · L3 = 6 · L4 = 8 · L5 = 10**.
- Academy full? Free seats still fill; the rest are **skipped** (you’ll see how many). No replace prompt.
- **Daily growth** while seated (faster / higher ceilings at higher YA). **Ready** guideline at **65 OVR** — you can promote earlier.
- **Promote** moves them to the senior club (soft cap **48** seniors). **Release** frees a slot (they leave the club).
- Age **20** without promote → auto-promote if there’s senior space, otherwise released (DM when possible).

### Paid scouting (optional)
Supplement Monday intake — shortlist of **3**, sign **up to 1** into a free academy slot.

| Tier | Cost | Wait |
|------|------|------|
| Quick | 3,000 | 2h |
| Standard | 10,000 | 8h |
| Deep | 25,000 | 24h |

Finish one report (or let it expire) before dispatching another. Scout-ready DMs when enabled; otherwise check Manage Academy.

### What stays out of academy
Academy prospects can’t go into `/squad`, marketplace sell lists, or `/development` drills / fusion / skill allocation until promoted.

### Already had youth on the roster?
Cards from before this update stay **senior** (grandfathered). Only **new** intake and scout signings use the holding phase.

---

## Bench rest reliability

After **bot** and **league** matches, unused healthy reserves get **+25** fitness (cap 100). Post-match press conference now shows a **Fitness** line when rest ran (or if the fitness update failed — rewards still count and fatigue can retry).

Highest-overall unused players rest first (up to **7**). Friendlies stay a sandbox (no fatigue).

## Hub cleanup & energy tweaks

**Recovery Session** now costs **5⚡** (was 10) — still 0 coins / 0 XP / +40 fatigue.

**Action energy max** is **120** (was 100). Regen rate is unchanged; you can just bank more.

**Hospital** moves fully under **`/profile` → Manage Hospital**. **Manage Academy** is also on **`/profile`**. Store → Club Facilities is YA + Training Ground upgrades only.

**`/club-finances`** is removed. Use **`/profile` → Finances** for wallet, wages, and facility summary.

## Training Drills limit clarity

- Hitting a **single player’s** daily drill/recovery cap (**5**) now shows the correct per-card message — not the club-wide “20” message.
- Daily Drills `used/20` on the Training hub follows the same **UTC day** reset as the server (no leftover yesterday count).
- Stuck club counters were reconciled against today’s real drill log.

## Recovery QoL (injury & fitness clocks)

Injuries and fatigue recover on a Discord-friendly real-time clock.

**Injuries (new clocks)**
- Untreated bases: **Minor 1 day**, **Moderate 4 days**, **Major 7 days** (was 3 / 8 / 20).
- Hospital still shortens those windows the same way — upgrades matter more when Majors aren’t three weeks long.

**Already injured when this shipped?**
- Open Hospital stays and untreated injuries were **recalculated fairly**: time you’d already waited counts toward the new clock.
- ETAs only got **shorter or stayed the same** — never longer.
- If you’d already served past the new maximum, that player was **discharged / cleared** early. Check **`/profile` → Manage Hospital**.

**Fitness**
- Daily passive (healthy players): **+25 + (TG level × 5)** — TG1 = +30, TG3 = +40, TG5 = +50 (was base +15).
- Bench rest after competitive matches: **+25** (was +15).
- Match fatigue base drain: **18** (was 22); PHY / tactics / intensity still apply.
- Recovery Session (+40 / **5⚡**) is unchanged.

## Active Fatigue Recovery

Fitness management is no longer “bench them or wait five days.”

**Recovery Session** (`/development` → Training Drills)
- Pick a tired player, choose **💚 Recovery Session** instead of a skill drill, and confirm.
- Restores **+40 fatigue** (capped at 100), grants **0 XP**, costs **0 coins**, and uses **5⚡** plus one daily drill slot.
- Injured players still go to **Hospital** — Recovery is for fatigue only.
- Fully rested players (100%) cannot start a Recovery Session.

**Training Ground passive**
- Daily fatigue recovery scales with your Training Ground: **+25 + (TG level × 5)** per day for healthy players (TG1 = +30; TG5 = +50).
- Hospital patients still use the hospital daily rate. Bench rest after competitive matches is **+25**.

## Retirement lifecycle fixes

Aging, retirement, and the scouting regen market got three balance/UX fixes so late careers and legend reincarnations feel fair.

**Aging curve**
- From **age 33+**, veterans also lose **DRI** (alongside the existing pace / physique / passing / defending drops).
- From **age 35+**, **SHO** declines too — no more immortal finishers who only got slower.
- Retirement age is unchanged (**36**); the curve just makes that exit feel earned.

**Squad holes**
- When a **starter** retires, an eligible **reserve** (same position role, not already in your XI) is **auto-promoted** into that slot.
- If nobody can cover the hole, your club is flagged invalid: **bot, league, and friendly** matches won’t start until you fix the lineup in **`/squad`**.
- `/squad` shows a clear warning when you’re in that state; saving a full valid XI clears it.

**Regen rarity (scouting pool)**
- Retired **85+ OVR** legends spawn **Epic or Rare** only (**50/50**) — never Common.
- **80–84** → **60% Rare / 40% Common**
- **75–79** → **80% Common / 20% Rare**
- Same market entry as before (OVR 75+ retirees, ages 16–19); only the rarity odds changed.

## Mentor Transfusion

Your legends finally have a late-game purpose. When a card hits its **potential ceiling**, surplus skill points aren't stuck anymore — you can **hand the torch** to the next generation.

**How it works**
- Open **`/development` → Allocate Skills** on a potential-maxed card with at least **5 SP**.
- Tap **Mentor Transfer**, pick a developing club mate (any position), choose **1 / 3 / 5 / Max** mentor units, and confirm the level-up preview.
- Conversion: **5 SP → 1 mentor unit (MP) → 500 XP** on the target. Leftover SP under 5 stays on the mentor.
- Cap: **3 mentor transfers per club per UTC day** (separate from fusion and skill-allocate limits).

**What you’ll notice**
- Maxed cards show **Mentor Ready** on Allocate Skills and on **`/player-profile`** (SP → MP / XP conversion).
- Youth still hit the same potential ceiling; mentoring speeds **leveling**, not how many SP you can spend on stats per day.
- Injury / fatigue does **not** block mentoring. Coins, energy, match XP rates, and marketplace prices are unchanged.

## Pack identities (Archetypes)

New cards from **`/store` packs**, registration, youth intake, and the scouting pool now roll a **playing style** — not just a position and OVR. Same rarity odds as before; the cards just feel less identical.

**Forward styles**
- **Poacher** — clinical finishing / physical presence  
- **Speedster** — pace and dribbling  
- **Complete Forward** — balanced attacker  

**Mid / Def / GK** also roll distinct styles (e.g. Playmaker, Destroyer, Box-to-Box · Stopper, Wing-Back, Ball-Playing Defender · Shot Stopper, Sweeper Keeper, Classic Keeper).

**What you’ll notice**
- Style shows as **Role** on pack reveals, onboarding, youth intake, and squad / player profile (same Role Style line you already know).
- The **OVR on the card matches True OVR** at creation — no more “looks like a 75, plays like a 72.”
- Daily pack mix (historical note; superseded — see top of changelog): was Common 60% · Rare 30% · Epic 8% · Legendary 2%.
- Cards you already owned keep their old Role — only **new** drops get the new styles.

## Live Match Immersion

Watching a match should feel like a match — not a scoreboard that jumped while you blinked.

Applies to **bot**, **league**, and **friendly** live streams:

- **Goal Scroll** sits under the scoreboard and lists every goal (minute + scorer), even after the 5-line commentary ticker has moved on (up to 10 goals shown).
- **Half-time** inserts a clear `--- HALF TIME ---` break in the ticker at 45'.
- **Bot / AI opponents** field a full named XI — no more “Opponent Striker” or “Opponent Midfielder”.
- **Possession & shots** stay believable when you’re outmatched (no more lifeless 0%–100% / 0-shot snowballs).

## Club Profile hub

Your club’s wallet and medical bay live on **`/profile`** now — one glance, then act.

- **Club Finance** — coins and gems at the top of the embed.
- **Hospital** — level, beds in use, recovery speed, and who’s recovering (or a clear “No Hospital / No injuries” empty state).
- **Buttons under the embed:**
  - **Manage Hospital** — upgrade, admit, or discharge (Back returns to your refreshed profile).
  - **Finances** — wage forecast + YA / Training Ground / Hospital levels.
  - **View Club Stats** — jumps to your Squad hub.
- Hospital is **Profile-only** (not under Store → Club Facilities).
- Finances live on **`/profile`** (the old `/club-finances` command is removed).

## Fatigue, Injuries & Hospital

Squad depth matters now. Push the same XI every day and they’ll tire, risk injury, and need Hospital beds — or rotation.

### Fatigue
- **Per-player fitness (0–100)** on every card — not the same as club **action energy**.
- **Starters** lose fatigue after **bot** and **league** matches (base drain **18**; PHY, tactics stance, and tough opponents still modify it).
- **Bench** players who sat a competitive match recover **+25** fitness (capped at 100).
- **Tired players perform worse** in live matches (soft → hard penalties as fatigue drops).
- **Daily recovery** for healthy players: **+25 + (Training Ground level × 5)** (TG1 = +30 … TG5 = +50). Hospital patients use the faster hospital daily rate.
- **Recovery Session** under `/development` → Training Drills restores **+40** for **5⚡** (0 XP / 0 coins; uses a drill slot).
- See fitness on **`/squad`** and **`/player-profile`**.

### Injuries
- Only players below **75% fatigue** can be injured, and **at most one** injury per club per match.
- Tiers: **Minor / Moderate / Major** (no career-ending auto-retire) — untreated clocks **1 / 4 / 7** real days; Hospital shortens further.
- Injured players are blocked from the **starting XI**, **stat drills**, **fusion**, **evolution start**, and **agent sale** until cleared.
- Expected return shows on profile and the Hospital panel.

### In-match stoppages (live matches)
- When an injury hits **before 90'** in a **live bot or league** match, play pauses at a natural stoppage.
- You get **30 seconds** to **pick a bench substitute** or **Play On** (weaker on the pitch; higher chance the injury worsens).
- **Timeout** auto-picks the best available bench player (or continues with **10 men** if nobody’s left).
- **Max 3 subs** per match; **GK** injuries prefer a bench GK, otherwise an emergency outfield keeper.
- **League auto-sim** and **AI clubs** resolve without a Discord prompt.
- **90'+** injuries are recorded for after the match — no mid-match prompt.

### Hospital (Club Facility)
- New facility under **`/profile` → Manage Hospital** (beds / recovery speed). Youth Academy & Training Ground remain under **`/store` → Club Facilities**.
- **Beds** = Hospital level + 1 (level 0 still has **1** first-aid bed).
- Higher levels = **more beds** and **faster recovery**.
- Post-match injuries **auto-admit** when a bed is free; if full, you get a **DM or Hospital panel** choice (never silent).
- **Upgrade costs (coins):** 1,500 / 4,000 / 10,000 / 25,000 / 60,000.
- Shares the **one facility upgrade per UTC week** slot with YA/TG.
- **L2** needs **5** career matches; **L4** needs **20** (same spirit as other facilities).
- No per-treatment coin fee — the upgrade ladder is the sink.

### Unchanged on purpose
- **Friendlies** stay a sandbox — no fatigue drain, no injuries, no Hospital admits.
- Club **action energy** / refill shop behavior is unchanged by fatigue recovery.

### For server operators
- Migration **050** (`fatigue_injury_hospital`) must be applied before deploying this bot build.
- Daily recovery job runs with the bot scheduler (~**00:05 UTC**).

---

## Match XP + Energy Regen Fix

### What changed
- **Match XP restored** for bot and league matches (XP pipe hardened after ledger security changes).
- **Faster energy regen** — **+1 action energy every 4 minutes** (~8h empty→full at 120 max). Hubs and insufficient-energy messages match this rate.
- Friendlies still grant **no XP** and spend **no energy**.

---

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
- **XP logging fix (migration 048)** — `apply_card_xp` runs as `SECURITY DEFINER` so XP grants work after ledger hardening (fixes `permission denied for table player_xp_log`).
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

Every week brings fresh prospects — rebuild without relying only on daily packs.

### What changed
- **3 youth prospects** (default) arrive each **Monday 00:00 UTC** for every manager (ages 16–19).
- **L1 Youth Academy baseline:** OVR 50–65, POT 72–82.
- **Higher Youth Academy levels** (`/store` → Club Facilities) raise intake OVR/POT ceilings and add a small **gem prospect** chance from L2 upward.
- New intake seats into **Manage Academy** (holding phase) — **not** auto-assigned to your starting XI. See **Youth Academy — Manage Academy** at the top of this changelog.
- You'll get a **DM** listing seated prospects when DMs are enabled.

---

## Club Facilities (US-33 — Phase C)

Invest coins to improve your academy and training ground over time. **Hospital** is a third facility — see **Fatigue, Injuries & Hospital** above.

### What changed
- **`/store` → Club Facilities** — upgrade **Youth Academy** / **Training Ground**. Open **`/profile` → Manage Academy** for seating, growth, promote/release, and paid scouting.
- **Youth Academy:** L1 is the baseline band above; higher levels widen OVR/POT ceilings up to roughly **56–69 OVR / 72–94 POT** at L5, with rising gem-prospect odds, more slots, and faster academy growth.
- **Training Ground:** **L1 +0 … L5 +4** flat bonus drill XP (shown on the Stat Drills hub).
- **Costs (YA/TG):** 750 / 2,000 / 5,000 / 12,000 coins per level (same all divisions). Hospital uses its own ladder (see above).
- **Level 1 is free** for YA/TG — upgrades are optional; max **1 upgrade per UTC week** across YA + TG + Hospital.
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

- **One pool:** `Action Energy` (max **120**) replaces separate match and training energy.
- **Regen:** **+1 energy every 4 minutes** (~6h 40m empty→full; synced when you open hubs or run actions).
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
| `/profile` | Club finance, Hospital, resources, records |
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
