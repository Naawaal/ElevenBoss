import unittest
from unittest.mock import patch, AsyncMock, MagicMock
import uuid
from app.services.standings_service import initialize_standings, get_table
from app.models.standing import LeagueStanding

class TestStandingsService(unittest.IsolatedAsyncioTestCase):
    
    @patch("app.services.standings_service.create_initial_standing")
    async def test_initialize_standings(self, mock_create):
        session_mock = AsyncMock()
        guild_id = "12345"
        season_id = uuid.uuid4()
        club_ids = [uuid.uuid4() for _ in range(3)]
        
        mock_create.side_effect = lambda s, g, se, c: LeagueStanding(
            guild_id=str(g),
            season_id=se,
            club_id=c,
            played=0,
            wins=0,
            draws=0,
            losses=0,
            goals_for=0,
            goals_against=0,
            goal_difference=0,
            points=0
        )
        
        standings = await initialize_standings(session_mock, guild_id, season_id, club_ids)
        
        self.assertEqual(len(standings), 3)
        self.assertEqual(mock_create.call_count, 3)
        for s, cid in zip(standings, club_ids):
            self.assertEqual(s.club_id, cid)
            self.assertEqual(s.played, 0)
            self.assertEqual(s.wins, 0)
            self.assertEqual(s.points, 0)
            self.assertEqual(s.goal_difference, 0)

    @patch("app.services.standings_service.get_session")
    @patch("app.services.standings_service.get_table_for_active_season")
    async def test_get_table_returns_sorted_rows(self, mock_repo_get_table, mock_get_session):
        session_mock = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = session_mock
        
        # Mock standings returned by repository
        mock_standings = [MagicMock(spec=LeagueStanding) for _ in range(2)]
        mock_repo_get_table.return_value = mock_standings
        
        result = await get_table("12345")
        
        self.assertEqual(result, mock_standings)
        mock_repo_get_table.assert_called_once_with(session_mock, "12345")

    async def test_get_ranked_table(self):
        from app.repositories.standing_repository import get_ranked_table
        session_mock = AsyncMock()
        guild_id = "12345"
        season_id = uuid.uuid4()
        
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        session_mock.execute.return_value = result_mock
        
        table = await get_ranked_table(session_mock, guild_id, season_id)
        self.assertEqual(table, [])
        session_mock.execute.assert_called_once()

