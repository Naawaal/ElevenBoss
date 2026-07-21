# packages/leagues/leagues/standings.py
"""Pure standings helpers for guild seasonal leagues (US-26)."""
from __future__ import annotations

from typing import Any


def result_char(
    home_id: int,
    away_id: int,
    team_id: int,
    home_score: int,
    away_score: int,
    *,
    result_type: str | None = None,
) -> str:
    # Double forfeit is a loss for both — never a draw in form strings.
    if result_type == "double_forfeit":
        return "L"
    if home_score == away_score:
        return "D"
    if team_id == home_id:
        return "W" if home_score > away_score else "L"
    return "W" if away_score > home_score else "L"


def apply_fixture_to_row(row: dict[str, Any], fixture: dict[str, Any], team_id: int) -> None:
    """Mutate a standings row for one played fixture (supports double_forfeit)."""
    result_type = fixture.get("result_type")
    hs = int(fixture.get("home_score") or 0)
    aws = int(fixture.get("away_score") or 0)
    is_home = team_id == fixture["home_team_id"]
    row["matches_played"] = int(row.get("matches_played") or 0) + 1

    if result_type == "double_forfeit":
        row["lost"] = int(row.get("lost") or 0) + 1
        # GF/GA/GD unchanged; points unchanged
        return

    gf = hs if is_home else aws
    ga = aws if is_home else hs
    row["goals_for"] = int(row.get("goals_for") or 0) + gf
    row["goals_against"] = int(row.get("goals_against") or 0) + ga
    row["goal_difference"] = row["goals_for"] - row["goals_against"]
    if gf > ga:
        row["won"] = int(row.get("won") or 0) + 1
        row["points"] = int(row.get("points") or 0) + 3
    elif gf == ga:
        row["drawn"] = int(row.get("drawn") or 0) + 1
        row["points"] = int(row.get("points") or 0) + 1
    else:
        row["lost"] = int(row.get("lost") or 0) + 1


def compute_form(team_id: int, fixtures: list[dict], limit: int = 5) -> str:
    """Last N results as W/D/L string (most recent last)."""
    played = [
        f for f in fixtures
        if f.get("is_played") and team_id in (f["home_team_id"], f["away_team_id"])
    ]
    played.sort(key=lambda f: (f.get("matchday") or 0, f.get("played_at") or ""))
    chars = []
    for f in played[-limit:]:
        chars.append(
            result_char(
                f["home_team_id"], f["away_team_id"], team_id,
                f["home_score"], f["away_score"],
                result_type=f.get("result_type"),
            )
        )
    return "".join(chars) if chars else "—"


def head_to_head_points(team_a: int, team_b: int, fixtures: list[dict]) -> tuple[int, int]:
    """Mini-league points between two tied teams from played H2H fixtures."""
    pts_a = pts_b = 0
    for f in fixtures:
        if not f.get("is_played"):
            continue
        if f.get("result_type") == "double_forfeit":
            # Both lost — no H2H points either side
            continue
        h, a = f["home_team_id"], f["away_team_id"]
        if {h, a} != {team_a, team_b}:
            continue
        hs, as_ = f["home_score"], f["away_score"]
        if hs == as_:
            pts_a += 1
            pts_b += 1
        elif (hs > as_ and h == team_a) or (as_ > hs and a == team_a):
            pts_a += 3
        else:
            pts_b += 3
    return pts_a, pts_b


def sort_standings(rows: list[dict], fixtures: list[dict] | None = None) -> list[dict]:
    """Sort by Pts → GD → GF → H2H (if fixtures provided)."""
    fixtures = fixtures or []

    def sort_key(row: dict) -> tuple:
        h2h_bonus = 0
        if fixtures:
            tied = [
                r for r in rows
                if r["points"] == row["points"]
                and r["goal_difference"] == row["goal_difference"]
                and r["goals_for"] == row["goals_for"]
                and r["discord_id"] != row["discord_id"]
            ]
            for other in tied:
                pa, pb = head_to_head_points(row["discord_id"], other["discord_id"], fixtures)
                if pa > pb:
                    h2h_bonus += 1
        return (
            row["points"],
            row["goal_difference"],
            row["goals_for"],
            h2h_bonus,
            -row["discord_id"],
        )

    return sorted(rows, key=sort_key, reverse=True)


def format_standings_table(rows: list[dict], fixtures: list[dict] | None = None, limit: int | None = None) -> str:
    """ASCII league table with form column."""
    fixtures = fixtures or []
    ordered = sort_standings(rows, fixtures)
    if limit:
        ordered = ordered[:limit]
    lines = ["Pos  Club                  Pld  Pts  GD  Form"]
    lines.append("-" * 48)
    for idx, row in enumerate(ordered, 1):
        club = row.get("club_name", "?")
        if row.get("is_ai"):
            club += " (AI)"
        if not row.get("is_active", True):
            club += " 💤"
        club = (club[:17] + "...") if len(club) > 20 else club
        form = compute_form(row["discord_id"], fixtures)
        lines.append(
            f"{idx:<4} {club:<20} {row.get('matches_played', 0):>3}  "
            f"{row['points']:>3}  {row['goal_difference']:+3}  {form}"
        )
    return "\n".join(lines)


def tie_breaker_footer() -> str:
    return "Tie-break: Pts → GD → GF → H2H → fair play"
