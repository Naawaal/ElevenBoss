import unittest
import asyncio
import discord
from unittest.mock import AsyncMock, patch, MagicMock

# Mock asyncio.get_running_loop() before importing any discord.ui components
mock_loop = MagicMock()
mock_loop.create_future.return_value = MagicMock()
asyncio.get_running_loop = MagicMock(return_value=mock_loop)

import pytest
import uuid
from datetime import datetime, timezone, timedelta

from app.models.club import Club
from app.models.player import Player
from app.models.guild_config import GuildConfig
from app.ui.handlers.session import ui_session_manager, UiSession
from app.services.friendly_service import FriendlyService, FriendlyMatchReport
from app.services.friendly_live_playback_service import friendly_playback_service
from app.services.lineup_service import LineupResolutionResult
from app.ui.renderers.friendly_live_renderer import FriendlyLiveRenderer
from app.ui.handlers.friendly_handler import (
    handle_friendly_challenge,
    handle_friendly_accept,
    handle_friendly_decline,
    handle_friendly_skip,
    handle_friendly_practice_select,
)
from app.ui.components import V2View


import pytest_asyncio

@pytest_asyncio.fixture(autouse=True)
async def cleanup_singleton_states():
    """
    Fixture to clean up active singleton states before and after each test case
    to prevent cross-test leakage.
    """
    ui_session_manager._sessions.clear()
    friendly_playback_service._active_playback_tasks.clear()
    yield
    ui_session_manager._sessions.clear()
    
    # Cancel any playback tasks
    for task in list(friendly_playback_service._active_playback_tasks.values()):
        if not task.done():
            task.cancel()
    friendly_playback_service._active_playback_tasks.clear()
    
    # Cancel any other pending tasks in the current loop
    try:
        loop = asyncio.get_running_loop()
        pending = asyncio.all_tasks(loop)
        for task in pending:
            if task is not asyncio.current_task(loop):
                task.cancel()
        await asyncio.sleep(0.01)
    except RuntimeError:
        pass


