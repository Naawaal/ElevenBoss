# tests/test_game_loop_orchestrator.py

import pytest
from unittest.mock import AsyncMock, patch, MagicMock, ANY
from datetime import datetime
from app.services.game_loop_orchestrator import GameLoopOrchestrator, AutomationStepResult
from app.models.guild_config import GuildConfig

@pytest.mark.asyncio
async def test_run_due_checks_scans_guilds():
    # Mock bot with list of guilds
    mock_bot = MagicMock()
    mock_guild1 = MagicMock()
    mock_guild1.id = 1111
    mock_guild2 = MagicMock()
    mock_guild2.id = 2222
    mock_bot.guilds = [mock_guild1, mock_guild2]
    
    orchestrator = GameLoopOrchestrator(mock_bot)
    
    with patch.object(orchestrator, "run_guild_check", return_value=AsyncMock()) as mock_run_guild_check:
        res = await orchestrator.run_due_checks()
        assert res.success
        assert len(res.guild_results) == 2
        assert mock_run_guild_check.call_count == 2
        mock_run_guild_check.assert_any_call(1111, ANY)

@pytest.mark.asyncio
@patch("app.services.game_loop_orchestrator.get_session")
async def test_run_guild_check_updates_status(mock_get_session):
    mock_session = AsyncMock()
    mock_get_session.return_value.__aenter__.return_value = mock_session
    
    # Mock config
    config = GuildConfig(
        guild_id="1111",
        automation_status="idle"
    )
    
    orchestrator = GameLoopOrchestrator()
    
    # Mock sub-steps
    step_lifecycle = AutomationStepResult(success=True, code="skipped_not_due", message="No start.")
    step_matchday = AutomationStepResult(success=True, code="skipped_disabled", message="Disabled.")
    
    with patch("app.services.game_loop_orchestrator.get_or_create_guild_config", return_value=config), \
         patch.object(orchestrator, "run_league_lifecycle_check", return_value=step_lifecycle), \
         patch.object(orchestrator, "run_matchday_due_check", return_value=step_matchday):
         
        res = await orchestrator.run_guild_check(1111)
        assert res.success
        assert res.guild_id == 1111
        # config last_automation_status gets set
        assert config.last_automation_status == "success"
