# apps/discord_bot/core/help_catalog.py
"""In-memory help topic catalog and docs URL resolver (046-help-hub)."""
from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urljoin

DOCS_BASE = "https://share.jotbird.com/bright-serene-sandia"

REQUIRED_TOPIC_IDS: frozenset[str] = frozenset(
    {
        "getting-started",
        "battle",
        "squad",
        "training",
        "evolutions",
        "league",
        "economy",
        "hospital",
        "commands",
    }
)


@dataclass(frozen=True)
class HelpField:
    name: str
    value: str


@dataclass(frozen=True)
class HelpTopic:
    id: str
    label: str
    emoji: str
    hub_blurb: str
    title: str
    fields: tuple[HelpField, ...] = field(default_factory=tuple)
    docs_path: str | None = None
    is_commands: bool = False


def resolve_docs_url(docs_path: str | None) -> str:
    """Return absolute jotbird docs URL; empty/None → DOCS_BASE."""
    if docs_path is None:
        return DOCS_BASE
    cleaned = docs_path.strip()
    if not cleaned:
        return DOCS_BASE
    base = DOCS_BASE if DOCS_BASE.endswith("/") else DOCS_BASE + "/"
    return urljoin(base, cleaned.lstrip("/"))


def _topics() -> tuple[HelpTopic, ...]:
    return (
        HelpTopic(
            id="getting-started",
            label="Getting Started",
            emoji="🚀",
            hub_blurb="Register, first squad, and the core loop",
            title="🚀 Getting Started",
            fields=(
                HelpField(
                    "Register your club",
                    "Use **`/register`** in a server to create your club and receive a starting squad. "
                    "You need a club before most hubs (squad, battle, store) will work.",
                ),
                HelpField(
                    "Core loop",
                    "1. Spend **action energy** on matches and training\n"
                    "2. Play matches for **XP** and **coins**\n"
                    "3. Players **level up**, unlock **skill points**, and grow toward potential\n"
                    "4. Develop, rotate fitness, and climb leagues\n"
                    "Energy regenerates over time. On **`/store`**, vote on Top.gg for your free pack, "
                    "then **buy energy refills** from the same Store when you need more ⚡.",
                ),
                HelpField(
                    "Where to go next",
                    "• **`/squad`** — set your XI and formation\n"
                    "• **`/battle`** — Bot Battles & friendlies\n"
                    "• **`/development`** — drills, skills, evolutions, mentor\n"
                    "• **`/store`** — daily login & energy\n"
                    "• **`/marketplace`** — buy/sell players\n"
                    "• **`/league`** — seasonal competition",
                ),
            ),
        ),
        HelpTopic(
            id="battle",
            label="Battle & Matches",
            emoji="⚔️",
            hub_blurb="Bot Battles, friendlies, live pitch & commentary",
            title="⚔️ Battle & Matches",
            fields=(
                HelpField(
                    "Battle hub",
                    "Open **`/battle`** for the Competitive Battle Arena. "
                    "Matches use your saved starting XI and formation from **`/squad`**.",
                ),
                HelpField(
                    "Bot Battles",
                    "Challenge a bot opponent from the battle hub. Costs action energy, "
                    "pays XP/coins on settle, and applies match fatigue.",
                ),
                HelpField(
                    "Friendly Matches",
                    "Challenge another manager with **`/battle friendly`** (mention an opponent). "
                    "Great for testing squads without league stakes.",
                ),
                HelpField(
                    "Ranked",
                    "**Coming soon** — Ranked matchmaking is not live yet. "
                    "Use Bot Battles and Friendlies for now.",
                ),
                HelpField(
                    "Live pitch & commentary",
                    "During a match you get a live pitch visual and commentary updates. "
                    "Watch the thread/channel for progress, injuries, and the final scoreline.",
                ),
            ),
        ),
        HelpTopic(
            id="squad",
            label="Squad & Formation",
            emoji="📋",
            hub_blurb="XI, formation, swaps, and the pitch view",
            title="📋 Squad & Formation",
            fields=(
                HelpField(
                    "Squad hub",
                    "Use **`/squad`** to view your roster, set formation, and manage the starting XI. "
                    "Save a full valid 11 before big matches.",
                ),
                HelpField(
                    "Formation",
                    "Supported shapes include **4-4-2**, **4-3-3**, **4-2-3-1**, **3-5-2**, and **5-3-2**. "
                    "Pick the shape that fits your best GK / DEF / MID / FWD depth.",
                ),
                HelpField(
                    "Swaps & pitch visual",
                    "Swap players into slots from the hub. The pitch visual shows who is where — "
                    "off-position or empty slots can weaken match performance or block kickoff.",
                ),
            ),
        ),
        HelpTopic(
            id="training",
            label="Training & Development",
            emoji="🏋️",
            hub_blurb="Drills, skill points, and mentor transfusion",
            title="🏋️ Training & Development",
            fields=(
                HelpField(
                    "Development hub",
                    "Open **`/development`** for drills, Recover, fusion, evolutions, skill allocation, "
                    "and mentor transfer. Daily login and energy refills live on **`/store`** instead.",
                ),
                HelpField(
                    "Drills",
                    "Run training drills to grant XP and a soft-capped attribute boost (when allowed). "
                    "Drills consume energy and respect daily caps per card and club.",
                ),
                HelpField(
                    "Skill points",
                    "Level-ups grant skill points. Allocate them on attributes under **Allocate Skills** — "
                    "potential (POT) caps still apply.",
                ),
                HelpField(
                    "Mentor transfusion",
                    "Potential-maxed veterans can feed surplus skill points into youth XP "
                    "(mentor transfer). Limits apply per club/day — follow the hub prompts.",
                ),
            ),
        ),
        HelpTopic(
            id="evolutions",
            label="Evolutions",
            emoji="✨",
            hub_blurb="Active tracks, requirements, rewards, and start",
            title="✨ Evolutions",
            fields=(
                HelpField(
                    "Where to manage",
                    "Evolutions live under **`/development`**. Open the Evolutions section to see "
                    "available tracks, progress, and claimable rewards.",
                ),
                HelpField(
                    "Tracks & requirements",
                    "Each track lists requirements (matches, drills, or other goals) and rewards "
                    "(stat/XP style payoffs). Start a track from the hub when the player is eligible — "
                    "costs and progress show before you confirm.",
                ),
                HelpField(
                    "Tips",
                    "Keep the evolving player active in the relevant actions (matches/training). "
                    "Claim rewards when a stage completes; unfinished tracks stay on the hub.",
                ),
            ),
        ),
        HelpTopic(
            id="league",
            label="League System",
            emoji="🏆",
            hub_blurb="Seasons, matchdays, divisions, rewards, automation",
            title="🏆 League System",
            fields=(
                HelpField(
                    "League hub",
                    "Use **`/league`** for standings, fixtures, and season status. "
                    "Leagues run in seasons with scheduled matchdays.",
                ),
                HelpField(
                    "Registration & divisions",
                    "Join when registration is open. Clubs are placed into divisions; "
                    "results move you up or down over seasons.",
                ),
                HelpField(
                    "Matchdays & automation",
                    "Fixtures resolve on the league schedule (auto-sim can settle overdue matches). "
                    "Keep a valid XI ready before kickoff. Pause/resume rules may apply during downtime.",
                ),
                HelpField(
                    "Rewards",
                    "Season and matchday outcomes pay coins/XP through the normal economy pipes. "
                    "Check the league hub for your current season state and upcoming fixtures.",
                ),
            ),
        ),
        HelpTopic(
            id="economy",
            label="Economy & Marketplace",
            emoji="💰",
            hub_blurb="Coins, gems, store, trading, tax & discovery",
            title="💰 Economy & Marketplace",
            fields=(
                HelpField(
                    "Coins & gems",
                    "Coins fund refills, marketplace activity, and development sinks. "
                    "Gems (tokens) appear on your **`/store`** / profile balances when available.",
                ),
                HelpField(
                    "Store",
                    "**`/store`** — claim daily login, vote on Top.gg then claim your free pack, "
                    "**purchase energy refills** (same hub — after voting or anytime you’re short on ⚡), "
                    "and upgrade facilities (Youth Academy / Training Ground).",
                ),
                HelpField(
                    "Marketplace",
                    "**`/marketplace`** — Transfer Board (player-to-player listings), agent sales, "
                    "scouting, and your listings. Listing and purchase flows show tax/net where applicable.",
                ),
                HelpField(
                    "Price discovery",
                    "Listing and buy screens can show fair-value and recent-sale style cues when "
                    "enough market data exists — the bot never invents fake averages.",
                ),
            ),
        ),
        HelpTopic(
            id="hospital",
            label="Hospital & Fatigue",
            emoji="🏥",
            hub_blurb="Fatigue, injuries, recovery, hospital upgrades",
            title="🏥 Hospital & Fatigue",
            fields=(
                HelpField(
                    "Fatigue",
                    "Matches drain fitness. Low fatigue hurts performance. "
                    "Use **`/development` → Recover** for active recovery (energy cost, no drill slots). "
                    "Daily passive recovery also applies outside the hospital.",
                ),
                HelpField(
                    "Injuries & hospital",
                    "Injured players may be admitted to hospital. Recovery time depends on severity "
                    "and your Hospital facility level. Check profile / hospital UI for ETA and slots.",
                ),
                HelpField(
                    "Upgrades",
                    "Improve Hospital (and related facilities) from **`/store` → Club Facilities** "
                    "to speed recovery and expand capacity where the hub allows.",
                ),
            ),
        ),
        HelpTopic(
            id="commands",
            label="Commands",
            emoji="📜",
            hub_blurb="Live slash command reference",
            title="📜 Commands Reference",
            fields=(),
            is_commands=True,
        ),
    )


_TOPIC_BY_ID: dict[str, HelpTopic] = {t.id: t for t in _topics()}


def list_topics() -> tuple[HelpTopic, ...]:
    return _topics()


def get_topic(topic_id: str) -> HelpTopic | None:
    key = (topic_id or "").strip().lower()
    if key in _TOPIC_BY_ID:
        return _TOPIC_BY_ID[key]
    # label alias (case-insensitive)
    needle = key.replace("&", "and")
    for topic in _TOPIC_BY_ID.values():
        if topic.label.lower() == key or topic.label.lower().replace("&", "and") == needle:
            return topic
        if topic.id.replace("-", " ") == needle.replace("-", " "):
            return topic
    return None


def topic_choices_for_autocomplete(current: str) -> list[tuple[str, str]]:
    """Return (name, value) pairs for autocomplete; value is topic id."""
    cur = (current or "").strip().lower()
    out: list[tuple[str, str]] = []
    for topic in list_topics():
        label = f"{topic.emoji} {topic.label}"
        if not cur or cur in topic.id or cur in topic.label.lower() or cur in label.lower():
            out.append((label[:100], topic.id))
    return out[:25]