@pytest.mark.asyncio
@patch("app.ui.handlers.friendly_handler.get_session")
@patch("app.ui.handlers.friendly_handler.get_user_club")
@patch("app.ui.handlers.friendly_handler.LineupService.resolve_team_lineup")
@patch("app.services.friendly_service.FriendlyService.simulate_friendly")
@patch("app.services.friendly_live_playback_service.get_session")
@patch("app.services.friendly_live_playback_service.get_or_create_guild_config")
async def test_accept_starts_playback_task(
    mock_get_guild_config,
    mock_playback_get_session,
    mock_simulate,
    mock_resolve_lineup,
    mock_get_club,
    mock_get_session
):
    session_mock = AsyncMock()
    mock_get_session.return_value.__aenter__.return_value = session_mock
    mock_playback_get_session.return_value.__aenter__.return_value = session_mock
    
    guild_config = GuildConfig(guild_id="12345", supports_private_threads=True)
    mock_get_guild_config.return_value = guild_config
    
    # 1. Setup challenge session
    challenger_id = 111
    opponent_id = 222
    challenger_club_id = uuid.uuid4()
    opponent_club_id = uuid.uuid4()
    
    ui_session = ui_session_manager.create_session(
        discord_user_id=opponent_id,
        guild_id="12345",
        metadata={
            "type": "friendly_challenge",
            "status": "pending",
            "challenger_user_id": challenger_id,
            "opponent_user_id": opponent_id,
            "challenger_club_id": str(challenger_club_id),
            "opponent_club_id": str(opponent_club_id),
            "challenger_club_name": "Challenger FC",
            "opponent_club_name": "Opponent FC"
        }
    )
    nonce = ui_session.session_id
    
    mock_resolve_lineup.side_effect = [
        LineupResolutionResult(formation="4-4-2", starters=[], bench=[]),
        LineupResolutionResult(formation="4-4-2", starters=[], bench=[])
    ]
    
    report = FriendlyMatchReport(
        home_club_id=str(challenger_club_id),
        away_club_id=str(opponent_club_id),
        home_club_name="Challenger FC",
        away_club_name="Opponent FC",
        home_goals=2,
        away_goals=1,
        home_possession=55,
        away_possession=45,
        home_shots=10,
        away_shots=8,
        home_shots_on_target=5,
        away_shots_on_target=4,
        motm_player_name="Daniel Taylor",
        timeline=[
            {"minute": 15, "type": "goal", "description": "Goal scored!", "club_id": str(challenger_club_id)},
            {"minute": 50, "type": "injury", "description": "Player injured cosmetic", "club_id": str(opponent_club_id)}
        ]
    )
    mock_simulate.return_value = report
    
    club_challenger = Club(id=challenger_club_id, name="Challenger FC", guild_id="12345")
    club_opponent = Club(id=opponent_club_id, name="Opponent FC", guild_id="12345")
    
    mock_execute_res = MagicMock()
    mock_execute_res.scalar_one_or_none.side_effect = [club_challenger, club_opponent]
    session_mock.execute.return_value = mock_execute_res
    
    # Mock discord interaction and thread interfaces
    interaction = MagicMock(spec=discord.Interaction)
    interaction.guild_id = 12345
    interaction.edit_original_response = AsyncMock()
    
    mock_thread = MagicMock(spec=discord.Thread)
    mock_thread.id = 9999
    mock_thread.mention = "<#9999>"
    mock_thread.send = AsyncMock()
    mock_thread.add_user = AsyncMock()
    mock_thread.delete = AsyncMock()
    
    mock_channel = MagicMock(spec=discord.TextChannel)
    mock_channel.create_thread = AsyncMock(return_value=mock_thread)
    interaction.channel = mock_channel
    
    mock_member = MagicMock(spec=discord.Member)
    interaction.guild.get_member.return_value = mock_member
    interaction.guild.fetch_member = AsyncMock(return_value=mock_member)
    
    # Disable actual sleeps in test to run instantly
    with patch.object(friendly_playback_service, "step_delay_seconds", 0.001):
        view = await handle_friendly_accept("1", opponent_id, nonce, interaction)
        assert isinstance(view, V2View)
        assert ui_session.metadata["status"] == "playing"
        
        # Wait a tiny fraction for background task to complete all iterations
        await asyncio.sleep(0.2)
        
        # Verify it went all the way to completed
        assert ui_session.metadata["status"] == "completed"
        assert ui_session.metadata["revealed_until_minute"] == 90
        
        # Verify thread was created and participants were added
        mock_channel.create_thread.assert_called_once()
        assert mock_thread.add_user.call_count >= 1
        
        # Verify thread message edits occurred
        assert mock_thread.send.return_value.edit.call_count >= 7


