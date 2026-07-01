# tests/test_automation_ui_payloads.py

import pytest
from app.models.guild_config import GuildConfig
from app.ui.layouts.setup import build_setup_layout
from app.ui.layouts.schedule import build_schedule_layout
from app.ui.layouts.automation import build_automation_layout

def test_setup_layout_renders():
    config = GuildConfig(
        guild_id="123456",
        auto_join_draft_league=True,
        auto_start_league=False,
        minimum_human_clubs=2,
        auto_fill_with_bot_clubs=True,
        matchday_enabled=False
    )
    
    view = build_setup_layout(config, is_admin=True, nonce="test_nonce")
    assert view is not None
    components = view.to_components()
    assert len(components) > 0
    
    container_comp = components[0]
    assert container_comp["type"] == 17  # Container
    text_display = container_comp["components"][0]
    assert text_display["type"] == 10  # TextDisplay
    assert "ELEVENBOSS" in text_display["content"]

def test_schedule_layout_renders():
    config = GuildConfig(
        guild_id="123456",
        matchday_enabled=True,
        matchday_day="Sunday",
        matchday_time="18:00",
        matchday_timezone="Asia/Kathmandu",
        game_channel_id="999"
    )
    
    view = build_schedule_layout(config, is_admin=True, nonce="test_nonce")
    assert view is not None
    components = view.to_components()
    assert len(components) > 0
    
    container_comp = components[0]
    text_display = container_comp["components"][0]
    assert "AUTOMATION SCHEDULE" in text_display["content"]

def test_automation_layout_renders():
    config = GuildConfig(
        guild_id="123456",
        automation_status="idle",
        last_automation_status="success"
    )
    
    view = build_automation_layout(
        config=config,
        league_status="ACTIVE",
        season_week="Season 1 / Week 2",
        next_run_str="2026-07-05 18:00 Local",
        is_admin=True,
        nonce="test_nonce"
    )
    
    assert view is not None
    components = view.to_components()
    assert len(components) > 0
    
    container_comp = components[0]
    text_display = container_comp["components"][0]
    assert "SYSTEM AUTOMATION STATUS" in text_display["content"]
    assert "ACTIVE" in text_display["content"]
    assert "Week 2" in text_display["content"]
