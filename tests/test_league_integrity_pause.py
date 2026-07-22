"""US-42.5 league integrity — pause metadata, idempotency, prize/AI guards."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUILD = ROOT / "apps" / "discord_bot" / "core" / "guild_resolver.py"
LIFECYCLE = ROOT / "apps" / "discord_bot" / "core" / "league_lifecycle_engine.py"
BATTLE = ROOT / "apps" / "discord_bot" / "cogs" / "battle_cog.py"
LEAGUE_COG = ROOT / "apps" / "discord_bot" / "cogs" / "league_cog.py"
MIG_064 = ROOT / "supabase" / "migrations" / "064_league_dynamics.sql"
APPS = ROOT / "apps" / "discord_bot"


def test_open_pauseable_statuses_include_v1():
    text = GUILD.read_text(encoding="utf-8")
    assert "OPEN_PAUSEABLE_STATUSES" in text
    for s in (
        "active",
        "registration_open",
        "registration_locked",
        "preparing",
        "registration",
    ):
        assert f'"{s}"' in text or f"'{s}'" in text


def test_pause_league_season_sets_pause_started_at():
    text = GUILD.read_text(encoding="utf-8")
    assert "async def pause_league_season" in text
    assert "pause_started_at" in text
    assert 'status": "paused"' in text or "status': 'paused'" in text or '"paused"' in text


def test_unreachable_pause_uses_shared_helper():
    text = GUILD.read_text(encoding="utf-8")
    assert "pause_league_season" in text
    # Must not status-only update without pause_started_at in the old narrow filter
    assert '.in_("status", ["active", "registration"])' not in text


def test_lifecycle_pause_delegates_to_helper():
    text = LIFECYCLE.read_text(encoding="utf-8")
    assert "pause_league_season" in text
    assert "async def pause_season" in text


def test_paused_play_copy_not_admin_resume():
    battle = BATTLE.read_text(encoding="utf-8")
    league = LEAGUE_COG.read_text(encoding="utf-8")
    assert "Wait for admin to resume" not in battle
    assert "admin resumes" not in league
    assert "paused" in battle.lower()
    assert "server is available" in battle or "windows will extend" in battle


def test_run_once_and_acquire_operation_present():
    text = LIFECYCLE.read_text(encoding="utf-8")
    assert "async def _run_once" in text
    assert "async def acquire_operation" in text
    assert "league_operation_runs" in text


def test_deadline_skips_is_played():
    text = LIFECYCLE.read_text(encoding="utf-8")
    assert "is_played" in text
    # fixture resolve early-out
    assert 'f.get("is_played")' in text or "is_played" in text


def test_prize_economy_keys_and_humans_only():
    text = MIG_064.read_text(encoding="utf-8")
    assert "season_prize:" in text
    assert "is_ai = FALSE" in text
    assert "promo_applied" in text
    assert "already_applied" in text
    assert "ON CONFLICT" in text


def test_no_player_hard_delete_on_leave_paths():
    hits: list[str] = []
    for path in APPS.rglob("*.py"):
        raw = path.read_text(encoding="utf-8", errors="ignore")
        if "table(\"players\")" in raw and ".delete()" in raw:
            # crude: same file mentions both
            if "on_member_remove" in raw or "on_guild_remove" in raw:
                hits.append(str(path.relative_to(ROOT)))
        if "DELETE FROM players" in raw or "delete from players" in raw.lower():
            hits.append(str(path.relative_to(ROOT)))
    assert hits == [], f"unexpected player delete on leave paths: {hits}"


def test_resume_requires_pause_started_at():
    text = LIFECYCLE.read_text(encoding="utf-8")
    assert "async def resume_season" in text
    assert "pause_started_at" in text
    assert "rebase_windows" in text


def test_resume_has_production_call_sites():
    """037: resume_season must be wired (hub + sweeper), not dead code."""
    lifecycle = LIFECYCLE.read_text(encoding="utf-8")
    league = LEAGUE_COG.read_text(encoding="utf-8")
    assert "async def try_resume_paused_season" in lifecycle
    assert "try_resume_paused_season" in league
    assert 'status == "paused"' in lifecycle
    assert "try_resume_paused_season(bot, db, season)" in lifecycle


def test_resume_null_pause_started_at_fail_safe():
    text = LIFECYCLE.read_text(encoding="utf-8")
    assert "missing pause_started_at" in text
    assert "clearing pause without rebase" in text
