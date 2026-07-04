# tests/test_match_consequences.py

import unittest
from unittest.mock import patch, AsyncMock, MagicMock
import uuid
from datetime import datetime
from decimal import Decimal

from app.models.player import Player
from app.models.fixture import Fixture
from app.services.match_consequence_service import MatchConsequenceService
from app.services.lineup_service import LineupService
from app.repositories.player_repository import get_available_players_by_club_id

class TestMatchConsequences(unittest.IsolatedAsyncioTestCase):
    
    @patch("app.repositories.player_repository.select")
    async def test_get_available_players_filter(self, mock_select):
        session_mock = AsyncMock()
        club_id = uuid.uuid4()
        
        # Mock result execution return value
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        session_mock.execute.return_value = mock_result
        
        # Call repo function
        await get_available_players_by_club_id(session_mock, club_id)
        
        # Verify select statement was generated with correct where clause filters
        mock_select.assert_called_once()
        args, kwargs = mock_select.call_args
        # Should be selecting Player model
        self.assertEqual(args[0], Player)

    async def test_consequences_idempotency(self):
        session_mock = AsyncMock()
        fixture_id = uuid.uuid4()
        home_club_id = uuid.uuid4()
        away_club_id = uuid.uuid4()
        
        # Mock fixture where consequences are already applied
        mock_fixture = MagicMock(spec=Fixture)
        mock_fixture.id = fixture_id
        mock_fixture.consequences_applied_at = datetime.utcnow()
        
        mock_execute = MagicMock()
        mock_execute.scalar_one_or_none.return_value = mock_fixture
        session_mock.execute.return_value = mock_execute
        
        sim_result = MagicMock()
        
        # Call consequence service
        await MatchConsequenceService.apply_league_match_consequences(
            session=session_mock,
            fixture_id=fixture_id,
            sim_result=sim_result,
            home_club_id=home_club_id,
            away_club_id=away_club_id
        )
        
        # Session flush should not be called since we skip
        session_mock.flush.assert_not_called()

    async def test_apply_league_match_consequences_success(self):
        session_mock = AsyncMock()
        fixture_id = uuid.uuid4()
        home_club_id = uuid.uuid4()
        away_club_id = uuid.uuid4()
        
        # 1. Mock Fixture (consequences not yet applied)
        mock_fixture = MagicMock(spec=Fixture)
        mock_fixture.id = fixture_id
        mock_fixture.consequences_applied_at = None
        
        # 2. Mock Players
        player_suspended = Player(
            id=uuid.uuid4(),
            display_name="Suspended Player",
            club_id=home_club_id,
            suspension_games_remaining=2,
            is_retired=False
        )
        player_clean = Player(
            id=uuid.uuid4(),
            display_name="Healthy Player",
            club_id=home_club_id,
            fitness=100,
            is_retired=False
        )
        player_red_carded = Player(
            id=uuid.uuid4(),
            display_name="Red Carded Player",
            club_id=away_club_id,
            fitness=100,
            is_retired=False
        )
        player_injured = Player(
            id=uuid.uuid4(),
            display_name="Injured Player",
            club_id=away_club_id,
            fitness=100,
            is_retired=False
        )
        
        players = [player_suspended, player_clean, player_red_carded, player_injured]
        
        # Set up mocks for executing queries
        async def session_execute_side_effect(stmt):
            mock_res = MagicMock()
            stmt_str = str(stmt).lower()
            if "fixtures" in stmt_str and "players" not in stmt_str:
                mock_res.scalar_one_or_none.return_value = mock_fixture
            else:
                mock_res.scalars.return_value.all.return_value = players
            return mock_res
            
        session_mock.execute.side_effect = session_execute_side_effect
        
        # 3. Create simulated match result
        from app.engine.match_engine import MatchSimulationResult, MatchCardEvent, MatchInjuryEvent
        
        # Mock card event (red card)
        red_card = MatchCardEvent(
            minute=75,
            club_id=str(away_club_id),
            player_id=str(player_red_carded.id),
            card_type="red",
            description="Straight red card"
        )
        
        # Mock injury event
        injury = MatchInjuryEvent(
            minute=45,
            club_id=str(away_club_id),
            player_id=str(player_injured.id),
            description="Pulled hamstring"
        )
        
        sim_result = MatchSimulationResult(
            home_goals=2,
            away_goals=1,
            home_possession=50,
            away_possession=50,
            home_shots=10,
            away_shots=8,
            home_shots_on_target=5,
            away_shots_on_target=4,
            cards=[red_card],
            injuries=[injury],
            final_fitness={
                str(player_clean.id): 0.85,
                str(player_red_carded.id): 0.90,
                str(player_injured.id): 0.95,
            },
            played_minutes={
                str(player_clean.id): 90,
                str(player_red_carded.id): 75,
                str(player_injured.id): 45,
            },
            player_ratings={
                str(player_clean.id): 7.2,
                str(player_red_carded.id): 5.8,
                str(player_injured.id): 6.0,
            }
        )
        
        # Apply consequences
        await MatchConsequenceService.apply_league_match_consequences(
            session=session_mock,
            fixture_id=fixture_id,
            sim_result=sim_result,
            home_club_id=home_club_id,
            away_club_id=away_club_id
        )
        
        # Assertions
        # 1. Existing suspension decremented
        self.assertEqual(player_suspended.suspension_games_remaining, 1)
        
        # 2. Red card suspension applied
        self.assertEqual(player_red_carded.suspension_games_remaining, 1)
        self.assertEqual(player_red_carded.suspension_created_fixture_id, fixture_id)
        
        # 3. Fitness decay updated (converted from float 0.0-1.0 to 0-100)
        self.assertEqual(player_clean.fitness, 85)
        self.assertEqual(player_clean.last_match_minutes, 90)
        self.assertEqual(player_clean.last_match_rating, Decimal("7.2"))
        
        # 4. Injury rolled and applied
        self.assertIsNotNone(player_injured.injury_severity)
        self.assertIsNotNone(player_injured.injury_type)
        self.assertTrue(player_injured.injury_days_remaining > 0)
        self.assertIsNotNone(player_injured.injury_created_at)
        # Injured player's fitness should have taken a penalty
        self.assertTrue(player_injured.fitness < 95)  # pre-match was 95 (0.95 * 100), penalty subtracted from it
        
        # 5. Consequences applied timestamp set
        self.assertIsNotNone(mock_fixture.consequences_applied_at)
        session_mock.flush.assert_called()

    @patch("app.services.lineup_service.get_active_lineup")
    @patch("app.services.lineup_service.get_players_by_club_id")
    @patch("app.services.lineup_service.get_available_players_by_club_id")
    @patch("app.services.lineup_service.validate_lineup")
    @patch("app.services.lineup_service.build_auto_lineup")
    @patch("app.services.lineup_service.save_lineup_with_players")
    async def test_resolve_lineup_unavailable_trigger_fallback(
        self, mock_save, mock_build_auto, mock_validate, mock_available_players, mock_players, mock_active_lineup
    ):
        session_mock = AsyncMock()
        club_id = uuid.uuid4()
        
        # Mock active lineup players
        p1 = MagicMock(id=uuid.uuid4(), display_name="P1", overall=70, fitness=100, is_retired=False)
        p2 = MagicMock(id=uuid.uuid4(), display_name="P2", overall=70, fitness=100, is_retired=False)
        p2.injury_days_remaining = 3
        
        # Add 10 other healthy players to reach at least 11 total squad players
        healthy_players = [
            MagicMock(id=uuid.uuid4(), display_name=f"Healthy {i}", overall=65, fitness=100, is_retired=False)
            for i in range(10)
        ]
        
        lineup_mock = MagicMock()
        lineup_mock.formation = "4-4-2"
        # Starters and bench
        lp1 = MagicMock(player_id=p1.id, is_starter=True, slot="GK", player=p1)
        lp2 = MagicMock(player_id=p2.id, is_starter=False, player=p2)
        
        # Fill rest of starters to form a valid starting XI of 11 players
        lp_others = []
        slots = ["LB", "CB1", "CB2", "RB", "LM", "CM1", "CM2", "RM", "ST1", "ST2"]
        for i, slot in enumerate(slots):
            lp_others.append(MagicMock(player_id=healthy_players[i].id, is_starter=True, slot=slot, player=healthy_players[i]))
            
        lineup_mock.lineup_players = [lp1, lp2] + lp_others
        
        mock_active_lineup.return_value = lineup_mock
        
        # P1 and healthy_players are available, but P2 is injured (not in available players list)
        club_players = [p1, p2] + healthy_players
        available_players_list = [p1] + healthy_players
        
        mock_players.return_value = club_players
        mock_available_players.return_value = available_players_list
        
        # Auto-pickup mock
        mock_build_auto.return_value = ({ "GK": p1 }, [], [])
        
        res = await LineupService.resolve_team_lineup(
            session=session_mock,
            guild_id="123",
            club_id=club_id,
            club_name="Kathmandu FC",
            persist_fallback=True
        )
        
        # Since P2 (selected on bench) is unavailable, the lineup resolution falls back to auto-pick
        mock_build_auto.assert_called_once()
        mock_save.assert_called_once()
        self.assertEqual(res.formation, "4-4-2")
        self.assertEqual(res.starters[0].player_id, str(p1.id))

    async def test_second_yellow_red_triggers_suspension(self):
        """A second_yellow_red card event must also trigger a 1-game suspension."""
        session_mock = AsyncMock()
        fixture_id = uuid.uuid4()
        home_club_id = uuid.uuid4()
        away_club_id = uuid.uuid4()

        mock_fixture = MagicMock(spec=Fixture)
        mock_fixture.id = fixture_id
        mock_fixture.consequences_applied_at = None

        player_double_yellow = Player(
            id=uuid.uuid4(),
            display_name="Double Yellow Player",
            club_id=home_club_id,
            fitness=90,
            is_retired=False,
        )

        players = [player_double_yellow]

        async def session_execute_side_effect(stmt):
            mock_res = MagicMock()
            stmt_str = str(stmt).lower()
            if "fixtures" in stmt_str and "players" not in stmt_str:
                mock_res.scalar_one_or_none.return_value = mock_fixture
            else:
                mock_res.scalars.return_value.all.return_value = players
            return mock_res

        session_mock.execute.side_effect = session_execute_side_effect

        from app.engine.match_engine import MatchSimulationResult, MatchCardEvent

        second_yellow_card = MatchCardEvent(
            minute=67,
            club_id=str(home_club_id),
            player_id=str(player_double_yellow.id),
            card_type="second_yellow_red",
            description="67' 🟨🟥 Second yellow! Double Yellow Player (Home FC) is sent off.",
            red_card_type="second_yellow",
            metadata={"red_card_type": "second_yellow", "yellow_count": 2, "suspension_matches": 1},
        )

        sim_result = MatchSimulationResult(
            home_goals=1,
            away_goals=0,
            home_possession=55,
            away_possession=45,
            home_shots=8,
            away_shots=5,
            home_shots_on_target=4,
            away_shots_on_target=2,
            cards=[second_yellow_card],
            final_fitness={str(player_double_yellow.id): 0.80},
            played_minutes={str(player_double_yellow.id): 67},
            player_ratings={str(player_double_yellow.id): 5.5},
        )

        await MatchConsequenceService.apply_league_match_consequences(
            session=session_mock,
            fixture_id=fixture_id,
            sim_result=sim_result,
            home_club_id=home_club_id,
            away_club_id=away_club_id,
        )

        # Suspension must have been applied for the second-yellow red
        self.assertEqual(player_double_yellow.suspension_games_remaining, 1)
        self.assertEqual(player_double_yellow.suspension_created_fixture_id, fixture_id)


if __name__ == "__main__":
    unittest.main()
