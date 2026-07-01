import unittest
import uuid
import asyncio
from unittest.mock import MagicMock
mock_loop = MagicMock()
mock_loop.create_future.return_value = MagicMock()
asyncio.get_running_loop = MagicMock(return_value=mock_loop)

from datetime import datetime, timedelta
from app.ui.custom_ids import encode_custom_id, decode_custom_id, CustomId
from app.ui.handlers.session import ui_session_manager, UiSession
from app.ui.components import container, section, text_display, separator, action_row, button, select_menu, V2View
from app.ui.layouts.locker_room import build_locker_room_layout, build_help_layout
from app.ui.layouts.club_dashboard import build_club_dashboard_layout
from app.ui.layouts.squad import build_squad_layout, PAGE_SIZE
from app.ui.layouts.player_detail import build_player_detail_layout, build_player_match_select_layout

class TestCustomIds(unittest.TestCase):
    def test_encode_decode_success(self):
        encoded = encode_custom_id("locker", "view", "squad", "abc123")
        self.assertEqual(encoded, "fcm:v1:locker:view:squad:abc123")
        
        decoded = decode_custom_id(encoded)
        self.assertEqual(decoded.scope, "locker")
        self.assertEqual(decoded.action, "view")
        self.assertEqual(decoded.target, "squad")
        self.assertEqual(decoded.nonce, "abc123")

    def test_malformed_rejection(self):
        with self.assertRaises(ValueError):
            decode_custom_id("fcm:v1:locker:view") # Too few parts
        with self.assertRaises(ValueError):
            decode_custom_id("other:v1:locker:view:squad:abc") # Wrong namespace
            
    def test_unsupported_version_rejection(self):
        with self.assertRaises(ValueError):
            decode_custom_id("fcm:v2:locker:view:squad:abc") # Unsupported version

    def test_unknown_scope_rejection(self):
        with self.assertRaises(ValueError):
            encode_custom_id("unknown_scope", "view", "squad", "abc")

    def test_unknown_action_rejection(self):
        with self.assertRaises(ValueError):
            encode_custom_id("locker", "invalid_action", "squad", "abc")

    def test_length_safety(self):
        long_target = "a" * 80
        with self.assertRaises(ValueError):
            # Combined length should exceed 100
            encode_custom_id("locker", "view", long_target, "abc")
            
class TestUiSession(unittest.TestCase):
    def setUp(self):
        ui_session_manager._sessions.clear()

    def test_session_creation(self):
        session = ui_session_manager.create_session(discord_user_id=123, guild_id=456)
        self.assertEqual(len(session.session_id), 6)
        self.assertEqual(session.discord_user_id, 123)
        self.assertEqual(session.guild_id, 456)
        
    def test_session_validation_ownership(self):
        session = ui_session_manager.create_session(discord_user_id=123, guild_id=456)
        
        # Valid owner
        valid, msg = ui_session_manager.validate_session(session.session_id, 123)
        self.assertTrue(valid)
        
        # Invalid owner
        valid, msg = ui_session_manager.validate_session(session.session_id, 999)
        self.assertFalse(valid)
        self.assertIn("own", msg)

    def test_session_expiry(self):
        session = ui_session_manager.create_session(discord_user_id=123, guild_id=456)
        # Set expiry to past
        session.expires_at = datetime.utcnow() - timedelta(seconds=1)
        
        valid, msg = ui_session_manager.validate_session(session.session_id, 123)
        self.assertFalse(valid)
        self.assertIn("expired", msg)

    def test_session_cleanup(self):
        session1 = ui_session_manager.create_session(discord_user_id=123, guild_id=456)
        session2 = ui_session_manager.create_session(discord_user_id=123, guild_id=456)
        session1.expires_at = datetime.utcnow() - timedelta(seconds=1)
        
        ui_session_manager.cleanup_expired()
        self.assertIsNone(ui_session_manager.get_session(session1.session_id))
        self.assertIsNotNone(ui_session_manager.get_session(session2.session_id))

class TestUiComponents(unittest.TestCase):
    def test_raw_payload_builders(self):
        btn = button("Test", "fcm:v1:locker:view:squad:abc", style=2)
        self.assertEqual(btn["type"], 2)
        self.assertEqual(btn["style"], 2)
        self.assertEqual(btn["label"], "Test")
        
        sel = select_menu("fcm:v1:player:view:select:abc", [{"label": "P", "value": "1"}])
        self.assertEqual(sel["type"], 3)
        self.assertEqual(sel["options"][0]["label"], "P")
        
        sep = separator(divider=True, spacing=2)
        self.assertEqual(sep["type"], 14)
        self.assertTrue(sep["divider"])
        self.assertEqual(sep["spacing"], 2)

        sec = section("Hello", accessory={"type": 2, "label": "Btn"})
        self.assertEqual(sec["type"], 9)
        self.assertIn("components", sec)
        self.assertEqual(sec["components"][0]["type"], 10)
        self.assertEqual(sec["components"][0]["content"], "Hello")
        self.assertEqual(sec["accessory"]["label"], "Btn")


