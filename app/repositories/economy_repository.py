# app/repositories/economy_repository.py

import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.club_transaction import ClubTransaction

async def insert_transaction_if_new(
    session: AsyncSession,
    *,
    club_id: uuid.UUID,
    guild_id: str,
    source_type: str,
    source_id: str,
    amount: int,
    balance_before: int,
    balance_after: int,
    description: str | None = None,
    metadata_json: dict | None = None,
) -> bool:
    """
    Inserts a new club transaction ledger row.
    Uses ON CONFLICT DO NOTHING to prevent transaction poisoning.
    Returns True if successfully inserted, False if it was a duplicate.
    """
    bind = session.bind
    dialect_name = bind.dialect.name if bind else "postgresql"

    if dialect_name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        stmt = (
            pg_insert(ClubTransaction)
            .values(
                club_id=club_id,
                guild_id=str(guild_id),
                source_type=source_type,
                source_id=str(source_id),
                amount=amount,
                balance_before=balance_before,
                balance_after=balance_after,
                description=description,
                metadata_json=metadata_json
            )
            .on_conflict_do_nothing(constraint="uq_club_transaction_source")
            .returning(ClubTransaction.id)
        )
        res = await session.execute(stmt)
        inserted_id = res.scalar_one_or_none()
        return inserted_id is not None
    else:
        # SQLite dialect for tests
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert
        stmt = (
            sqlite_insert(ClubTransaction)
            .values(
                club_id=club_id,
                guild_id=str(guild_id),
                source_type=source_type,
                source_id=str(source_id),
                amount=amount,
                balance_before=balance_before,
                balance_after=balance_after,
                description=description,
                metadata_json=metadata_json
            )
            .on_conflict_do_nothing(index_elements=["club_id", "source_type", "source_id"])
            .returning(ClubTransaction.id)
        )
        res = await session.execute(stmt)
        inserted_id = res.scalar_one_or_none()
        return inserted_id is not None

async def get_recent_transactions_by_club_id(
    session: AsyncSession,
    *,
    club_id: uuid.UUID,
    limit: int = 3,
) -> list[ClubTransaction]:
    """
    Fetch the most recent transactions for a club, sorted by newest first.
    """
    stmt = (
        select(ClubTransaction)
        .where(ClubTransaction.club_id == club_id)
        .order_by(ClubTransaction.created_at.desc(), ClubTransaction.id.desc())
        .limit(limit)
    )
    res = await session.execute(stmt)
    return list(res.scalars().all())
