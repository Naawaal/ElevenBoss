# tests/test_dm_settings_service.py

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
import discord

from app.services.dm_settings_service import DMSettingsService
from app.services.settings_service import SettingsService
from app.models.guild_config import GuildConfig

@pytest.mark.asyncio
@patch("app.services.dm_settings_service.can_manage_guild_settings")
async def test_select_guild_for_settings_flow(mock_can_manage):
    # Allowed access
    mock_can_manage.return_value = True
    res = await DMSettingsService.select_guild_for_settings(user_id=12345, guild_id=123456)
    assert res.success
    assert res.selected_guild_id == 123456

    # Denied access
    mock_can_manage.return_value = False
    res2 = await DMSettingsService.select_guild_for_settings(user_id=12345, guild_id=123456)
    assert not res2.success
    assert res2.code == "permission_denied"

@pytest.mark.asyncio
@patch("app.services.settings_service.get_session")
async def test_channels_partial_updates(mock_get_session):
    mock_session = AsyncMock()
    mock_get_session.return_value.__aenter__.return_value = mock_session
    
    with patch("app.services.settings_service.db_update_channels") as mock_db_update:
        success, msg = await SettingsService.update_channels(
            guild_id=123456,
            guild_obj=None,
            game_channel_id="888"
        )
        assert success
        mock_db_update.assert_called_once_with(
            session=mock_session,
            guild_id=123456,
            game_channel_id="888",
            matchday_channel_id=None
        )
