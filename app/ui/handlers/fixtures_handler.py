"""
Fixtures Handler — UI-layer orchestration for fixture viewing interactions.

Bridges the fixture service and the UI renderer/layout.
Handles session validation.

Fixture GENERATION is handled inside league_service.start_league().
No generate handler exists here — it is not a user-facing command.
"""

import logging
import discord

from app.ui.handlers.session import ui_session_manager
from app.services.fixture_service import (
    get_current_week_fixtures,
    get_fixtures_for_week,
)
from app.ui.renderers.fixture_renderer import render_fixture_week_view
from app.ui.layouts.fixtures import build_fixture_empty_state_layout
from app.ui.components import V2View

logger = logging.getLogger("app.ui.handlers.fixtures_handler")


async def handle_view_current_week_fixtures(
    guild_id: int,
    user: discord.Member,
    nonce: str,
) -> V2View:
    """
    Handles /fixtures view and the 'Current Week' navigation button.

    Loads the active season's current week and returns a fixture list screen.
    Shows a safe empty-state screen if fixtures are missing or the league hasn't started.
    """
    valid, err_msg = ui_session_manager.validate_session(nonce, user.id)
    if not valid:
        raise ValueError(err_msg)

    result = await get_current_week_fixtures(guild_id)

    if result.success:
        logger.info(
            f"fixtures_viewed: guild_id={guild_id}, user_id={user.id}, "
            f"week={result.selected_week}"
        )
        return render_fixture_week_view(result, nonce)

    logger.info(
        f"fixtures_view_failed: guild_id={guild_id}, user_id={user.id}, "
        f"code={result.code}"
    )
    return build_fixture_empty_state_layout(
        message=f"❌ {result.message}",
        nonce=nonce,
        league_name=result.league_name,
        season_number=result.season_number,
    )


async def handle_view_week_fixtures(
    guild_id: int,
    user: discord.Member,
    nonce: str,
    week: int,
) -> V2View:
    """
    Handles /fixtures week and the Prev/Next/numeric week navigation buttons.

    Validates the week is within the season's valid range.
    Returns the fixture list for the selected week, or a safe error screen.
    """
    valid, err_msg = ui_session_manager.validate_session(nonce, user.id)
    if not valid:
        raise ValueError(err_msg)

    result = await get_fixtures_for_week(guild_id, week)

    if result.success:
        logger.info(
            f"fixtures_week_viewed: guild_id={guild_id}, user_id={user.id}, "
            f"week={week}"
        )
        return render_fixture_week_view(result, nonce)

    logger.info(
        f"fixtures_week_view_failed: guild_id={guild_id}, user_id={user.id}, "
        f"week={week}, code={result.code}"
    )
    return build_fixture_empty_state_layout(
        message=f"❌ {result.message}",
        nonce=nonce,
        league_name=result.league_name,
        season_number=result.season_number,
    )
