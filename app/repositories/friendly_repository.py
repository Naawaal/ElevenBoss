import logging
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.friendly import FriendlyThreadBreadcrumb, FriendlyCooldown

logger = logging.getLogger("app.repositories.friendly_repository")

def _now() -> datetime:
    return datetime.now(timezone.utc)

# ── Cooldown Queries ────────────────────────────────────────────────────────

async def get_friendly_cooldown(
    session: AsyncSession,
    guild_id: int | str,
    challenger_id: int | str,
    opponent_id: int | str
) -> FriendlyCooldown | None:
    """
    Retrieve active cooldown for the challenger against the opponent, if it exists and is not expired.
    """
    stmt = select(FriendlyCooldown).where(
        FriendlyCooldown.guild_id == str(guild_id),
        FriendlyCooldown.challenger_id == str(challenger_id),
        FriendlyCooldown.opponent_id == str(opponent_id),
        FriendlyCooldown.expires_at > _now()
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

async def set_friendly_cooldown(
    session: AsyncSession,
    guild_id: int | str,
    challenger_id: int | str,
    opponent_id: int | str,
    expires_at: datetime
) -> FriendlyCooldown:
    """
    Insert or update a friendly challenge cooldown.
    """
    stmt = select(FriendlyCooldown).where(
        FriendlyCooldown.guild_id == str(guild_id),
        FriendlyCooldown.challenger_id == str(challenger_id),
        FriendlyCooldown.opponent_id == str(opponent_id)
    )
    result = await session.execute(stmt)
    cooldown = result.scalar_one_or_none()

    if cooldown:
        cooldown.expires_at = expires_at
    else:
        cooldown = FriendlyCooldown(
            guild_id=str(guild_id),
            challenger_id=str(challenger_id),
            opponent_id=str(opponent_id),
            expires_at=expires_at
        )
        session.add(cooldown)
    
    return cooldown

async def clean_expired_cooldowns(session: AsyncSession) -> None:
    """
    Delete all expired cooldown entries from the database.
    """
    stmt = delete(FriendlyCooldown).where(FriendlyCooldown.expires_at <= _now())
    await session.execute(stmt)

# ── Thread Breadcrumb Queries ────────────────────────────────────────────────

async def create_thread_breadcrumb(
    session: AsyncSession,
    thread_id: int | str,
    parent_message_id: int | str | None,
    guild_id: int | str,
    participant_ids: list[int],
    status: str,
    created_at: datetime | None = None
) -> FriendlyThreadBreadcrumb:
    """
    Create a new friendly match thread breadcrumb.
    """
    if created_at is None:
        created_at = _now()

    breadcrumb = FriendlyThreadBreadcrumb(
        thread_id=str(thread_id),
        parent_message_id=str(parent_message_id) if parent_message_id else None,
        guild_id=str(guild_id),
        participant_ids=participant_ids,
        status=status,
        created_at=created_at,
        cleanup_after=None
    )
    session.add(breadcrumb)
    return breadcrumb

async def update_breadcrumb_status(
    session: AsyncSession,
    thread_id: int | str,
    status: str,
    cleanup_after: datetime | None = None
) -> FriendlyThreadBreadcrumb | None:
    """
    Update status and cleanup schedule for a friendly thread breadcrumb.
    """
    stmt = select(FriendlyThreadBreadcrumb).where(
        FriendlyThreadBreadcrumb.thread_id == str(thread_id)
    ).with_for_update()
    result = await session.execute(stmt)
    breadcrumb = result.scalar_one_or_none()

    if breadcrumb:
        breadcrumb.status = status
        if cleanup_after:
            breadcrumb.cleanup_after = cleanup_after
    return breadcrumb

async def get_cleanup_due_breadcrumbs(
    session: AsyncSession
) -> list[FriendlyThreadBreadcrumb]:
    """
    Retrieve COMPLETED breadcrumbs whose cleanup_after has passed.
    """
    stmt = select(FriendlyThreadBreadcrumb).where(
        FriendlyThreadBreadcrumb.status == "COMPLETED",
        FriendlyThreadBreadcrumb.cleanup_after <= _now()
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())

async def get_dangling_breadcrumbs(
    session: AsyncSession,
    max_duration_minutes: int = 10
) -> list[FriendlyThreadBreadcrumb]:
    """
    Retrieve PLAYING breadcrumbs that are older than the maximum duration threshold,
    indicating they were orphaned due to a crash.
    """
    threshold = _now() - timedelta(minutes=max_duration_minutes)
    stmt = select(FriendlyThreadBreadcrumb).where(
        FriendlyThreadBreadcrumb.status == "PLAYING",
        FriendlyThreadBreadcrumb.created_at < threshold
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())

async def delete_breadcrumb(
    session: AsyncSession,
    breadcrumb_id: uuid.UUID
) -> None:
    """
    Delete a breadcrumb row by its database primary key UUID.
    """
    stmt = delete(FriendlyThreadBreadcrumb).where(FriendlyThreadBreadcrumb.id == breadcrumb_id)
    await session.execute(stmt)

async def update_breadcrumb_cleanup_error(
    session: AsyncSession,
    breadcrumb_id: uuid.UUID,
    attempted_at: datetime,
    error: str | None
) -> None:
    """
    Record cleanup error metadata for debugging.
    """
    stmt = select(FriendlyThreadBreadcrumb).where(
        FriendlyThreadBreadcrumb.id == breadcrumb_id
    ).with_for_update()
    result = await session.execute(stmt)
    breadcrumb = result.scalar_one_or_none()

    if breadcrumb:
        breadcrumb.cleanup_attempted_at = attempted_at
        breadcrumb.cleanup_error = error
