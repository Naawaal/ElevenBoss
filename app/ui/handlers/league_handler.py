import logging
import discord
from app.db.session import get_session
from app.models.guild_config import GuildConfig
from sqlalchemy.future import select
from app.ui.handlers.session import ui_session_manager
from app.services.league_service import get_league_status, join_league, start_league
from app.services.standings_service import get_table
from app.ui.renderers.league_renderer import render_league_dashboard
from app.ui.renderers.table_renderer import render_table

logger = logging.getLogger("app.ui.handlers.league_handler")

async def check_admin_permission(guild_id: int | str, user: discord.Member) -> bool:
    """
    Checks if the user has Discord Administrator permissions or has the configured game admin role.
    """
    if user.guild_permissions.administrator:
        return True
        
    try:
        async with get_session() as session:
            stmt = select(GuildConfig).where(GuildConfig.guild_id == str(guild_id))
            result = await session.execute(stmt)
            config = result.scalar_one_or_none()
            if config and config.admin_role_id:
                role_id = int(config.admin_role_id)
                if any(r.id == role_id for r in user.roles):
                    return True
    except Exception as e:
        logger.error(f"Failed to check admin role permission: {e}", exc_info=e)
        
    return False

async def handle_open_league_dashboard(guild_id: int, user: discord.Member, nonce: str | None = None, banner: str | None = None):
    """
    Retrieves the league status and returns the League Dashboard V2View.
    """
    if nonce:
        valid, err_msg = ui_session_manager.validate_session(nonce, user.id)
        if not valid:
            raise ValueError(err_msg)
    else:
        session = ui_session_manager.create_session(user.id, guild_id)
        nonce = session.session_id
        
    status_res = await get_league_status(guild_id)
    if not status_res.success:
        logger.info(f"ui_league_status_view_failed: guild_id={guild_id}, reason={status_res.message}")
        raise ValueError(status_res.message)
        
    is_admin = await check_admin_permission(guild_id, user)
    logger.info(f"league_status_viewed: guild_id={guild_id}, user_id={user.id}, session_id={nonce}")
    return render_league_dashboard(status_res, nonce, is_admin, banner=banner, has_image=True)

async def handle_join_league(guild_id: int, user: discord.Member, nonce: str):
    """
    Processes the request to join the league and refreshes the league dashboard view.
    """
    valid, err_msg = ui_session_manager.validate_session(nonce, user.id)
    if not valid:
        raise ValueError(err_msg)
        
    logger.info(f"league_join_started: guild_id={guild_id}, user_id={user.id}")
    res = await join_league(guild_id, user.id)
    if not res.success:
        logger.info(f"league_join_failed: guild_id={guild_id}, user_id={user.id}, reason={res.message}")
        raise ValueError(res.message)
        
    logger.info(f"league_joined: guild_id={guild_id}, user_id={user.id}, league_id={res.league_id}")
    
    # Return updated dashboard
    status_res = await get_league_status(guild_id)
    is_admin = await check_admin_permission(guild_id, user)
    return render_league_dashboard(status_res, nonce, is_admin, banner=f"✅ {res.message}", has_image=True)

async def handle_start_league(guild_id: int, user: discord.Member, nonce: str):
    """
    Starts the league season (generates bot clubs, standings, season) and refreshes dashboard.
    """
    valid, err_msg = ui_session_manager.validate_session(nonce, user.id)
    if not valid:
        raise ValueError(err_msg)
        
    # Permission validation
    is_admin = await check_admin_permission(guild_id, user)
    if not is_admin:
        logger.info(f"league_interaction_rejected: reason=permission_denied, user_id={user.id}, action=start_league")
        raise ValueError("You do not have permission to start the league. Only server administrators or game admins can do this.")
        
    logger.info(f"league_start_started: guild_id={guild_id}, user_id={user.id}")
    res = await start_league(guild_id)
    if not res.success:
        logger.info(f"league_start_failed: guild_id={guild_id}, reason={res.message}")
        raise ValueError(res.message)
        
    logger.info(f"league_started: guild_id={guild_id}, league_id={res.league_id}, bot_clubs={res.bot_clubs}")

    # Return updated dashboard with fixture stats in the banner
    status_res = await get_league_status(guild_id)
    banner_content = (
        f"✅ **League started — fixtures ready!**\n"
        f"🏆 **League:** `{res.league_name}`\n"
        f"👥 **Human Clubs:** `{res.human_clubs}`  |  🤖 **Bot Clubs:** `{res.bot_clubs}`\n"
        f"📆 **Total Weeks:** `{res.total_weeks}`  |  🗂️ **Fixtures:** `{res.total_fixtures}`\n"
        f"▶️ **Current Week:** Week `{res.current_week}`\n"
        f"→ Use `/fixtures view` to see Week 1."
    )
    return render_league_dashboard(status_res, nonce, is_admin, banner=banner_content, has_image=True)


async def handle_view_table(guild_id: int, user: discord.Member, nonce: str):
    """
    Fetches standings table and returns the table V2View.
    """
    valid, err_msg = ui_session_manager.validate_session(nonce, user.id)
    if not valid:
        raise ValueError(err_msg)
        
    standings = await get_table(guild_id)
    if not standings:
        logger.info(f"league_table_view_failed: guild_id={guild_id}, reason=no_active_season")
        raise ValueError("The standings table is only available once the league has started and is active.")
        
    from app.services.club_service import get_manager_club_summary
    summary = await get_manager_club_summary(guild_id, user.id)
    manager_club_id = summary["club_id"] if summary else None
    
    logger.info(f"league_table_viewed: guild_id={guild_id}, user_id={user.id}")
    return render_table(standings, nonce, manager_club_id=manager_club_id, has_image=True)

async def handle_refresh_table(guild_id: int, user: discord.Member, nonce: str):
    """
    Refreshes the standings table.
    """
    return await handle_view_table(guild_id, user, nonce)
