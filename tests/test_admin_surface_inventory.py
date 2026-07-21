# tests/test_admin_surface_inventory.py
"""027: Discord admin must not expose lifecycle mutators."""
from __future__ import annotations

from pathlib import Path

ADMIN_COG = Path(__file__).resolve().parents[1] / "apps" / "discord_bot" / "cogs" / "admin_cog.py"

BANNED_CUSTOM_IDS = (
    "league_admin_open_reg",
    "league_admin_start",
    "league_admin_end",
    "league_admin_pause",
    "league_admin_sim",
    "league_admin_kick",
    "league_admin_duration",
    "league_admin_config",
    "league_admin_run_cycle",
    "league_admin_tz",
    "admin_hub_league",
)


def test_banned_lifecycle_custom_ids_absent() -> None:
    source = ADMIN_COG.read_text(encoding="utf-8")
    missing_ok = []
    for cid in BANNED_CUSTOM_IDS:
        assert cid not in source, f"banned custom_id still present: {cid}"
        missing_ok.append(cid)
    assert len(missing_ok) == len(BANNED_CUSTOM_IDS)


def test_league_time_surface_present() -> None:
    source = ADMIN_COG.read_text(encoding="utf-8")
    assert "admin_hub_server_settings" in source
    assert "admin_server_league_time" in source
    assert "LeagueTimeModal" in source
    assert "league_lifecycle_v1_enabled" not in source
