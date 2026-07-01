# tests/test_guild_selection_service.py

import pytest
import discord
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.guild_selection_service import GuildSelectionService
from app.ui.handlers.dm_settings_handler import handle_open_settings_console
from app.ui.handlers.session import ui_session_manager

@pytest.mark.asyncio
@patch("app.services.guild_selection_service.get_manageable_guilds")
async def test_no_manageable_guilds(mock_get_manageable):
    mock_get_manageable.return_value = []
    
    # Testing that handle_open_settings_console raises ValueError for no guilds
    mock_user = MagicMock(spec=discord.User)
    mock_user.id = 12345
    
    with pytest.raises(ValueError) as exc:
        await handle_open_settings_console(mock_user)
    assert "do not have permission" in str(exc.value)

@pytest.mark.asyncio
@patch("app.services.guild_selection_service.get_manageable_guilds")
async def test_one_manageable_guild_skips(mock_get_manageable):
    mock_guild = MagicMock(spec=discord.Guild)
    mock_guild.id = 123456
    mock_guild.name = "NFL Server"
    mock_guild.icon = None
    mock_get_manageable.return_value = [mock_guild]

    # Mock member and permission check
    mock_member = MagicMock(spec=discord.Member)
    mock_member.guild_permissions.administrator = True
    mock_guild.get_member.return_value = mock_member
    
    mock_user = MagicMock(spec=discord.User)
    mock_user.id = 12345

    # Mock get_settings_helpers, get_session, and get_or_create_guild_config
    # to let handle_open_settings_overview succeed and return a view
    from app.models.guild_config import GuildConfig
    config = GuildConfig(guild_id="123456")
    
    with patch("app.services.permission_service.bot") as mock_bot, \
         patch("app.ui.handlers.dm_settings_handler.get_settings_helpers", return_value=("DRAFT", "Not Started")), \
         patch("app.ui.handlers.dm_settings_handler.get_session") as mock_get_sess, \
         patch("app.ui.handlers.dm_settings_handler.get_or_create_guild_config", return_value=config):
         
         mock_sess_db = AsyncMock()
         mock_get_sess.return_value.__aenter__.return_value = mock_sess_db
         mock_bot.get_guild.return_value = mock_guild
         
         view = await handle_open_settings_console(mock_user)
         assert view is not None
         # Verify that the session guild_id was automatically set to 123456 (skipped picker)
         # Find the last session created
         sessions = list(ui_session_manager._sessions.values())
         assert len(sessions) > 0
         assert sessions[-1].guild_id == 123456

@pytest.mark.asyncio
@patch("app.services.guild_selection_service.get_manageable_guilds")
async def test_multiple_manageable_guilds_shows_picker(mock_get_manageable):
    mock_guild1 = MagicMock(spec=discord.Guild)
    mock_guild1.id = 111
    mock_guild1.name = "NFL Server"
    mock_guild1.icon = None
    
    mock_guild2 = MagicMock(spec=discord.Guild)
    mock_guild2.id = 222
    mock_guild2.name = "Beta Server"
    mock_guild2.icon = None
    
    mock_get_manageable.return_value = [mock_guild1, mock_guild2]

    # Mock members
    m1 = MagicMock(spec=discord.Member)
    m1.guild_permissions.administrator = True
    mock_guild1.get_member.return_value = m1
    mock_guild1.fetch_member = AsyncMock(return_value=m1)
    
    m2 = MagicMock(spec=discord.Member)
    m2.guild_permissions.administrator = True
    mock_guild2.get_member.return_value = m2
    mock_guild2.fetch_member = AsyncMock(return_value=m2)

    # Let GuildSelectionService fetch
    views = await GuildSelectionService.get_manageable_guilds(12345)
    assert len(views) == 2
    assert views[0].guild_name == "NFL Server"
    assert views[1].guild_name == "Beta Server"
