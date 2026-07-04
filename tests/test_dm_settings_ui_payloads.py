# tests/test_dm_settings_ui_payloads.py

import pytest
import discord
from unittest.mock import MagicMock
from app.models.guild_config import GuildConfig
from app.ui.layouts.dm_settings import (
    build_dm_server_picker,
    build_settings_overview_layout,
    build_settings_channels_layout,
    build_settings_admin_role_layout,
    build_settings_automation_layout,
    build_settings_schedule_layout,
    build_settings_matchday_layout,
)
from app.ui.layouts.dm_admin import build_admin_dashboard_layout
from app.services.guild_selection_service import ManageableGuildView

def test_dm_server_picker_renders():
    guild_views = [
        ManageableGuildView(guild_id=111, guild_name="NFL Server", permission_label="Discord Admin"),
        ManageableGuildView(guild_id=222, guild_name="Beta Server", permission_label="ElevenBoss Admin")
    ]
    view = build_dm_server_picker(guild_views, nonce="test_nonce")
    assert view is not None
    components = view.to_components()
    assert len(components) > 0
    # Container component
    assert "Select a server" in components[0]["components"][0]["content"]

def test_settings_overview_layout_renders():
    config = GuildConfig(
        guild_id="123456",
        auto_join_draft_league=True,
        minimum_human_clubs=2,
        matchday_enabled=False
    )
    view = build_settings_overview_layout(
        config=config,
        guild_name="NFL Server",
        league_status="DRAFT",
        season_week="Not Started",
        next_run_str="Disabled",
        admin_role_name="None",
        mention_role_name="None",
        is_admin=True,
        nonce="test_nonce"
    )
    assert view is not None
    components = view.to_components()
    assert "SETTINGS — NFL SERVER" in components[0]["components"][0]["content"]

def test_settings_channels_layout_renders():
    config = GuildConfig(guild_id="123456", game_channel_id="777")
    mock_ch1 = MagicMock(spec=discord.TextChannel)
    mock_ch1.id = 777
    mock_ch1.name = "general"
    
    view = build_settings_channels_layout(
        config=config,
        guild_name="NFL Server",
        guild_channels=[mock_ch1],
        is_admin=True,
        nonce="test_nonce"
    )
    assert view is not None
    components = view.to_components()
    # Channels select menus
    assert len(components) > 0

def test_settings_admin_role_layout_renders():
    config = GuildConfig(guild_id="123456", admin_role_id="999")
    mock_role = MagicMock(spec=discord.Role)
    mock_role.id = 999
    mock_role.name = "League Admin"
    
    view = build_settings_admin_role_layout(
        config=config,
        guild_name="NFL Server",
        guild_roles=[mock_role],
        is_admin=True,
        nonce="test_nonce"
    )
    assert view is not None
    assert len(view.to_components()) > 0

def test_settings_automation_layout_renders():
    config = GuildConfig(guild_id="123456", auto_start_league=True)
    view = build_settings_automation_layout(
        config=config,
        guild_name="NFL Server",
        is_admin=True,
        nonce="test_nonce"
    )
    assert view is not None
    assert len(view.to_components()) > 0

def test_settings_schedule_layout_renders():
    config = GuildConfig(guild_id="123456", matchday_enabled=True)
    view = build_settings_schedule_layout(
        config=config,
        guild_name="NFL Server",
        next_run_str="2026-07-05 18:00 UTC",
        is_admin=True,
        nonce="test_nonce"
    )
    assert view is not None
    assert len(view.to_components()) > 0

def test_settings_matchday_layout_renders():
    config = GuildConfig(guild_id="123456")
    view = build_settings_matchday_layout(
        config=config,
        guild_name="NFL Server",
        league_status="ACTIVE",
        season_week="Season 1 / Week 2",
        fixtures_stats={"total": 28, "scheduled": 24, "played": 4},
        is_admin=True,
        nonce="test_nonce"
    )
    assert view is not None
    assert len(view.to_components()) > 0

def test_admin_dashboard_layout_renders():
    view = build_admin_dashboard_layout(
        guild_name="NFL Server",
        league_status="ACTIVE",
        season_week="Season 1 / Week 2",
        is_admin=True,
        nonce="test_nonce"
    )
    assert view is not None
    components = view.to_components()
    assert "ADMIN OVERRIDES — NFL SERVER" in components[0]["components"][0]["content"]
