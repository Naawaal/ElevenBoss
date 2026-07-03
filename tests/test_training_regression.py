# tests/test_training_regression.py

import pytest
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.player import Player
from app.models.club import Club
from app.models.player_development import PlayerDevelopmentState
from app.services.player_service import PlayerService
from app.services.lineup_service import LineupService
from app.engine.training_engine import calculate_season_training_bonus


@pytest.mark.asyncio
async def test_season_bonus_applied_even_when_zero():
    """
    Verifies that every evaluated development state is marked season_bonus_applied=True,
    even when the bonus is 0 (e.g. for players age >= 30).
    """
    session = AsyncMock()
    season_id = uuid.uuid4()

    # 1. Player age 32 (should get 0 bonus)
    player = Player(
        id=uuid.uuid4(),
        display_name="Veteran Player",
        age=32,
        overall=70,
        potential=75,
        fitness=100,
        is_retired=False,
    )
    dev_state = PlayerDevelopmentState(
        id=uuid.uuid4(),
        player_id=player.id,
        season_id=season_id,
        training_xp=200,
        match_xp=100,
        weeks_trained=10, # avg = 30 XP/wk -> raw bonus would be 2
        season_bonus_applied=False,
        player=player,
    )

    # Mock repository methods
    with patch("app.repositories.training_repository.get_season_dev_states_for_bonus", new_callable=AsyncMock) as mock_get_eligible, \
         patch("app.repositories.training_repository.mark_bonus_applied", new_callable=AsyncMock) as mock_mark_applied:
        
        mock_get_eligible.return_value = [dev_state]
        
        bonus_map = {player.id: 0} # computed as 0 because age >= 30
        
        await PlayerService.apply_training_bonuses_after_aging(session, season_id, bonus_map)

        # Player overall must NOT change
        assert player.overall == 70
        
        # mark_bonus_applied must still be called with bonus_ovr=0 to flag the state as evaluated
        mock_mark_applied.assert_called_once_with(session, dev_state.id, 0)


@pytest.mark.asyncio
async def test_season_bonus_capped_by_potential():
    """
    Verifies that season OVR training bonus never exceeds potential room.
    """
    # Potential room = 1 (OVR 78 -> POT 79). Avg XP = 30 -> raw bonus = 2.
    # Bonus must be capped at 1.
    bonus = calculate_season_training_bonus(
        age=22,
        overall=78,
        potential=79,
        training_xp=200,
        match_xp=100,
        weeks_trained=10,
        season_bonus_already_applied=False,
    )
    assert bonus == 1

    # Apply via PlayerService
    session = AsyncMock()
    season_id = uuid.uuid4()

    player = Player(
        id=uuid.uuid4(),
        display_name="Young Star",
        age=22,
        overall=78,
        potential=79,
        fitness=100,
        is_retired=False,
    )
    dev_state = PlayerDevelopmentState(
        id=uuid.uuid4(),
        player_id=player.id,
        season_id=season_id,
        training_xp=200,
        match_xp=100,
        weeks_trained=10,
        season_bonus_applied=False,
        player=player,
    )

    with patch("app.repositories.training_repository.get_season_dev_states_for_bonus", new_callable=AsyncMock) as mock_get_eligible, \
         patch("app.repositories.training_repository.mark_bonus_applied", new_callable=AsyncMock) as mock_mark_applied:
        
        mock_get_eligible.return_value = [dev_state]
        
        bonus_map = {player.id: 2} # raw bonus
        
        await PlayerService.apply_training_bonuses_after_aging(session, season_id, bonus_map)

        # Player overall must be capped at potential (79)
        assert player.overall == 79
        
        # mark_bonus_applied must receive the actual applied value (1), not the raw mapped value (2)
        mock_mark_applied.assert_called_once_with(session, dev_state.id, 1)


@pytest.mark.asyncio
async def test_readiness_snapshot_does_not_mutate_db_fitness():
    """
    Verifies that training readiness modifier only scales the fitness value inside
    the MatchPlayerInput snapshot, leaving the persistent player.fitness unchanged.
    """
    session = AsyncMock()
    club_id = uuid.uuid4()
    guild_id = "123"
    
    # Setup target player and 10 dummy players to make a full squad of 11
    player = Player(
        id=uuid.uuid4(),
        club_id=club_id,
        display_name="John Doe",
        position="ST",
        overall=75,
        potential=80,
        fitness=90, # persistent DB fitness
        is_retired=False,
    )
    
    players = [player]
    positions = ["GK", "LB", "CB", "CB", "RB", "LM", "CM", "CM", "RM", "ST"]
    for i, pos in enumerate(positions):
        players.append(Player(
            id=uuid.uuid4(),
            club_id=club_id,
            display_name=f"Dummy Player {i}",
            position=pos,
            overall=60,
            potential=70,
            fitness=100,
            is_retired=False,
        ))

    # Mock lineup queries to return a valid active lineup containing these players
    lineup_mock = MagicMock()
    lineup_mock.formation = "4-4-2"
    lineup_players = []
    
    slots = ["ST1", "GK", "LB", "CB1", "CB2", "RB", "LM", "CM1", "CM2", "RM", "ST2"]
    for slot, p in zip(slots, players):
        lp = MagicMock()
        lp.is_starter = True
        lp.slot = slot
        lp.player = p
        lineup_players.append(lp)
    lineup_mock.lineup_players = lineup_players

    with patch("app.services.lineup_service.get_active_lineup", new_callable=AsyncMock) as mock_get_lineup, \
         patch("app.services.lineup_service.get_players_by_club_id", new_callable=AsyncMock) as mock_get_players, \
         patch("app.services.lineup_service.validate_lineup") as mock_validate:
        
        mock_get_lineup.return_value = lineup_mock
        mock_get_players.return_value = players
        mock_validate.return_value = (True, [])

        # Mock readiness modifier to be 0.95
        dev_state = PlayerDevelopmentState(
            club_id=club_id,
            player_id=player.id,
            season_id=uuid.uuid4(),
            guild_id=guild_id,
            readiness_modifier=Decimal("0.95"),
        )
        dev_state_map = {player.id: dev_state}

        with patch("app.repositories.get_active_or_draft_league_by_guild", new_callable=AsyncMock) as mock_league, \
             patch("app.repositories.get_active_season_for_league", new_callable=AsyncMock) as mock_season, \
             patch("app.repositories.training_repository.get_dev_state_map_for_players", new_callable=AsyncMock) as mock_get_dev_map:
            
            mock_league.return_value = MagicMock(id=uuid.uuid4())
            mock_season.return_value = MagicMock(id=uuid.uuid4())
            mock_get_dev_map.return_value = dev_state_map

            res = await LineupService.resolve_team_lineup(session, guild_id, club_id, "Test Club", persist_fallback=False)
            
            # Resolved starter should have readiness-adjusted fitness (90 * 0.95 = 85)
            starter = res.starters[0]
            assert starter.fitness == 85
            
            # Persistent player object's fitness MUST remain exactly 90
            assert player.fitness == 90
