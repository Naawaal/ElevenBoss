# tests/test_announcement_service.py

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.announcement_service import AnnouncementService
from app.models.guild_config import GuildConfig

@pytest.mark.asyncio
async def test_announcement_no_bot():
    AnnouncementService.bot = None
    res = await AnnouncementService.announce_league_start("123456", "Test League")
    assert not res

@pytest.mark.asyncio
@patch("app.services.announcement_service.get_session")
async def test_announcement_success(mock_get_session):
    # Mock database session & config
    mock_session = AsyncMock()
    mock_get_session.return_value.__aenter__.return_value = mock_session
    
    config = GuildConfig(
        guild_id="123456",
        game_channel_id="9999"
    )
    
    # Mock session query return value
    # get_or_create_guild_config logic will query guild_configs
    # To mock the repository call get_or_create_guild_config, let's patch it
    with patch("app.services.announcement_service.get_or_create_guild_config", return_value=config):
        # Mock Discord bot
        mock_bot = MagicMock()
        mock_guild = MagicMock()
        mock_channel = AsyncMock()
        
        mock_guild.get_channel.return_value = mock_channel
        mock_bot.get_guild.return_value = mock_guild
        
        AnnouncementService.bot = mock_bot
        
        res = await AnnouncementService.announce_league_start("123456", "Test League")
        assert res
        mock_channel.send.assert_called_once()
        assert "Test League" in mock_channel.send.call_args[0][0]

@pytest.mark.asyncio
@patch("app.services.announcement_service.get_session")
async def test_announcement_channel_failure(mock_get_session):
    mock_session = AsyncMock()
    mock_get_session.return_value.__aenter__.return_value = mock_session
    
    config = GuildConfig(
        guild_id="123456",
        game_channel_id="9999"
    )
    
    with patch("app.services.announcement_service.get_or_create_guild_config", return_value=config):
        mock_bot = MagicMock()
        mock_guild = MagicMock()
        mock_channel = AsyncMock()
        mock_channel.send.side_effect = Exception("Discord API error")
        
        mock_guild.get_channel.return_value = mock_channel
        mock_bot.get_guild.return_value = mock_guild
        
        AnnouncementService.bot = mock_bot
        
        res = await AnnouncementService.announce_league_start("123456", "Test League")
        # Senders must handle failures safely and return False, not raise exception
        assert not res
