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
from app.models.lineup import Lineup
from app.models.guild_config import GuildConfig
from app.ui.handlers.session import ui_session_manager, UiSession
from app.services.friendly_service import FriendlyService, FriendlyMatchReport
from app.services.friendly_live_playback_service import friendly_playback_service
from app.ui.handlers.friendly_handler import (
    handle_friendly_challenge,
    handle_friendly_accept,
    handle_friendly_decline,
    handle_friendly_practice,
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
    
    original_sleep = asyncio.sleep
    async def mock_sleep(seconds, *args, **kwargs):
        if seconds == 120:
            await original_sleep(0)
        else:
            await original_sleep(seconds)
            
    with patch("app.services.friendly_live_playback_service.asyncio.sleep", mock_sleep):
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
async def test_challenge_rejected_no_club(mock_get_club, mock_get_session):
    session_mock = AsyncMock()
    mock_get_session.return_value.__aenter__.return_value = session_mock
    
    challenger = MagicMock(spec=discord.Member, id=111, display_name="Challenger")
    opponent = MagicMock(spec=discord.Member, id=222, display_name="Opponent", bot=False)
    
    # Challenger has no club
    mock_get_club.side_effect = [None, None]
    
    with pytest.raises(ValueError, match="register a club first"):
        await handle_friendly_challenge("12345", challenger, opponent)

    # Opponent has no club
    club_challenger = Club(id=uuid.uuid4(), name="Challenger FC", guild_id="12345")
    mock_get_club.side_effect = [club_challenger, None]
    
    with pytest.raises(ValueError, match="does not have a registered club"):
        await handle_friendly_challenge("12345", challenger, opponent)


@pytest.mark.asyncio
async def test_challenge_rejected_against_self():
    challenger = MagicMock(spec=discord.Member, id=111)
    opponent = MagicMock(spec=discord.Member, id=111)
    
    with pytest.raises(ValueError, match="cannot challenge yourself"):
        await handle_friendly_challenge("12345", challenger, opponent)


@pytest.mark.asyncio
@patch("app.ui.handlers.friendly_handler.get_session")
@patch("app.ui.handlers.friendly_handler.get_user_club")
async def test_challenge_cooldown_and_anti_spam(mock_get_club, mock_get_session):
    session_mock = AsyncMock()
    mock_get_session.return_value.__aenter__.return_value = session_mock
    
    challenger = MagicMock(spec=discord.Member, id=111, display_name="Challenger")
    opponent = MagicMock(spec=discord.Member, id=222, display_name="Opponent", bot=False)
    
    club_challenger = Club(id=uuid.uuid4(), name="Challenger FC", guild_id="12345")
    club_opponent = Club(id=uuid.uuid4(), name="Opponent FC", guild_id="12345")
    mock_get_club.side_effect = [club_challenger, club_opponent, club_challenger, club_opponent]
    
    # First challenge succeeds
    view = await handle_friendly_challenge("12345", challenger, opponent)
    assert isinstance(view, V2View)
    
    # Second challenge immediately gets blocked by cooldown
    with pytest.raises(ValueError, match="challenge cooldown"):
        await handle_friendly_challenge("12345", challenger, opponent)
        
    # Reset cooldown for subsequent tests
    from app.services.friendly_service import _friendly_cooldowns
    _friendly_cooldowns.clear()


@pytest.mark.asyncio
@patch("app.ui.handlers.friendly_handler.get_session")
@patch("app.ui.handlers.friendly_handler.get_user_club")
@patch("app.ui.handlers.friendly_handler.FriendlyService.resolve_team_lineup")
@patch("app.services.friendly_service.FriendlyService.simulate_friendly")
@patch("app.services.friendly_live_playback_service.get_session")
@patch("app.services.friendly_live_playback_service.get_or_create_guild_config")
async def test_challenge_accept_workflow(
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
    
    # Setup challenge session
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
    
    # Mock resolved lineups
    from app.engine.match_engine import MatchPlayerInput
    dummy_starters = [
        MatchPlayerInput(
            player_id=str(uuid.uuid4()),
            name=f"Player {i}",
            position="GK" if i == 0 else "CB" if i < 4 else "CM" if i < 8 else "ST",
            slot="GK" if i == 0 else f"CB{i}" if i < 4 else f"CM{i}" if i < 8 else f"ST{i}",
            overall=70,
            potential=75,
            fitness=100,
            morale=80,
            consistency=70,
            is_goalkeeper=(i == 0)
        )
        for i in range(11)
    ]
    mock_resolve_lineup.side_effect = [
        ("4-4-2", dummy_starters),  # Challenger XI
        ("4-4-2", dummy_starters)   # Opponent XI
    ]
    
    # Mock simulate result DTO
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
    mock_simulate.return_value = report
    
    # Simulate database executes for club load
    club_challenger = Club(id=challenger_club_id, name="Challenger FC", guild_id="12345")
    club_opponent = Club(id=opponent_club_id, name="Opponent FC", guild_id="12345")
    
    mock_execute_res = MagicMock()
    mock_execute_res.scalar_one_or_none.side_effect = [club_challenger, club_opponent]
    session_mock.execute.return_value = mock_execute_res
    
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
    
    # Non-opponent accepts challenge -> raises ownership error
    with pytest.raises(ValueError, match="Only the challenged manager can accept/decline"):
        await handle_friendly_accept("1", challenger_id, nonce, interaction)
        
    # Non-participant accepts challenge -> raises participant error
    with pytest.raises(ValueError, match="You are not a participant in this friendly challenge"):
        await handle_friendly_accept("1", 999, nonce, interaction)
        
    # Opponent accepts challenge -> succeeds (runs progressively)
    with patch.object(friendly_playback_service, "step_delay_seconds", 0.001):
        view = await handle_friendly_accept("1", opponent_id, nonce, interaction)
        assert isinstance(view, V2View)
        assert ui_session.metadata["status"] == "playing"
        
        # Wait a tiny bit for playback loop to finish progressively
        await asyncio.sleep(0.2)
        
        # Verify session is marked completed
        assert ui_session.metadata["status"] == "completed"
        
        # Subsequent Accept clicks on completed session -> rejected
        with pytest.raises(ValueError, match="already been simulated"):
            await handle_friendly_accept("1", opponent_id, nonce, interaction)


@pytest.mark.asyncio
async def test_challenge_decline_workflow():
    opponent_id = 222
    challenger_id = 111
    ui_session = ui_session_manager.create_session(
        discord_user_id=opponent_id,
        guild_id="12345",
        metadata={
            "type": "friendly_challenge",
            "status": "pending",
            "challenger_user_id": challenger_id,
            "opponent_user_id": opponent_id,
            "challenger_club_id": str(uuid.uuid4()),
            "opponent_club_id": str(uuid.uuid4()),
            "challenger_club_name": "Challenger FC",
            "opponent_club_name": "Opponent FC"
        }
    )
    nonce = ui_session.session_id
    
    # Challenger decline -> rejected
    with pytest.raises(ValueError, match="Only the challenged manager can accept/decline"):
        await handle_friendly_decline("1", challenger_id, nonce)
        
    # Non-participant decline -> rejected
    with pytest.raises(ValueError, match="You are not a participant in this friendly challenge"):
        await handle_friendly_decline("1", 999, nonce)
    
    # Decline succeeds
    view = await handle_friendly_decline("1", opponent_id, nonce)
    assert isinstance(view, V2View)
    assert ui_session.metadata["status"] == "declined"
    
    # Verify session is cleaned up
    assert ui_session_manager.get_session(nonce) is None


@pytest.mark.asyncio
async def test_challenge_cancel_workflow():
    opponent_id = 222
    challenger_id = 111
    ui_session = ui_session_manager.create_session(
        discord_user_id=opponent_id,
        guild_id="12345",
        metadata={
            "type": "friendly_challenge",
            "status": "pending",
            "challenger_user_id": challenger_id,
            "opponent_user_id": opponent_id,
            "challenger_club_id": str(uuid.uuid4()),
            "opponent_club_id": str(uuid.uuid4()),
            "challenger_club_name": "Challenger FC",
            "opponent_club_name": "Opponent FC"
        }
    )
    nonce = ui_session.session_id
    
    from app.ui.handlers.friendly_handler import handle_friendly_cancel
    
    # Opponent cancel -> rejected
    with pytest.raises(ValueError, match="Only the challenger who sent the challenge"):
        await handle_friendly_cancel("1", opponent_id, nonce)
        
    # Non-participant cancel -> rejected
    with pytest.raises(ValueError, match="Only the challenger who sent the challenge"):
        await handle_friendly_cancel("1", 999, nonce)
        
    # Challenger cancel -> succeeds
    view = await handle_friendly_cancel("1", challenger_id, nonce)
    assert isinstance(view, V2View)
    assert ui_session.metadata["status"] == "cancelled"
    
    # Verify session is cleaned up
    assert ui_session_manager.get_session(nonce) is None


@pytest.mark.asyncio
@patch("app.ui.handlers.friendly_handler.get_session")
@patch("app.ui.handlers.friendly_handler.get_user_club")
async def test_practice_mode_hub_opening(mock_get_club, mock_get_session):
    session_mock = AsyncMock()
    mock_get_session.return_value.__aenter__.return_value = session_mock
    
    user = MagicMock(spec=discord.Member, id=111, display_name="Manager")
    club = Club(id=uuid.uuid4(), name="Practice FC", guild_id="12345")
    mock_get_club.return_value = club
    
    view = await handle_friendly_practice("12345", user)
    assert isinstance(view, V2View)
    components = view.to_components()
    
    # Verify it lists Select menu for bot difficulty selection
    has_select = False
    for comp in components:
        if comp.get("type") == 1:  # ACTION_ROW
            for child in comp.get("components", []):
                if child.get("type") == 3:  # STRING_SELECT
                    assert "friendly:practice:select" in child.get("custom_id", "")
                    has_select = True
    assert has_select


@pytest.mark.asyncio
@patch("app.ui.handlers.friendly_handler.get_session")
@patch("app.ui.handlers.friendly_handler.FriendlyService.resolve_team_lineup")
@patch("app.services.friendly_live_playback_service.get_session")
@patch("app.services.friendly_live_playback_service.get_or_create_guild_config")
async def test_practice_mode_simulation_select(
    mock_get_guild_config,
    mock_playback_get_session,
    mock_resolve_lineup,
    mock_get_session
):
    session_mock = AsyncMock()
    mock_get_session.return_value.__aenter__.return_value = session_mock
    mock_playback_get_session.return_value.__aenter__.return_value = session_mock
    
    guild_config = GuildConfig(guild_id="12345", supports_private_threads=True)
    mock_get_guild_config.return_value = guild_config
    
    club_id = uuid.uuid4()
    ui_session = ui_session_manager.create_session(
        discord_user_id=111,
        guild_id="12345",
        metadata={
            "type": "friendly_practice",
            "status": "pending",
            "club_id": str(club_id),
            "club_name": "Practice FC"
        }
    )
    nonce = ui_session.session_id
    
    # Mock Resolved User Lineup
    from app.engine.match_engine import MatchPlayerInput
    dummy_starters = [
        MatchPlayerInput(
            player_id=str(uuid.uuid4()),
            name=f"Player {i}",
            position="GK" if i == 0 else "CB" if i < 4 else "CM" if i < 8 else "ST",
            slot="GK" if i == 0 else f"CB{i}" if i < 4 else f"CM{i}" if i < 8 else f"ST{i}",
            overall=70,
            potential=75,
            fitness=100,
            morale=80,
            consistency=70,
            is_goalkeeper=(i == 0)
        )
        for i in range(11)
    ]
    mock_resolve_lineup.return_value = ("4-3-3", dummy_starters)
    
    # Mock database executes for club load
    club = Club(id=club_id, name="Practice FC", guild_id="12345")
    mock_execute_res = MagicMock()
    mock_execute_res.scalar_one_or_none.return_value = club
    session_mock.execute.return_value = mock_execute_res
    
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
    
    # Run practice against Legend bot (mocking progressive delay)
    with patch.object(friendly_playback_service, "step_delay_seconds", 0.001):
        view = await handle_friendly_practice_select("legend", 111, nonce, interaction)
        assert isinstance(view, V2View)
        
        # Verify database was NOT written to (pure transient sandbox)
        assert len(session_mock.add.call_args_list) == 0
        assert len(session_mock.commit.call_args_list) == 0
        
        # Yield control for loop to finish
        await asyncio.sleep(0.2)
        
        # Verify session cleaned up after completion
        assert ui_session_manager.get_session(nonce) is None


@pytest.mark.asyncio
@patch("app.services.friendly_service.get_active_lineup")
@patch("app.services.friendly_service.get_players_by_club_id")
async def test_friendly_invalid_lineup_fallback_auto_best_xi(mock_get_players, mock_get_active_lineup):
    # Setup mocks
    session_mock = AsyncMock()
    mock_get_active_lineup.return_value = None  # No active lineup saved
    
    # Generate 15 dummy players
    players = []
    positions = ["GK", "LB", "CB", "CB", "RB", "LM", "CM", "CM", "RM", "ST", "ST", "LM", "CM", "CB", "GK"]
    for i, pos in enumerate(positions):
        players.append(Player(
            id=uuid.uuid4(),
            first_name="Player",
            last_name=str(i),
            display_name=f"Player {i}",
            position=pos,
            overall=65,
            potential=70,
            fitness=100,
            morale=80,
            consistency=70
        ))
    mock_get_players.return_value = players
    
    club = Club(id=uuid.uuid4(), name="Practice FC", guild_id="12345")
    
    # Should resolve successfully using fallback auto lineup
    formation, starters = await FriendlyService.resolve_team_lineup(session_mock, "12345", club)
    assert formation == "4-4-2"
    assert len(starters) == 11
    
    # Verify GK position exists in starters
    gk_found = False
    for p in starters:
        if p.position == "GK":
            gk_found = True
            break
    assert gk_found
