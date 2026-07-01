# tests/test_league_lifecycle_service.py

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.league_lifecycle_service import LeagueLifecycleService
from app.models.guild_config import GuildConfig
from app.models.league import League, LeagueStatus
from app.models.club import Club

@pytest.mark.asyncio
@patch("app.services.league_lifecycle_service.get_session")
async def test_auto_start_disabled(mock_get_session):
    mock_session = AsyncMock()
    mock_get_session.return_value.__aenter__.return_value = mock_session
    
    config = GuildConfig(
        guild_id="123456",
        auto_start_league=False
    )
    
    with patch("app.services.league_lifecycle_service.get_or_create_guild_config", return_value=config):
        res = await LeagueLifecycleService.check_and_trigger_auto_start("123456")
        assert res is None

@pytest.mark.asyncio
@patch("app.services.league_lifecycle_service.get_session")
async def test_auto_start_not_enough_humans(mock_get_session):
    mock_session = AsyncMock()
    mock_get_session.return_value.__aenter__.return_value = mock_session
    
    config = GuildConfig(
        guild_id="123456",
        auto_start_league=True,
        minimum_human_clubs=3
    )
    
    league = League(
        id=None,
        guild_id="123456",
        name="Test League",
        status=LeagueStatus.DRAFT,
        max_clubs=8
    )
    
    clubs = [
        Club(guild_id="123456", is_bot_controlled=False),
        Club(guild_id="123456", is_bot_controlled=False)
    ]
    
    with patch("app.services.league_lifecycle_service.get_or_create_guild_config", return_value=config), \
         patch("app.services.league_lifecycle_service.get_draft_league_by_guild", return_value=league), \
         patch("app.services.league_lifecycle_service.get_clubs_in_league", return_value=clubs):
         
        res = await LeagueLifecycleService.check_and_trigger_auto_start("123456")
        assert res is None

@pytest.mark.asyncio
@patch("app.services.league_lifecycle_service.get_session")
async def test_auto_start_triggered_by_auto_fill(mock_get_session):
    mock_session = AsyncMock()
    mock_get_session.return_value.__aenter__.return_value = mock_session
    
    config = GuildConfig(
        guild_id="123456",
        auto_start_league=True,
        auto_fill_with_bot_clubs=True,
        minimum_human_clubs=2
    )
    
    league = League(
        id=None,
        guild_id="123456",
        name="Test League",
        status=LeagueStatus.DRAFT,
        max_clubs=8
    )
    
    clubs = [
        Club(guild_id="123456", is_bot_controlled=False),
        Club(guild_id="123456", is_bot_controlled=False)
    ]
    
    # Mock return from start_league
    from app.services.league_service import LeagueResult
    expected_result = LeagueResult(success=True, code="success", message="League started!")
    
    with patch("app.services.league_lifecycle_service.get_or_create_guild_config", return_value=config), \
         patch("app.services.league_lifecycle_service.get_draft_league_by_guild", return_value=league), \
         patch("app.services.league_lifecycle_service.get_clubs_in_league", return_value=clubs), \
         patch("app.services.league_lifecycle_service.start_league", return_value=expected_result) as mock_start_league:
         
        res = await LeagueLifecycleService.check_and_trigger_auto_start("123456")
        assert res is not None
        assert res.success
        mock_start_league.assert_called_once_with("123456")
