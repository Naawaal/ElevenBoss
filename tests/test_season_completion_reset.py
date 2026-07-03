import unittest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

# Mock asyncio.get_running_loop() before importing any discord.ui components
mock_loop = MagicMock()
mock_loop.create_future.return_value = MagicMock()
asyncio.get_running_loop = MagicMock(return_value=mock_loop)

import pytest
import uuid
from datetime import datetime, timezone

from app.models.league import League, LeagueStatus
from app.models.season import Season, SeasonStatus
from app.models.season_snapshot import SeasonSnapshot
from app.models.club import Club
from app.models.standing import LeagueStanding
from app.services.season_completion_service import SeasonCompletionService
from app.services.season_reset_service import SeasonResetService
from app.services.league_lifecycle_service import LeagueLifecycleService
from app.services.league_service import start_league
from app.ui.layouts.season import build_season_summary_layout
from app.ui.components import V2View

@pytest.mark.asyncio
@patch("app.services.season_completion_service.get_season_snapshot")
@patch("app.services.season_completion_service.get_ranked_table")
@patch("app.services.season_completion_service.create_season_snapshot")
async def test_save_final_snapshot_success(
    mock_create_snapshot,
    mock_get_table,
    mock_get_snapshot,
):
    # Setup mocks
    session_mock = AsyncMock()
    mock_get_snapshot.return_value = None
    
    # Mock Standings
    club_1 = Club(id=uuid.uuid4(), name="Pokhara City")
    club_2 = Club(id=uuid.uuid4(), name="Kathmandu FC")
    
    standing1 = LeagueStanding(club_id=club_1.id, club=club_1, played=2, wins=2, draws=0, losses=0, goals_for=4, goals_against=1, goal_difference=3, points=6)
    standing2 = LeagueStanding(club_id=club_2.id, club=club_2, played=2, wins=0, draws=0, losses=2, goals_for=1, goals_against=4, goal_difference=-3, points=0)
    
    mock_get_table.return_value = [standing1, standing2]
    
    # Mock Season
    season = Season(
        id=uuid.uuid4(),
        guild_id="12345",
        league_id=uuid.uuid4(),
        season_number=1,
        status=SeasonStatus.ACTIVE
    )
    mock_execute_result = MagicMock()
    mock_execute_result.scalar_one_or_none.return_value = season
    session_mock.execute.return_value = mock_execute_result

    res = await SeasonCompletionService.save_final_snapshot(session_mock, "12345", season.id)
    assert res is True
    mock_create_snapshot.assert_called_once()
    
    # Verify snapshot call arguments
    args = mock_create_snapshot.call_args[1]
    assert args["guild_id"] == "12345"
    assert args["season_id"] == season.id
    assert args["season_number"] == 1
    assert args["champion_club_id"] == club_1.id
    assert args["runner_up_club_id"] == club_2.id
    assert args["total_matches"] == 2
    assert args["total_goals"] == 5
    assert args["final_table_json"] == {
        "rows": [
            {
                "club_id": str(club_1.id),
                "club_name": "Pokhara City",
                "played": 2,
                "wins": 2,
                "draws": 0,
                "losses": 0,
                "goals_for": 4,
                "goals_against": 1,
                "goal_difference": 3,
                "points": 6,
                "rank": 1
            },
            {
                "club_id": str(club_2.id),
                "club_name": "Kathmandu FC",
                "played": 2,
                "wins": 0,
                "draws": 0,
                "losses": 2,
                "goals_for": 1,
                "goals_against": 4,
                "goal_difference": -3,
                "points": 0,
                "rank": 2
            }
        ]
    }


@pytest.mark.asyncio
@patch("app.services.league_lifecycle_service.get_session")
@patch("app.repositories.get_or_create_running_job")
@patch("app.repositories.mark_job_success")
@patch("app.services.player_service.PlayerService.age_players", new_callable=AsyncMock)
@patch("app.services.season_completion_service.SeasonCompletionService.save_final_snapshot", new_callable=AsyncMock)
@patch("app.repositories.guild_config_repository.get_or_create_guild_config")
async def test_complete_current_season_saves_snapshot(
    mock_get_config,
    mock_save_snapshot,
    mock_age_players,
    mock_job_success,
    mock_get_job,
    mock_get_session
):
    session_mock = AsyncMock()
    mock_get_session.return_value.__aenter__.return_value = session_mock
    
    season_id = uuid.uuid4()
    league_id = uuid.uuid4()
    season = Season(id=season_id, league_id=league_id, status=SeasonStatus.ACTIVE, season_number=1)
    league = League(id=league_id, status=LeagueStatus.ACTIVE)
    
    # Mock double row locking executions
    res1 = MagicMock()
    res1.scalar_one_or_none.side_effect = [season, league]
    session_mock.execute.return_value = res1

    # Mock Config: auto_start_league = False
    mock_config = MagicMock()
    mock_config.auto_start_league = False
    mock_get_config.return_value = mock_config

    res = await LeagueLifecycleService.complete_current_season(session_mock, "12345", season_id)
    assert res is True
    
    # Verify save snapshot was triggered
    mock_save_snapshot.assert_called_once_with(session_mock, "12345", season_id)
    assert season.status == SeasonStatus.COMPLETED
    assert league.status == LeagueStatus.COMPLETED


