# tests/test_club_cog_interactions.py

import pytest
import discord
from unittest.mock import AsyncMock, patch, MagicMock
from app.cogs.club_cog import ClubCog
from app.ui.custom_ids import encode_custom_id
from app.ui.handlers.session import ui_session_manager

@pytest.mark.asyncio
@patch("app.cogs.club_cog.handle_view_table")
@patch("app.cogs.club_cog.decode_custom_id")
async def test_on_interaction_public_view_table_auto_session(mock_decode, mock_handle_view_table):
    cog = ClubCog(MagicMock())
    
    # Mock a public view table button click
    mock_interaction = AsyncMock()
    mock_interaction.type = discord.InteractionType.component
    mock_interaction.data = {"custom_id": "fcm:v1:league:view_table:main:_"}
    mock_interaction.guild_id = 777
    mock_interaction.user.id = 123
    
    # Mock CustomId decoding
    from app.ui.custom_ids import CustomId
    mock_decode.return_value = CustomId(
        namespace="fcm",
        version="v1",
        scope="league",
        action="view_table",
        target="main",
        nonce="_"
    )
    
    # Ensure no session exists initially for user 123
    ui_session_manager._sessions.clear()
    
    mock_handle_view_table.return_value = (MagicMock(), None)
    
    # Trigger on_interaction
    await cog.on_interaction(mock_interaction)
    
    # 1. Verify ephemeral deferral was called
    mock_interaction.response.defer.assert_called_once_with(ephemeral=True)
    
    # 2. Verify a session was created for user 123
    self_sessions = list(ui_session_manager._sessions.values())
    assert len(self_sessions) == 1
    session = self_sessions[0]
    assert session.discord_user_id == 123
    assert session.guild_id == 777
    
    # 3. Verify handle_view_table was called with the new session's ID
    mock_handle_view_table.assert_called_once_with(777, mock_interaction.user, session.session_id)

@pytest.mark.asyncio
@patch("app.cogs.club_cog.ScheduleSetupModal")
@patch("app.cogs.club_cog.decode_custom_id")
async def test_on_interaction_schedule_open_modal(mock_decode, mock_modal_cls):
    cog = ClubCog(MagicMock())
    
    # Mock open schedule modal click
    mock_interaction = AsyncMock()
    mock_interaction.type = discord.InteractionType.component
    mock_interaction.data = {"custom_id": "fcm:v1:schedule:open_modal:setup:nonce123"}
    mock_interaction.guild_id = 777
    mock_interaction.user.id = 123
    
    # Mock CustomId decoding
    from app.ui.custom_ids import CustomId
    mock_decode.return_value = CustomId(
        namespace="fcm",
        version="v1",
        scope="schedule",
        action="open_modal",
        target="setup",
        nonce="nonce123"
    )
    
    # Register mock session
    session = ui_session_manager.create_session(123, 777)
    session.session_id = "nonce123"
    ui_session_manager._sessions["nonce123"] = session
    
    # Trigger on_interaction
    await cog.on_interaction(mock_interaction)
    
    # 1. Verify we did not defer (defer is skipped when opening a modal)
    mock_interaction.response.defer.assert_not_called()
    
    # 2. Verify ScheduleSetupModal was constructed and sent
    mock_modal_cls.assert_called_once_with(777, "nonce123", cog.bot)
    mock_interaction.response.send_modal.assert_called_once()

@pytest.mark.asyncio
@patch("app.cogs.club_cog.CreateLeagueModal")
@patch("app.cogs.club_cog.decode_custom_id")
async def test_on_interaction_dm_admin_create_league_modal(mock_decode, mock_modal_cls):
    cog = ClubCog(MagicMock())
    
    # Mock open create league modal click
    mock_interaction = AsyncMock()
    mock_interaction.type = discord.InteractionType.component
    mock_interaction.data = {"custom_id": "fcm:v1:dm_admin:open_modal:create_league:nonce123"}
    mock_interaction.guild_id = 777
    mock_interaction.user.id = 123
    
    # Mock CustomId decoding
    from app.ui.custom_ids import CustomId
    mock_decode.return_value = CustomId(
        namespace="fcm",
        version="v1",
        scope="dm_admin",
        action="open_modal",
        target="create_league",
        nonce="nonce123"
    )
    
    # Mock permission check
    with patch("app.services.permission_service.can_run_admin_action", return_value=True):
        # Trigger on_interaction
        await cog.on_interaction(mock_interaction)
    
    # 1. Verify we did not defer (defer is skipped when opening a modal)
    mock_interaction.response.defer.assert_not_called()
    
    # 2. Verify CreateLeagueModal was constructed and sent
    mock_modal_cls.assert_called_once_with(777, "nonce123", cog.bot)
    mock_interaction.response.send_modal.assert_called_once()
