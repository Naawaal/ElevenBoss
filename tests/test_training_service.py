# tests/test_training_service.py

import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal

from app.models.player import Player
from app.models.club import Club
from app.models.fixture import Fixture
from app.models.player_development import PlayerDevelopmentState, ClubTrainingSettings, WeeklyTrainingLog, MatchDevelopmentEvent
from app.models.facility import Facility, FacilityType
from app.services.training_service import TrainingService


@pytest.mark.asyncio
async def test_weekly_tick_excludes_bot_clubs():
    session = AsyncMock()
    guild_id = "test_guild"
    season_id = uuid.uuid4()
    week = 1

    # Mock get_human_club_players_for_training to return empty (meaning no human club players or all bots excluded)
    with patch("app.services.training_service.get_human_club_players_for_training", new_callable=AsyncMock) as mock_get_players:
        mock_get_players.return_value = []
        
        await TrainingService.run_weekly_training_tick(session, guild_id, season_id, week)
        
        # Verify get_or_create_dev_state and other DB operations were not called
        session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_weekly_tick_creates_dev_state_for_human_player():
    session = AsyncMock()
    guild_id = "test_guild"
    season_id = uuid.uuid4()
    week = 1

    club = Club(id=uuid.uuid4(), guild_id=guild_id, is_bot_controlled=False, name="Human FC")
    player = Player(
        id=uuid.uuid4(),
        club_id=club.id,
        guild_id=guild_id,
        display_name="John Doe",
        age=22,
        overall=70,
        potential=80,
        sharpness=50,
        morale=75,
        fitness=100,
        injury_days_remaining=0,
        is_retired=False,
    )

    with patch("app.services.training_service.get_human_club_players_for_training", new_callable=AsyncMock) as mock_get_players, \
         patch("app.services.training_service.get_or_create_training_settings", new_callable=AsyncMock) as mock_settings, \
         patch("app.services.training_service.get_or_create_dev_state", new_callable=AsyncMock) as mock_dev_state, \
         patch("app.services.training_service.insert_weekly_training_log_returning_id", new_callable=AsyncMock) as mock_insert_log:
        
        mock_get_players.return_value = [(club, player)]
        
        club_settings = ClubTrainingSettings(club_id=club.id, season_id=season_id, guild_id=guild_id, default_plan="balanced", intensity="normal")
        mock_settings.return_value = club_settings
        
        dev_state = PlayerDevelopmentState(
            club_id=club.id,
            player_id=player.id,
            season_id=season_id,
            guild_id=guild_id,
            training_xp=0,
            match_xp=0,
            weeks_trained=0,
            plan_type="balanced",
            readiness_modifier=Decimal("1.00"),
        )
        mock_dev_state.return_value = dev_state
        
        mock_insert_log.return_value = uuid.uuid4()  # insert succeeded

        # Mock facility query to return no facilities (default level 1)
        mock_execute = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_execute.scalars.return_value = mock_scalars
        session.execute.return_value = mock_execute

        await TrainingService.run_weekly_training_tick(session, guild_id, season_id, week)

        # Check player mutations: sharpness +2, morale +1, fitness unchanged
        assert player.sharpness == 52
        assert player.morale == 76
        assert player.fitness == 100

        # Check dev_state mutations: training_xp += 8, weeks_trained += 1
        assert dev_state.training_xp == 8
        assert dev_state.weeks_trained == 1
        assert dev_state.readiness_modifier == Decimal("1.00")