@pytest.mark.asyncio
@patch("app.services.season_reset_service.get_session")
@patch("app.services.season_reset_service.get_latest_league_for_update")
@patch("app.services.season_reset_service.get_or_create_running_job")
@patch("app.services.season_reset_service.mark_job_success")
@patch("app.services.season_reset_service.get_clubs_in_league")
async def test_prepare_next_season_success(
    mock_get_clubs,
    mock_job_success,
    mock_get_job,
    mock_get_league,
    mock_get_session
):
    session_mock = AsyncMock()
    mock_get_session.return_value.__aenter__.return_value = session_mock
    
    # League Status COMPLETED
    league = League(id=uuid.uuid4(), status=LeagueStatus.COMPLETED)
    mock_get_league.return_value = league
    
    # Latest Season completed
    season = Season(id=uuid.uuid4(), league_id=league.id, status=SeasonStatus.COMPLETED, season_number=1)
    res_season = MagicMock()
    res_season.scalars.return_value.first.return_value = season
    session_mock.execute.return_value = res_season
    
    # Human & Bot clubs
    club1 = Club(id=uuid.uuid4(), name="Club 1", season_id=season.id)
    mock_get_clubs.return_value = [club1]
    
    res = await SeasonResetService.prepare_next_season("12345")
    assert res["success"] is True
    assert league.status == LeagueStatus.DRAFT
    
    # Checks that new draft season was added
    assert len(session_mock.add.call_args_list) > 0
    added_obj = session_mock.add.call_args_list[0][0][0]
    assert isinstance(added_obj, Season)
    assert added_obj.season_number == 2
    assert added_obj.status == SeasonStatus.DRAFT
    assert club1.season_id == added_obj.id


@pytest.mark.asyncio
@patch("app.services.league_service.get_session")
@patch("app.services.league_service.claim_league_for_starting")
@patch("app.services.league_service.get_or_create_running_job")
@patch("app.services.league_service.mark_job_success")
@patch("app.services.league_service.initialize_standings")
@patch("app.services.league_service.bulk_create_fixtures")
async def test_start_league_with_existing_draft_season(
    mock_bulk_fixtures,
    mock_init_standings,
    mock_job_success,
    mock_get_job,
    mock_claim,
    mock_get_session
):
    session_mock = AsyncMock()
    mock_get_session.return_value.__aenter__.return_value = session_mock
    
    league_id = uuid.uuid4()
    league = League(id=league_id, name="Nepal Premier", target_club_count=2, status=LeagueStatus.STARTING, fill_bots_after_deadline=True)
    mock_claim.return_value = league
    
    # 1 human club
    human_club = Club(id=uuid.uuid4(), name="Kathmandu Human", is_bot_controlled=False, league_id=league_id)
    res_clubs = MagicMock()
    res_clubs.scalars.return_value.all.return_value = [human_club]
    
    # Existing draft Season 2
    draft_season = Season(id=uuid.uuid4(), league_id=league_id, status=SeasonStatus.DRAFT, season_number=2)
    
    # Mock session executes
    mock_execute_res = MagicMock()
    mock_execute_res.scalars.return_value.all.return_value = [human_club]
    mock_execute_res.scalar_one_or_none.return_value = draft_season
    session_mock.execute.return_value = mock_execute_res
    
    with patch("app.services.league_service.generate_bot_clubs_for_league") as mock_bot_gen:
        bot_club = Club(id=uuid.uuid4(), name="Bot FC", is_bot_controlled=True, league_id=league_id)
        mock_bot_gen.return_value = [bot_club]
        
        result = await start_league("12345", force_bot_fill=True)
        assert result.success is True
        assert result.season_id == draft_season.id
        assert draft_season.status == SeasonStatus.ACTIVE
        assert human_club.season_id == draft_season.id
        assert bot_club.season_id == draft_season.id


def test_build_season_summary_layout_view():
    snapshot_data = {
        "season_number": 1,
        "champion_name": "Pokhara City",
        "runner_up_name": "Kathmandu FC",
        "total_matches": 28,
        "total_goals": 79,
        "table_rows": [
            {"rank": 1, "club_name": "Pokhara City", "played": 14, "wins": 10, "draws": 2, "losses": 2, "goals_for": 35, "goals_against": 12, "points": 32},
            {"rank": 2, "club_name": "Kathmandu FC", "played": 14, "wins": 8, "draws": 3, "losses": 3, "goals_for": 28, "goals_against": 15, "points": 27}
        ]
    }
    view = build_season_summary_layout(snapshot_data, "nonce-test")
    assert isinstance(view, V2View)
    
    # Assert elements exist
    components = view.to_components()
    has_text = False
    for comp in components:
        if comp.get("type") == 17:  # Container
            for child in comp.get("components", []):
                if child.get("type") == 10:  # TextDisplay
                    content = child.get("content", "")
                    assert "SEASON 1 SUMMARY" in content
                    assert "🥇 **Champion:** **Pokhara City**" in content
                    assert "🥈 **Runner-up:** **Kathmandu FC**" in content
                    assert "Nepal" not in content  # Just a safety check
                    has_text = True
    assert has_text
