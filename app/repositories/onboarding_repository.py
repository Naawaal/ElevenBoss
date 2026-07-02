"""
Onboarding repository — all database queries for onboarding_sessions.
All functions accept an AsyncSession and do NOT commit; callers own the transaction.
"""
import logging
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy import update, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.onboarding_session import OnboardingSession

logger = logging.getLogger("app.repositories.onboarding_repository")

# ── Status constants ────────────────────────────────────────────────────────
STATUS_ACTIVE = "ACTIVE"
STATUS_COMPLETING = "COMPLETING"
STATUS_COMPLETED = "COMPLETED"
STATUS_ABANDONED = "ABANDONED"
STATUS_FAILED = "FAILED"


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Read queries ────────────────────────────────────────────────────────────

async def get_active_session(
    session: AsyncSession, guild_id: int | str, user_id: int | str
) -> OnboardingSession | None:
    """Return the single ACTIVE or COMPLETING session for a user in a guild, if any."""
    stmt = select(OnboardingSession).where(
        OnboardingSession.guild_id == str(guild_id),
        OnboardingSession.user_id == str(user_id),
        OnboardingSession.status.in_([STATUS_ACTIVE, STATUS_COMPLETING]),
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_session_by_id(
    session: AsyncSession, session_id: uuid.UUID
) -> OnboardingSession | None:
    """Fetch an onboarding session by its UUID."""
    return await session.get(OnboardingSession, session_id)


async def get_for_update(
    session: AsyncSession, session_id: uuid.UUID
) -> OnboardingSession | None:
    """SELECT FOR UPDATE — use inside an explicit transaction to prevent races."""
    stmt = (
        select(OnboardingSession)
        .where(OnboardingSession.id == session_id)
        .with_for_update()
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_nudgeable_sessions(session: AsyncSession) -> list[OnboardingSession]:
    """ACTIVE sessions inactive for ≥10 min that have not yet been nudged."""
    threshold = _now() - timedelta(minutes=10)
    stmt = select(OnboardingSession).where(
        OnboardingSession.status == STATUS_ACTIVE,
        OnboardingSession.last_activity_at <= threshold,
        OnboardingSession.nudge_sent_at.is_(None),
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_abandonment_due_sessions(session: AsyncSession) -> list[OnboardingSession]:
    """ACTIVE sessions inactive for ≥15 min (including already-nudged ones)."""
    threshold = _now() - timedelta(minutes=15)
    stmt = select(OnboardingSession).where(
        OnboardingSession.status == STATUS_ACTIVE,
        OnboardingSession.last_activity_at <= threshold,
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_cleanup_due_sessions(session: AsyncSession) -> list[OnboardingSession]:
    """Sessions whose cleanup_after timestamp has passed."""
    now = _now()
    stmt = select(OnboardingSession).where(
        OnboardingSession.cleanup_after.isnot(None),
        OnboardingSession.cleanup_after <= now,
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_stuck_completing_sessions(session: AsyncSession) -> list[OnboardingSession]:
    """COMPLETING sessions that have been stuck for more than 5 minutes."""
    threshold = _now() - timedelta(minutes=5)
    stmt = select(OnboardingSession).where(
        OnboardingSession.status == STATUS_COMPLETING,
        OnboardingSession.completing_at <= threshold,
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


# ── Write / mutation queries ────────────────────────────────────────────────

async def create_active_reservation(
    session: AsyncSession,
    guild_id: int | str,
    user_id: int | str,
    channel_id: int | str | None,
) -> OnboardingSession:
    """
    Insert a new ACTIVE onboarding session with current_step=WELCOME.
    The DB partial unique index (uq_onboarding_active_per_user) prevents a second
    concurrent row from being created for the same (guild, user).
    """
    now = _now()
    onb = OnboardingSession(
        guild_id=str(guild_id),
        user_id=str(user_id),
        channel_id=str(channel_id) if channel_id else None,
        current_step="WELCOME",
        collected_data={},
        status=STATUS_ACTIVE,
        flow_version=1,
        started_at=now,
        last_activity_at=now,
    )
    session.add(onb)
    await session.flush()  # get the generated UUID back
    logger.info(f"onboarding_reservation_created: id={onb.id}, guild={guild_id}, user={user_id}")
    return onb


async def attach_thread(
    session: AsyncSession,
    session_id: uuid.UUID,
    thread_id: int,
    starter_message_id: int | None,
    thread_mode: str,
) -> None:
    """Update an existing session with the Discord thread details."""
    stmt = (
        update(OnboardingSession)
        .where(OnboardingSession.id == session_id)
        .values(
            thread_id=str(thread_id),
            starter_message_id=str(starter_message_id) if starter_message_id else None,
            thread_mode=thread_mode,
            last_activity_at=_now(),
        )
    )
    await session.execute(stmt)


async def advance_step(
    session: AsyncSession, session_id: uuid.UUID, next_step: str
) -> None:
    """Move to the next step and bump last_activity_at."""
    stmt = (
        update(OnboardingSession)
        .where(OnboardingSession.id == session_id)
        .values(current_step=next_step, last_activity_at=_now())
    )
    await session.execute(stmt)


async def save_collected_data(
    session: AsyncSession, session_id: uuid.UUID, key: str, value: str
) -> None:
    """Merge a key-value pair into collected_data JSONB."""
    stmt = (
        update(OnboardingSession)
        .where(OnboardingSession.id == session_id)
        .values(
            collected_data=OnboardingSession.collected_data.op("||")(
                text(f"'{{\"{key}\": \"{value}\"}}'::jsonb")
            ),
            last_activity_at=_now(),
        )
    )
    await session.execute(stmt)


async def set_club_id(
    session: AsyncSession, session_id: uuid.UUID, club_id: uuid.UUID
) -> None:
    """Persist club_id on the session row (called atomically with club creation)."""
    stmt = (
        update(OnboardingSession)
        .where(OnboardingSession.id == session_id)
        .values(club_id=club_id, last_activity_at=_now())
    )
    await session.execute(stmt)


async def claim_completion(session: AsyncSession, session_id: uuid.UUID) -> bool:
    """
    Atomically transition status ACTIVE → COMPLETING.
    Returns True only if this call performed the transition (race-safe).
    """
    now = _now()
    stmt = (
        update(OnboardingSession)
        .where(
            OnboardingSession.id == session_id,
            OnboardingSession.status == STATUS_ACTIVE,
            OnboardingSession.current_step == "COMPLETE",
        )
        .values(status=STATUS_COMPLETING, completing_at=now, last_activity_at=now)
        .returning(OnboardingSession.id)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


async def mark_completed(
    session: AsyncSession,
    session_id: uuid.UUID,
    club_id: uuid.UUID,
    cleanup_after: datetime,
) -> None:
    """Transition to COMPLETED status and schedule thread cleanup."""
    now = _now()
    stmt = (
        update(OnboardingSession)
        .where(OnboardingSession.id == session_id)
        .values(
            status=STATUS_COMPLETED,
            club_id=club_id,
            completed_at=now,
            last_activity_at=now,
            cleanup_after=cleanup_after,
        )
    )
    await session.execute(stmt)


async def mark_failed(
    session: AsyncSession, session_id: uuid.UUID, reason: str
) -> None:
    """Mark session as FAILED with an error reason."""
    now = _now()
    stmt = (
        update(OnboardingSession)
        .where(OnboardingSession.id == session_id)
        .values(
            status=STATUS_FAILED,
            status_reason=reason[:1000],  # guard against absurdly long errors
            failed_at=now,
            last_activity_at=now,
            cleanup_after=now,
        )
    )
    await session.execute(stmt)


async def mark_abandoned(session: AsyncSession, session_id: uuid.UUID) -> None:
    """Mark session as ABANDONED (inactivity timeout)."""
    now = _now()
    stmt = (
        update(OnboardingSession)
        .where(OnboardingSession.id == session_id)
        .values(
            status=STATUS_ABANDONED,
            abandoned_at=now,
            last_activity_at=now,
            # Schedule immediate cleanup so sweeper removes the thread
            cleanup_after=now,
        )
    )
    await session.execute(stmt)


async def return_to_step(
    session: AsyncSession,
    session_id: uuid.UUID,
    step: str,
    error: str | None = None,
) -> None:
    """Reset a COMPLETING session back to ACTIVE at the specified step (e.g. after a name clash)."""
    stmt = (
        update(OnboardingSession)
        .where(OnboardingSession.id == session_id)
        .values(
            status=STATUS_ACTIVE,
            current_step=step,
            status_reason=error,
            completing_at=None,
            last_activity_at=_now(),
        )
    )
    await session.execute(stmt)


async def mark_nudge_sent(session: AsyncSession, session_id: uuid.UUID) -> None:
    """Record that the inactivity nudge has been sent."""
    stmt = (
        update(OnboardingSession)
        .where(OnboardingSession.id == session_id)
        .values(nudge_sent_at=_now())
    )
    await session.execute(stmt)


async def update_cleanup_state(
    session: AsyncSession,
    session_id: uuid.UUID,
    attempted_at: datetime,
    error: str | None,
) -> None:
    """Record a cleanup attempt result (for sweeper retry logic)."""
    stmt = (
        update(OnboardingSession)
        .where(OnboardingSession.id == session_id)
        .values(
            cleanup_attempted_at=attempted_at,
            cleanup_error=error,
            # Clear cleanup_after on success so sweeper won't retry
            cleanup_after=None if error is None else OnboardingSession.cleanup_after,
        )
    )
    await session.execute(stmt)
