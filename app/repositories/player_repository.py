from sqlalchemy.ext.asyncio import AsyncSession
from app.models.player import Player

async def bulk_create_players(session: AsyncSession, players: list[Player]) -> None:
    """
    Bulk create player records in a single operation.
    """
    session.add_all(players)
