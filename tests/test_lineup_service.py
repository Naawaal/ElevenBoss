# tests/test_lineup_service.py

import unittest
from unittest.mock import patch, AsyncMock, MagicMock
import uuid
from app.services.lineup_service import LineupService

class TestLineupService(unittest.IsolatedAsyncioTestCase):
    @patch("app.services.lineup_service.get_session")
    @patch("app.services.lineup_service.get_manager_by_discord_id")
    @patch("app.services.lineup_service.get_club_by_manager_id")
    @patch("app.services.lineup_service.get_players_by_club_id")
    @patch("app.services.lineup_service.get_active_lineup")
    async def test_get_lineup_screen_data_success(
        self, mock_active_lineup, mock_players, mock_club, mock_manager, mock_get_session
    ):
        # Mock db session context manager
        session_mock = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = session_mock
        
        # Setup mock entities
        club_id = uuid.uuid4()
        manager_mock = MagicMock()
        manager_mock.club_id = club_id
        mock_manager.return_value = manager_mock
        
        club_mock = MagicMock()
        club_mock.name = "Kathmandu FC"
        club_mock.id = club_id
        mock_club.return_value = club_mock
        
        mock_players.return_value = []
        mock_active_lineup.return_value = None
        
        # Run service method
        res = await LineupService.get_lineup_screen_data(guild_id="12345", discord_user_id="67890")
        
        self.assertTrue(res.success)
        self.assertEqual(res.club_name, "Kathmandu FC")
        self.assertEqual(res.formation, "4-4-2")
        self.assertEqual(res.starters, {})
        self.assertEqual(res.bench, [])

    @patch("app.services.lineup_service.get_session")
    @patch("app.services.lineup_service.get_manager_by_discord_id")
    @patch("app.services.lineup_service.get_club_by_manager_id")
    @patch("app.services.lineup_service.get_players_by_club_id")
    async def test_preview_auto_lineup_success(
        self, mock_players, mock_club, mock_manager, mock_get_session
    ):
        session_mock = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = session_mock
        
        club_id = uuid.uuid4()
        manager_mock = MagicMock()
        manager_mock.club_id = club_id
        mock_manager.return_value = manager_mock
        
        club_mock = MagicMock()
        club_mock.name = "Kathmandu FC"
        club_mock.id = club_id
        mock_club.return_value = club_mock
        
        # Provide a GK and 10 CMs to form a lineup
        p_list = [
            MagicMock(id=uuid.uuid4(), position="GK", overall=75, fitness=100, is_retired=False)
        ]
        for i in range(15):
            p_list.append(
                MagicMock(id=uuid.uuid4(), position="CM", overall=70, fitness=100, is_retired=False)
            )
        mock_players.return_value = p_list
        
        res = await LineupService.preview_auto_lineup(guild_id="12345", discord_user_id="67890", formation="4-4-2")
        
        self.assertTrue(res.success)
        self.assertEqual(len(res.starters), 11)
        self.assertEqual(len(res.bench), 5) # 16 total players - 11 starters = 5 bench

    @patch("app.services.lineup_service.get_session")
    @patch("app.services.lineup_service.get_manager_by_discord_id")
    @patch("app.services.lineup_service.get_club_by_manager_id")
    @patch("app.services.lineup_service.get_players_by_club_id")
    @patch("app.services.lineup_service.save_lineup_with_players")
    async def test_save_lineup_success(
        self, mock_save, mock_players, mock_club, mock_manager, mock_get_session
    ):
        session_mock = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = session_mock
        
        club_id = uuid.uuid4()
        manager_mock = MagicMock()
        manager_mock.club_id = club_id
        mock_manager.return_value = manager_mock
        
        club_mock = MagicMock()
        club_mock.name = "Kathmandu FC"
        club_mock.id = club_id
        mock_club.return_value = club_mock
        
        # 15 players belonging to the club
        p_ids = [uuid.uuid4() for _ in range(15)]
        p_list = [
            MagicMock(id=pid, position="CM", overall=70, fitness=100, is_retired=False)
            for pid in p_ids
        ]
        mock_players.return_value = p_list
        
        starters = {
            "GK": str(p_ids[0]),
            "LB": str(p_ids[1]),
            "CB1": str(p_ids[2]),
            "CB2": str(p_ids[3]),
            "RB": str(p_ids[4]),
            "LM": str(p_ids[5]),
            "CM1": str(p_ids[6]),
            "CM2": str(p_ids[7]),
            "RM": str(p_ids[8]),
            "ST1": str(p_ids[9]),
            "ST2": str(p_ids[10])
        }
        bench = [str(p_ids[11]), str(p_ids[12]), str(p_ids[13])]
        
        res = await LineupService.save_lineup(
            guild_id="123",
            discord_user_id="456",
            formation="4-4-2",
            starters=starters,
            bench=bench
        )
        
        self.assertTrue(res.success)
        mock_save.assert_called_once()

if __name__ == "__main__":
    unittest.main()
