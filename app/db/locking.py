# app/db/locking.py

from typing import Iterable
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

def maybe_for_update(stmt, session: AsyncSession):
    """
    Applies .with_for_update() to a statement only if the database dialect is not SQLite.
    Allows local testing on SQLite while ensuring transaction locks on PostgreSQL.
    """
    bind = session.bind
    dialect_name = bind.dialect.name if bind else "postgresql"

    if dialect_name == "sqlite":
        return stmt

    return stmt.with_for_update()

def sort_club_ids_for_locking(club_ids: Iterable[uuid.UUID]) -> list[uuid.UUID]:
    """
    Sorts club IDs deterministically by their string representations to prevent deadlocks
    when locking multiple club rows.
    """
    return sorted(club_ids, key=str)
