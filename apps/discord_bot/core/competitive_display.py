# apps/discord_bot/core/competitive_display.py
"""Post-match and profile competitive point display helpers (US-30)."""
from __future__ import annotations

from leagues import tier_progress_label, weekly_reset_countdown


def resolve_global_tier(global_lp: int, divisions: list[dict]) -> tuple[str, dict | None, dict | None]:
    """Return (current_name, current_div, next_div) from sorted global_divisions rows."""
    current = None
    next_div = None
    for idx, div in enumerate(divisions):
        if global_lp >= div.get("min_lp", 0):
            current = div
            next_div = divisions[idx + 1] if idx + 1 < len(divisions) else None
    if not current:
        current = {"name": "Bronze III", "min_lp": 0}
        next_div = divisions[1] if len(divisions) > 1 else None
    return current["name"], current, next_div


def global_lp_progress_snippet(global_lp: int, divisions: list[dict]) -> str:
    """One-line LP progress for post-match embed."""
    name, current, next_div = resolve_global_tier(global_lp, divisions)
    if not next_div:
        return f"**{global_lp} LP** ({name})"
    min_lp = current.get("min_lp", 0)
    max_lp = next_div.get("min_lp", 0)
    return f"**{global_lp}/{max_lp} LP** to {next_div['name']}"


def format_bot_rewards_block(
    *,
    coins: int,
    div_pts_earned: int,
    weekly_total: int,
    lp_delta: int,
    new_lp: int,
    divisions: list[dict],
) -> str:
    lines = [f"🪙 **+{coins} coins**"]
    if div_pts_earned > 0:
        lines.append(f"📊 **+{div_pts_earned} Division Rank** ({tier_progress_label(weekly_total)})")
    elif div_pts_earned == 0 and weekly_total > 0:
        lines.append(f"📊 Division Rank: {tier_progress_label(weekly_total)}")
    sign = "+" if lp_delta >= 0 else ""
    lp_snip = global_lp_progress_snippet(new_lp, divisions)
    lines.append(f"🌍 **{sign}{lp_delta} LP** → {lp_snip}")
    return "\n".join(lines)


def format_season_reward_line(club_name: str, coins: int, season_pts: int, prefix: str = "") -> str:
    pts_label = "Season Pt" if season_pts == 1 else "Season Pts"
    return f"{prefix}**{club_name}**: `🪙 +{coins} coins`, `📊 +{season_pts} {pts_label}`"


def profile_leaderboard_hint() -> str:
    return "Use `/leaderboard` for full rankings. Division Rank resets " + weekly_reset_countdown() + "."


def league_standings_leaderboard_hint() -> str:
    return (
        "These Pts = **Season Pts** (guild fixtures). "
        "Weekly **Division Rank** & **Global LP** are separate — `/leaderboard`."
    )
