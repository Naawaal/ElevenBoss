# tests/test_settings_service.py

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

from app.services.settings_service import SettingsService
from app.models.guild_config import GuildConfig

@pytest.mark.asyncio
@patch("app.services.settings_service.get_session")
async def test_update_channels_success(mock_get_session):
    mock_session = AsyncMock()
    mock_get_session.return_value.__aenter__.return_value = mock_session
    
    # Mock update_channels database call
    with patch("app.services.settings_service.db_update_channels") as mock_db_update:
        success, msg = await SettingsService.update_channels(
            guild_id=123456,
            guild_obj=None,
            game_channel_id="111",
            matchday_channel_id="222"
        )
        assert success
        mock_db_update.assert_called_once_with(
            session=mock_session,
            guild_id=123456,
            game_channel_id="111",
            matchday_channel_id="222"
        )

@pytest.mark.asyncio
@patch("app.services.settings_service.get_session")
async def test_update_admin_role_success(mock_get_session):
    mock_session = AsyncMock()
    mock_get_session.return_value.__aenter__.return_value = mock_session
    
    with patch("app.services.settings_service.db_update_admin_role") as mock_db_update:
        success, msg = await SettingsService.update_admin_role(
            guild_id=123456,
            role_id="999"
        )
        assert success
        mock_db_update.assert_called_once_with(mock_session, 123456, "999")

@pytest.mark.asyncio
@patch("app.services.settings_service.get_session")
async def test_update_automation_settings_validation(mock_get_session):
    mock_session = AsyncMock()
    mock_get_session.return_value.__aenter__.return_value = mock_session
    
    # Invalid minimum_human_clubs (< 1)
    success, msg = await SettingsService.update_automation_settings(
        guild_id=123456,
        min_human=0
    )
    assert not success
    assert "at least 1" in msg

    # Invalid deadline (past time)
    past_time = datetime.utcnow() - timedelta(hours=1)
    success, msg = await SettingsService.update_automation_settings(
        guild_id=123456,
        deadline=past_time
    )
    assert not success
    assert "in the future" in msg

@pytest.mark.asyncio
@patch("app.services.settings_service.get_session")
async def test_update_schedule_settings_validation(mock_get_session):
    mock_session = AsyncMock()
    mock_get_session.return_value.__aenter__.return_value = mock_session
    
    # Invalid day
    success, msg = await SettingsService.update_schedule_settings(
        guild_id=123456,
        guild_obj=None,
        day="Funday"
    )
    assert not success
    assert "Invalid day" in msg

    # Invalid time
    success, msg = await SettingsService.update_schedule_settings(
        guild_id=123456,
        guild_obj=None,
        time="25:70"
    )
    assert not success
    assert "Time hours must be" in msg

    # Invalid timezone
    success, msg = await SettingsService.update_schedule_settings(
        guild_id=123456,
        guild_obj=None,
        timezone="Mars/Standard"
    )
    assert not success
    assert "Invalid timezone string" in msg