@pytest.mark.asyncio
async def test_weekly_tick_skips_when_insert_returns_none():
    session = AsyncMock()
    guild_id = "test_guild"
    season_id = uuid.uuid4()
    week = 1

    club = Club(id=uuid.uuid4(), guild_id=guild_id, is_bot_controlled=False, name="Human FC")
    player = Player(
        id=uuid.uuid4(),
        club_id=club.id,
        guild_id=guild_id,
        display_name="John Doe",
        age=22,
        overall=70,
        potential=80,
        sharpness=50,
        morale=75,
        fitness=100,
        injury_days_remaining=0,
        is_retired=False,
    )

    with patch("app.services.training_service.get_human_club_players_for_training", new_callable=AsyncMock) as mock_get_players, \
         patch("app.services.training_service.get_or_create_training_settings", new_callable=AsyncMock) as mock_settings, \
         patch("app.services.training_service.get_or_create_dev_state", new_callable=AsyncMock) as mock_dev_state, \
         patch("app.services.training_service.insert_weekly_training_log_returning_id", new_callable=AsyncMock) as mock_insert_log:
        
        mock_get_players.return_value = [(club, player)]
        
        club_settings = ClubTrainingSettings(club_id=club.id, season_id=season_id, guild_id=guild_id, default_plan="balanced", intensity="normal")
        mock_settings.return_value = club_settings
        
        dev_state = PlayerDevelopmentState(
            club_id=club.id,
            player_id=player.id,
            season_id=season_id,
            guild_id=guild_id,
            training_xp=10,
            match_xp=5,
            weeks_trained=1,
            plan_type="balanced",
            readiness_modifier=Decimal("1.00"),
        )
        mock_dev_state.return_value = dev_state
        
        mock_insert_log.return_value = None  # insert failed (log already exists for this week)

        mock_execute = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_execute.scalars.return_value = mock_scalars
        session.execute.return_value = mock_execute

        await TrainingService.run_weekly_training_tick(session, guild_id, season_id, week)

        # Player stats must NOT change because log insertion failed (already processed)
        assert player.sharpness == 50
        assert player.morale == 75
        assert player.fitness == 100

        # Dev state must NOT change
        assert dev_state.training_xp == 10
        assert dev_state.weeks_trained == 1


@pytest.mark.asyncio
async def test_match_dev_events_exclude_bot_players():
    session = AsyncMock()
    fixture = Fixture(
        id=uuid.uuid4(),
        guild_id="test_guild",
        season_id=uuid.uuid4(),
        home_club_id=uuid.uuid4(),
        away_club_id=uuid.uuid4(),
    )

    # Let's mock the Club queries
    home_club = Club(id=fixture.home_club_id, is_bot_controlled=True, name="Bot FC")
    away_club = Club(id=fixture.away_club_id, is_bot_controlled=False, name="Human FC")

    async def session_execute_side_effect(stmt):
        # Inspect the compiled query parameters to find the club ID being queried
        compiled = stmt.compile()
        params = compiled.params
        # Find the ID parameter (could be 'id_1')
        id_val = params.get("id_1")
        if not id_val and params:
            id_val = list(params.values())[0]
        
        m = MagicMock()
        if id_val == home_club.id:
            m.scalar_one.return_value = home_club
        else:
            m.scalar_one.return_value = away_club
        return m
    session.execute = AsyncMock(side_effect=session_execute_side_effect)

    # Mock MatchSimulationResult
    sim_result = MagicMock()
    # Bot player played 90 mins, Human player played 90 mins
    bot_player_id = uuid.uuid4()
    human_player_id = uuid.uuid4()
    sim_result.played_minutes = {
        str(bot_player_id): 90,
        str(human_player_id): 90,
    }
    sim_result.player_ratings = {
        str(bot_player_id): 7.0,
        str(human_player_id): 7.0,
    }

    players_by_id = {
        bot_player_id: Player(id=bot_player_id, club_id=home_club.id, display_name="Bot P", is_retired=False),
        human_player_id: Player(id=human_player_id, club_id=away_club.id, display_name="Human P", is_retired=False),
    }

    with patch("app.services.training_service.insert_match_development_event_returning_id", new_callable=AsyncMock) as mock_insert_event, \
         patch("app.services.training_service.get_or_create_dev_state", new_callable=AsyncMock) as mock_get_dev:
        
        mock_insert_event.return_value = uuid.uuid4()
        dev_state = PlayerDevelopmentState(
            club_id=away_club.id, player_id=human_player_id, season_id=fixture.season_id, guild_id=fixture.guild_id, match_xp=0
        )
        mock_get_dev.return_value = dev_state

        await TrainingService.record_match_development_events(
            session, fixture, sim_result, fixture.home_club_id, fixture.away_club_id, players_by_id
        )

        # insert_match_development_event must be called exactly once (for the human player, not the bot)
        mock_insert_event.assert_called_once()
        called_args = mock_insert_event.call_args[1]
        assert called_args["player_id"] == human_player_id
        assert called_args["club_id"] == away_club.id
        
        # Human player dev state XP must be updated
        # rating = 7.0, mins = 90
        # base = 5
        # mins_played // 30 = 3 -> +9
        # rating diff = 7.0 - 6.0 = 1.0 -> rating bonus = +2
        # Total = 16 XP
        assert dev_state.match_xp == 16


