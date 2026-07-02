# tests/test_league_lifecycle_service.py

import pytest
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

from app.models.league import League, LeagueStatus
from app.models.club import Club
from app.services.league_lifecycle_service import LeagueLifecycleService
from app.services.league_service import LeagueResult

@pytest.mark.asyncio
@patch("app.services.league_lifecycle_service.get_session")
@patch("app.services.league_lifecycle_service.get_draft_league_by_guild")
async def test_lifecycle_case_1_deadline_not_reached(mock_get_draft, mock_get_session):
    # Case 1: Deadline has not passed -> do nothing
    mock_session = AsyncMock()
    mock_get_session.return_value.__aenter__.return_value = mock_session
    
    future_deadline = datetime.now(timezone.utc) + timedelta(days=1)
    league = League(
        id=uuid.uuid4(),
        guild_id="123456",
        name="Test League",
        status=LeagueStatus.DRAFT,
        registration_deadline_at=future_deadline,
        registration_deadline_timezone="Asia/Kathmandu"
    )
    mock_get_draft.return_value = league

    result = await LeagueLifecycleService.check_and_trigger_auto_start("123456")
    assert result is None

@pytest.mark.asyncio
@patch("app.services.league_lifecycle_service.get_session")
@patch("app.services.league_lifecycle_service.get_draft_league_by_guild")
@patch("app.services.league_lifecycle_service.get_clubs_in_league")
@patch("app.services.league_lifecycle_service.get_joined_player_user_ids")
@patch("app.services.league_lifecycle_service.LeagueLifecycleService.transition_to_review")
async def test_lifecycle_case_2_auto_start_disabled(mock_transition, mock_get_player_ids, mock_get_clubs, mock_get_draft, mock_get_session):
    # Case 2: Deadline passed but auto_start_after_deadline is False -> needs_admin_review
    mock_session = AsyncMock()
    mock_get_session.return_value.__aenter__.return_value = mock_session
    mock_get_player_ids.return_value = [555]
    
    past_deadline = datetime.now(timezone.utc) - timedelta(hours=1)
    league = League(
        id=uuid.uuid4(),
        guild_id="123456",
        name="Test League",
        status=LeagueStatus.DRAFT,
        registration_deadline_at=past_deadline,
        auto_start_after_deadline=False
    )
    mock_get_draft.return_value = league
    mock_get_clubs.return_value = []
    
    result = await LeagueLifecycleService.check_and_trigger_auto_start("123456")
    assert result is not None
    assert result.success is False
    assert result.code == "needs_admin_review"
    assert "Auto-start is disabled" in result.message
    mock_transition.assert_called_once()

@pytest.mark.asyncio
@patch("app.services.league_lifecycle_service.get_session")
@patch("app.services.league_lifecycle_service.get_draft_league_by_guild")
@patch("app.services.league_lifecycle_service.get_clubs_in_league")
@patch("app.services.league_lifecycle_service.get_joined_player_user_ids")
@patch("app.services.league_lifecycle_service.LeagueLifecycleService.transition_to_review")
async def test_lifecycle_case_3_not_enough_humans(mock_transition, mock_get_player_ids, mock_get_clubs, mock_get_draft, mock_get_session):
    # Case 3: Not enough human clubs -> needs_admin_review
    mock_session = AsyncMock()
    mock_get_session.return_value.__aenter__.return_value = mock_session
    mock_get_player_ids.return_value = [555]
    
    past_deadline = datetime.now(timezone.utc) - timedelta(hours=1)
    league = League(
        id=uuid.uuid4(),
        guild_id="123456",
        name="Test League",
        status=LeagueStatus.DRAFT,
        registration_deadline_at=past_deadline,
        auto_start_after_deadline=True,
        minimum_human_clubs=3
    )
    mock_get_draft.return_value = league
    
    # Only 2 humans
    clubs = [
        Club(guild_id="123456", is_bot_controlled=False),
        Club(guild_id="123456", is_bot_controlled=False)
    ]
    mock_get_clubs.return_value = clubs
    
    result = await LeagueLifecycleService.check_and_trigger_auto_start("123456")
    assert result is not None
    assert result.success is False
    assert result.code == "needs_admin_review"
    assert "Minimum humans required" in result.message
    mock_transition.assert_called_once()