@pytest.mark.asyncio
@patch("app.services.friendly_live_playback_service.get_session")
@patch("app.repositories.friendly_repository.update_breadcrumb_status")
async def test_skip_to_full_time_ends_playback(mock_update_status, mock_get_session):
    session_mock = AsyncMock()
    mock_get_session.return_value.__aenter__.return_value = session_mock
    mock_update_status.return_value = MagicMock()

    challenger_id = 111
    opponent_id = 222
    challenger_club_id = uuid.uuid4()
    opponent_club_id = uuid.uuid4()
    
    report = FriendlyMatchReport(
        home_club_id=str(challenger_club_id),
        away_club_id=str(opponent_club_id),
        home_club_name="Challenger FC",
        away_club_name="Opponent FC",
        home_goals=2,
        away_goals=1,
        home_possession=55,
        away_possession=45,
        home_shots=10,
        away_shots=8,
        home_shots_on_target=5,
        away_shots_on_target=4,
        motm_player_name="Daniel Taylor",
        timeline=[
            {"minute": 15, "type": "goal", "description": "Goal scored!", "club_id": str(challenger_club_id)}
        ]
    )
    
    ui_session = ui_session_manager.create_session(
        discord_user_id=opponent_id,
        guild_id="12345",
        metadata={
            "type": "friendly_challenge",
            "status": "playing",
            "challenger_user_id": challenger_id,
            "opponent_user_id": opponent_id,
            "challenger_club_id": str(challenger_club_id),
            "opponent_club_id": str(opponent_club_id),
            "challenger_club_name": "Challenger FC",
            "opponent_club_name": "Opponent FC",
            "report": report,
            "thread_id": 9999
        }
    )
    nonce = ui_session.session_id
    
    # Start a fake background task to mock active playback
    async def dummy_loop():
        await asyncio.sleep(10)
    task = asyncio.create_task(dummy_loop())
    friendly_playback_service._active_playback_tasks[nonce] = task
    
    interaction = MagicMock(spec=discord.Interaction)
    mock_guild = MagicMock()
    interaction.guild = mock_guild
    mock_thread = MagicMock(spec=discord.Thread)
    mock_thread.send = AsyncMock()
    mock_thread.delete = AsyncMock()
    mock_guild.get_thread.return_value = mock_thread
    mock_guild.fetch_channel = AsyncMock(return_value=mock_thread)
    
    # Non-participant clicks Skip -> raises Permission error
    with pytest.raises(ValueError, match="Only the challenger or opponent"):
        await handle_friendly_skip("1", 999, nonce, interaction)
        
    # Opponent clicks Skip -> succeeds
    view = await handle_friendly_skip("1", opponent_id, nonce, interaction)
    assert isinstance(view, V2View)
    assert ui_session.metadata["status"] == "completed"
    
    # Verify task was cancelled and registry popped
    await asyncio.sleep(0.1)
    assert task.cancelled() or task.cancelling()
    assert nonce not in friendly_playback_service._active_playback_tasks
    
    # Verify database update status was called
    mock_update_status.assert_called_once()
    args, kwargs = mock_update_status.call_args
    assert args[1] == 9999
    assert args[2] == "COMPLETED"


def test_progressive_renderer_calculations():
    challenger_club_id = uuid.uuid4()
    opponent_club_id = uuid.uuid4()
    
    report = FriendlyMatchReport(
        home_club_id=str(challenger_club_id),
        away_club_id=str(opponent_club_id),
        home_club_name="Challenger FC",
        away_club_name="Opponent FC",
        home_goals=2,
        away_goals=1,
        home_possession=55,
        away_possession=45,
        home_shots=10,
        away_shots=8,
        home_shots_on_target=5,
        away_shots_on_target=4,
        motm_player_name="Daniel Taylor",
        timeline=[
            {"minute": 0, "type": "match_start", "description": "Kickoff", "club_id": None},
            {"minute": 15, "type": "goal", "description": "Home goal", "club_id": str(challenger_club_id)},
            {"minute": 30, "type": "yellow_card", "description": "Yellow card", "club_id": str(opponent_club_id)},
            {"minute": 45, "type": "half_time", "description": "Halftime", "club_id": None},
            {"minute": 60, "type": "goal", "description": "Away goal", "club_id": str(opponent_club_id)},
            {"minute": 75, "type": "goal", "description": "Home goal 2", "club_id": str(challenger_club_id)},
        ]
    )
    
    # Score at minute 30: 1 - 0
    h, a = FriendlyLiveRenderer.get_score_at_minute(report, 30)
    assert h == 1
    assert a == 0
    
    # Score at minute 50: 1 - 0
    h, a = FriendlyLiveRenderer.get_score_at_minute(report, 50)
    assert h == 1
    assert a == 0
    
    # Score at minute 75: 2 - 1
    h, a = FriendlyLiveRenderer.get_score_at_minute(report, 75)
    assert h == 2
    assert a == 1
    
    # Render progressive events up to 45'
    events_text = FriendlyLiveRenderer.render_progressive_events(report, 45)
    assert "Home goal" in events_text
    assert "Yellow card" in events_text
    assert "Away goal" not in events_text
    
    # Render progressive stats at 45' (should be half of final)
    stats_text = FriendlyLiveRenderer.render_progressive_stats(report, 45)
    assert "Shots:** 5 vs 4" in stats_text