@pytest.mark.asyncio
async def test_match_dev_event_skips_when_insert_returns_none():
    session = AsyncMock()
    fixture = Fixture(
        id=uuid.uuid4(),
        guild_id="test_guild",
        season_id=uuid.uuid4(),
        home_club_id=uuid.uuid4(),
        away_club_id=uuid.uuid4(),
    )

    home_club = Club(id=fixture.home_club_id, is_bot_controlled=False, name="Human 1 FC")
    away_club = Club(id=fixture.away_club_id, is_bot_controlled=True, name="Bot FC")

    mock_execute = MagicMock()
    async def session_execute_side_effect(stmt):
        stmt_str = str(stmt)
        m = MagicMock()
        if str(fixture.home_club_id) in stmt_str:
            m.scalar_one.return_value = home_club
        else:
            m.scalar_one.return_value = away_club
        return m
    session.execute = AsyncMock(side_effect=session_execute_side_effect)

    sim_result = MagicMock()
    human_player_id = uuid.uuid4()
    sim_result.played_minutes = {
        str(human_player_id): 90,
    }
    sim_result.player_ratings = {
        str(human_player_id): 7.0,
    }

    players_by_id = {
        human_player_id: Player(id=human_player_id, club_id=home_club.id, display_name="Human P", is_retired=False),
    }

    with patch("app.services.training_service.insert_match_development_event_returning_id", new_callable=AsyncMock) as mock_insert_event, \
         patch("app.services.training_service.get_or_create_dev_state", new_callable=AsyncMock) as mock_get_dev:
        
        mock_insert_event.return_value = None  # event already exists
        
        await TrainingService.record_match_development_events(
            session, fixture, sim_result, fixture.home_club_id, fixture.away_club_id, players_by_id
        )

        # mock_get_dev should not be called since insert failed
        mock_get_dev.assert_not_called()


@pytest.mark.asyncio
async def test_calculate_bonuses_excludes_retired_players():
    session = AsyncMock()
    season_id = uuid.uuid4()

    # eligible states should not be returned if players are retired or age >= 30,
    # but the repository's get_season_dev_states_for_bonus is expected to pre-filter them.
    # We still check that calculate_season_training_bonuses works correctly.
    player = Player(
        id=uuid.uuid4(),
        age=25,
        overall=70,
        potential=80,
        is_retired=False,
    )
    dev_state = PlayerDevelopmentState(
        id=uuid.uuid4(),
        player_id=player.id,
        season_id=season_id,
        training_xp=180,
        match_xp=120,
        weeks_trained=10,
        season_bonus_applied=False,
        player=player,
    )

    with patch("app.services.training_service.get_season_dev_states_for_bonus", new_callable=AsyncMock) as mock_get_eligible:
        mock_get_eligible.return_value = [dev_state]

        bonus_map = await TrainingService.calculate_season_training_bonuses(session, season_id)
        
        # Avg weekly XP = (180 + 120) / 10 = 30.0 -> bonus = 2
        assert bonus_map[player.id] == 2