class TestUiLayouts(unittest.TestCase):
    def test_locker_room_payload(self):
        data = {
            "club_name": "Kathmandu FC",
            "discord_user_id": 123,
            "squad_size": 25,
            "average_overall": 71.4,
            "best_player_name": "James Smith",
            "best_player_ovr": 78,
            "budget": 10000000,
            "league_status": "No Active League",
            "next_suggested_action": "Do something"
        }
        view = build_locker_room_layout(data, "abc123")
        self.assertTrue(isinstance(view, V2View))
        self.assertTrue(view.has_components_v2())
        
        payload = view.to_components()
        self.assertEqual(payload[0]["type"], 17) # Container
        self.assertEqual(payload[1]["type"], 1)  # Action Row (squad, players, dashboard)
        self.assertEqual(payload[2]["type"], 1)  # Action Row (refresh, help, close)

    def test_club_dashboard_payload(self):
        data = {
            "club_name": "Kathmandu FC",
            "discord_user_id": 123,
            "squad_size": 25,
            "average_overall": 71.4,
            "best_player_name": "James Smith",
            "best_player_ovr": 78,
            "highest_pot_name": "John Johnson",
            "highest_pot_val": 88,
            "budget": 10000000,
            "stadium_capacity": 10000,
            "league_status": "No Active League"
        }
        view = build_club_dashboard_layout(data, "abc123")
        payload = view.to_components()
        self.assertEqual(payload[0]["type"], 17)
        self.assertEqual(payload[1]["type"], 1)

    def test_squad_payload_and_pagination(self):
        players = [
            {"id": str(i), "display_name": f"Player {i}", "position": "CM", "age": 22, "overall": 70, "potential": 80, "fitness": 100, "morale": 75}
            for i in range(25)
        ]
        
        # Page 1
        view1 = build_squad_layout("Kathmandu FC", players, page=1, nonce="abc123")
        payload1 = view1.to_components()
        self.assertEqual(payload1[0]["type"], 17) # Stats Table Container
        self.assertEqual(payload1[1]["type"], 1)  # Player Select menu Action Row
        self.assertEqual(payload1[2]["type"], 1)  # Navigation buttons Action Row
        
        # Verify dropdown has 8 players (PAGE_SIZE)
        dropdown = payload1[1]["components"][0]
        self.assertEqual(len(dropdown["options"]), 8)
        
        # Verify Prev is disabled, Next is enabled
        nav_buttons = payload1[2]["components"]
        self.assertTrue(nav_buttons[0]["disabled"]) # Prev
        self.assertFalse(nav_buttons[1]["disabled"]) # Next
        
        # Page 4 (Last page, since 25 / 8 = 4 pages)
        view4 = build_squad_layout("Kathmandu FC", players, page=4, nonce="abc123")
        payload4 = view4.to_components()
        # Page 4 should have 1 player (25 - 24 = 1)
        dropdown4 = payload4[1]["components"][0]
        self.assertEqual(len(dropdown4["options"]), 1)
        
        # Verify Prev is enabled, Next is disabled
        nav_buttons4 = payload4[2]["components"]
        self.assertFalse(nav_buttons4[0]["disabled"]) # Prev
        self.assertTrue(nav_buttons4[1]["disabled"]) # Next

    def test_player_detail_payload(self):
        player = {
            "id": "player_uuid",
            "display_name": "James Smith",
            "position": "CM",
            "age": 24,
            "overall": 72,
            "potential": 80,
            "fitness": 100,
            "sharpness": 50,
            "morale": 75,
            "preferred_foot": "Right",
            "weak_foot": 3,
            "skill_moves": 3,
            "traits": {"list": ["clinical_finisher"]},
            "value": 5000000,
            "wage": 25000
        }
        view = build_player_detail_layout(player, "abc123")
        payload = view.to_components()
        self.assertEqual(payload[0]["type"], 17)
        self.assertEqual(payload[1]["type"], 1)

    def test_player_matches_payload(self):
        matches = [
            {"id": "1", "display_name": "James Smith", "position": "CM", "overall": 70, "potential": 80},
            {"id": "2", "display_name": "James Smith", "position": "ST", "overall": 75, "potential": 85}
        ]
        view = build_player_match_select_layout("James", matches, "abc123")
        payload = view.to_components()
        self.assertEqual(payload[0]["type"], 17) # Container
        self.assertEqual(payload[1]["type"], 1)  # Dropdown menu Row
        self.assertEqual(payload[2]["type"], 1)  # Back/Close Row
