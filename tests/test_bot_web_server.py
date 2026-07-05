import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from apps.discord_bot.main import ElevenBossBot

class TestBotWebServer(unittest.IsolatedAsyncioTestCase):
    async def test_web_server_health_check(self):
        # Instantiate bot
        bot = ElevenBossBot()
        bot._connection = MagicMock()
        bot._connection.user = MagicMock()
        bot._connection.user.name = "TestBot"
        bot._connection.close = AsyncMock()
        
        # Mock TCPSite to avoid port binding in tests
        with patch("aiohttp.web.TCPSite") as MockTCPSite:
            mock_site = MagicMock()
            mock_site.start = AsyncMock()
            mock_site.stop = AsyncMock()
            MockTCPSite.return_value = mock_site
            
            await bot._start_web_server(28591)
            
            # Verify runner and site were created
            self.assertTrue(hasattr(bot, "_web_runner"))
            self.assertTrue(hasattr(bot, "_web_site"))
            
            # Retrieve application and test the handler
            app = bot._web_runner.app
            self.assertIsNotNone(app)
            
            # Verify routes are registered
            routes = list(app.router.routes())
            # 2 paths (/, /health) * 2 methods (GET, HEAD) = 4 routes
            self.assertEqual(len(routes), 4)
            
            # Call the handler directly
            handler = routes[0].handler
            request_mock = MagicMock()
            response = await handler(request_mock)
            
            # Verify response content
            self.assertEqual(response.status, 200)
            self.assertEqual(response.content_type, "application/json")
            
            # Clean up
            await bot.close()