@pytest.mark.asyncio
@patch("app.services.league_lifecycle_service.get_session")
@patch("app.services.league_lifecycle_service.get_draft_league_by_guild")
@patch("app.services.league_lifecycle_service.get_clubs_in_league")
@patch("app.services.league_lifecycle_service.get_joined_player_user_ids")
@patch("app.services.league_lifecycle_service.start_league")
async def test_lifecycle_case_4_full_human(mock_start, mock_get_player_ids, mock_get_clubs, mock_get_draft, mock_get_session):
    # Case 4: Deadline passed, league is full with humans -> start_league(force_bot_fill=False)
    mock_session = AsyncMock()
    mock_get_session.return_value.__aenter__.return_value = mock_session
    mock_get_player_ids.return_value = [555]
    
    past_deadline = datetime.now(timezone.utc) - timedelta(hours=1)
    league = League(
        id=uuid.uuid4(),
        guild_id="123456",
        name="Test League",
        status=LeagueStatus.DRAFT,
        registration_deadline_at=past_deadline,
        auto_start_after_deadline=True,
        minimum_human_clubs=2,
        target_club_count=4
    )
    mock_get_draft.return_value = league
    
    # 4 humans
    clubs = [Club(guild_id="123456", is_bot_controlled=False) for _ in range(4)]
    mock_get_clubs.return_value = clubs
    mock_start.return_value = LeagueResult(success=True, code="success", message="Started")
    
    result = await LeagueLifecycleService.check_and_trigger_auto_start("123456")
    assert result is not None
    assert result.success is True
    mock_start.assert_called_once_with("123456", force_bot_fill=False)

@pytest.mark.asyncio
@patch("app.services.league_lifecycle_service.get_session")
@patch("app.services.league_lifecycle_service.get_draft_league_by_guild")
@patch("app.services.league_lifecycle_service.get_clubs_in_league")
@patch("app.services.league_lifecycle_service.get_joined_player_user_ids")
@patch("app.services.league_lifecycle_service.start_league")
async def test_lifecycle_case_5_bot_fill_enabled(mock_start, mock_get_player_ids, mock_get_clubs, mock_get_draft, mock_get_session):
    # Case 5: Under-filled and bot fill enabled -> start_league(force_bot_fill=True)
    mock_session = AsyncMock()
    mock_get_session.return_value.__aenter__.return_value = mock_session
    mock_get_player_ids.return_value = [555]
    
    past_deadline = datetime.now(timezone.utc) - timedelta(hours=1)
    league = League(
        id=uuid.uuid4(),
        guild_id="123456",
        name="Test League",
        status=LeagueStatus.DRAFT,
        registration_deadline_at=past_deadline,
        auto_start_after_deadline=True,
        minimum_human_clubs=2,
        target_club_count=8,
        fill_bots_after_deadline=True
    )
    mock_get_draft.return_value = league
    
    # 2 humans
    clubs = [Club(guild_id="123456", is_bot_controlled=False) for _ in range(2)]
    mock_get_clubs.return_value = clubs
    mock_start.return_value = LeagueResult(success=True, code="success", message="Started")
    
    result = await LeagueLifecycleService.check_and_trigger_auto_start("123456")
    assert result is not None
    assert result.success is True
    mock_start.assert_called_once_with("123456", force_bot_fill=True)

@pytest.mark.asyncio
@patch("app.services.league_lifecycle_service.get_session")
@patch("app.services.league_lifecycle_service.get_draft_league_by_guild")
@patch("app.services.league_lifecycle_service.get_clubs_in_league")
@patch("app.services.league_lifecycle_service.get_joined_player_user_ids")
@patch("app.services.league_lifecycle_service.LeagueLifecycleService.transition_to_review")
async def test_lifecycle_case_6_bot_fill_disabled(mock_transition, mock_get_player_ids, mock_get_clubs, mock_get_draft, mock_get_session):
    # Case 6: Under-filled and bot fill disabled -> needs_admin_review
    mock_session = AsyncMock()
    mock_get_session.return_value.__aenter__.return_value = mock_session
    mock_get_player_ids.return_value = [555]
    
    past_deadline = datetime.now(timezone.utc) - timedelta(hours=1)
    league = League(
        id=uuid.uuid4(),
        guild_id="123456",
        name="Test League",
        status=LeagueStatus.DRAFT,
        registration_deadline_at=past_deadline,
        auto_start_after_deadline=True,
        minimum_human_clubs=2,
        target_club_count=8,
        fill_bots_after_deadline=False
    )
    mock_get_draft.return_value = league
    
    # 2 humans
    clubs = [Club(guild_id="123456", is_bot_controlled=False) for _ in range(2)]
    mock_get_clubs.return_value = clubs
    
    result = await LeagueLifecycleService.check_and_trigger_auto_start("123456")
    assert result is not None
    assert result.success is False
    assert result.code == "needs_admin_review"
    assert "League is under-filled and bot filling is disabled" in result.message
    mock_transition.assert_called_once()
