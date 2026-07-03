import logging
import uuid
from sqlalchemy.future import select

from app.db.session import get_session
from app.repositories.season_snapshot_repository import get_season_snapshot
from app.ui.renderers.season_renderer import render_season_summary
from app.ui.handlers.session import ui_session_manager
from app.models.club import Club

logger = logging.getLogger("app.ui.handlers.season_handler")

async def handle_view_season_summary(season_id: uuid.UUID, user_id: int, nonce: str):
    """
    Handles loading the season snapshot data and rendering the Season Summary view.
    """
    valid, err_msg = ui_session_manager.validate_session(nonce, user_id)
    if not valid:
        raise ValueError(err_msg)

    async with get_session() as session:
        snapshot = await get_season_snapshot(session, season_id)
        if not snapshot:
            raise ValueError("Season summary/snapshot not found.")

        # Resolve champion and runner-up names
        champion_name = "N/A"
        runner_up_name = "N/A"
        
        if snapshot.champion_club_id:
            res_c = await session.execute(select(Club.name).where(Club.id == snapshot.champion_club_id))
            champion_name = res_c.scalar() or "N/A"
            
        if snapshot.runner_up_club_id:
            res_r = await session.execute(select(Club.name).where(Club.id == snapshot.runner_up_club_id))
            runner_up_name = res_r.scalar() or "N/A"

        snapshot_data = {
            "season_number": snapshot.season_number,
            "champion_name": champion_name,
            "runner_up_name": runner_up_name,
            "total_matches": snapshot.total_matches,
            "total_goals": snapshot.total_goals,
            "table_rows": snapshot.final_table_json.get("rows", [])
        }

    return render_season_summary(snapshot_data, nonce)
