# app/repositories/lineup_repository.py

import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.models.lineup import Lineup, LineupPlayer

async def get_active_lineup(session: AsyncSession, club_id: uuid.UUID) -> Lineup | None:
    """
    Fetch the active lineup for a club, including its players.
    """
    stmt = (
        select(Lineup)
        .where(
            Lineup.club_id == club_id,
            Lineup.is_active == True
        )
        .options(
            selectinload(Lineup.lineup_players).selectinload(LineupPlayer.player)
        )
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

async def deactivate_all_lineups(session: AsyncSession, club_id: uuid.UUID) -> None:
    """
    Deactivates all active lineups for a club.
    """
    stmt = select(Lineup).where(
        Lineup.club_id == club_id,
        Lineup.is_active == True
    )
    result = await session.execute(stmt)
    active_lineups = result.scalars().all()
    for lineup in active_lineups:
        lineup.is_active = False

async def save_lineup_with_players(
    session: AsyncSession,
    guild_id: int | str,
    club_id: uuid.UUID,
    formation: str,
    starters: dict[str, uuid.UUID],  # slot -> player_id
    bench: list[uuid.UUID]            # list of player_ids
) -> Lineup:
    """
    Saves a new active lineup and its players.
    This deactivates any existing active lineup in the same transaction.
    """
    # 1. Deactivate old lineups
    await deactivate_all_lineups(session, club_id)
    
    # 2. Create new lineup
    new_lineup = Lineup(
        guild_id=str(guild_id),
        club_id=club_id,
        formation=formation,
        is_active=True
    )
    session.add(new_lineup)
    await session.flush()  # Generate the lineup ID
    
    # 3. Create lineup players
    lineup_players = []
    
    # Add starters
    for sort_order, (slot, player_id) in enumerate(starters.items()):
        lp = LineupPlayer(
            guild_id=str(guild_id),
            lineup_id=new_lineup.id,
            player_id=player_id,
            slot=slot,
            role=slot,  # For V1, role can just match slot
            is_starter=True,
            sort_order=sort_order
        )
        lineup_players.append(lp)
        
    # Add bench
    for sort_order, player_id in enumerate(bench):
        slot_name = f"SUB_{sort_order + 1}"
        lp = LineupPlayer(
            guild_id=str(guild_id),
            lineup_id=new_lineup.id,
            player_id=player_id,
            slot=slot_name,
            role="SUB",
            is_starter=False,
            sort_order=sort_order
        )
        lineup_players.append(lp)
        
    session.add_all(lineup_players)
    return new_lineup
