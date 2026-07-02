"""
Tests for the onboarding repository — in-memory SQLite via SQLAlchemy.
"""
import pytest
import asyncio
import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool
from app.db.base import Base
from app.models.onboarding_session import OnboardingSession
from app.models.club import Club
from app.repositories import onboarding_repository as onb_repo
import pytest_asyncio
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB


@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


@pytest_asyncio.fixture
async def engine():
    # SQLite in-memory; UNIQUE constraints apply but partial indexes require workaround
    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with eng.begin() as conn:
        # Create only the tables needed by these tests
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine):
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        yield s
        await s.rollback()


# ── Helper ─────────────────────────────────────────────────────────────────

async def _create(session, guild_id="100", user_id="200"):
    return await onb_repo.create_active_reservation(session, guild_id, user_id, channel_id="300")


# ── Tests ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_active_session(session):
    onb = await _create(session)
    assert onb.id is not None
    assert onb.status == "ACTIVE"
    assert onb.current_step == "WELCOME"
    assert onb.guild_id == "100"
    assert onb.user_id == "200"


@pytest.mark.asyncio
async def test_get_active_session_returns_created(session):
    await _create(session, guild_id="101", user_id="201")
    await session.flush()
    found = await onb_repo.get_active_session(session, "101", "201")
    assert found is not None
    assert found.user_id == "201"


@pytest.mark.asyncio
async def test_get_active_session_returns_none_for_unknown(session):
    found = await onb_repo.get_active_session(session, "999", "999")
    assert found is None


@pytest.mark.asyncio
async def test_attach_thread(session):
    onb = await _create(session, guild_id="102", user_id="202")
    await session.flush()
    await onb_repo.attach_thread(session, onb.id, thread_id=99999, starter_message_id=None, thread_mode="PRIVATE")
    await session.flush()
    refreshed = await session.get(OnboardingSession, onb.id)
    await session.refresh(refreshed)
    assert refreshed.thread_id == "99999"
    assert refreshed.thread_mode == "PRIVATE"


@pytest.mark.asyncio
async def test_advance_step(session):
    onb = await _create(session, guild_id="103", user_id="203")
    await session.flush()
    await onb_repo.advance_step(session, onb.id, "EXPLAIN_CLUBS")
    await session.flush()
    refreshed = await session.get(OnboardingSession, onb.id)
    await session.refresh(refreshed)
    assert refreshed.current_step == "EXPLAIN_CLUBS"


@pytest.mark.asyncio
async def test_mark_abandoned(session):
    onb = await _create(session, guild_id="104", user_id="204")
    await session.flush()
    await onb_repo.mark_abandoned(session, onb.id)
    await session.flush()
    refreshed = await session.get(OnboardingSession, onb.id)
    await session.refresh(refreshed)
    assert refreshed.status == "ABANDONED"
    assert refreshed.cleanup_after is not None


@pytest.mark.asyncio
async def test_mark_failed(session):
    onb = await _create(session, guild_id="105", user_id="205")
    await session.flush()
    await onb_repo.mark_failed(session, onb.id, "Test error")
    await session.flush()
    refreshed = await session.get(OnboardingSession, onb.id)
    await session.refresh(refreshed)
    assert refreshed.status == "FAILED"
    assert refreshed.status_reason == "Test error"


@pytest.mark.asyncio
async def test_mark_nudge_sent(session):
    onb = await _create(session, guild_id="106", user_id="206")
    await session.flush()
    assert onb.nudge_sent_at is None
    await onb_repo.mark_nudge_sent(session, onb.id)
    await session.flush()
    refreshed = await session.get(OnboardingSession, onb.id)
    await session.refresh(refreshed)
    assert refreshed.nudge_sent_at is not None


@pytest.mark.asyncio
async def test_return_to_step(session):
    onb = await _create(session, guild_id="107", user_id="207")
    await session.flush()
    # Simulate: advance past COLLECT_CLUB_NAME then return to it
    await onb_repo.advance_step(session, onb.id, "COMPLETE")
    await session.flush()
    await onb_repo.return_to_step(session, onb.id, "COLLECT_CLUB_NAME", "Name taken")
    await session.flush()
    refreshed = await session.get(OnboardingSession, onb.id)
    await session.refresh(refreshed)
    assert refreshed.current_step == "COLLECT_CLUB_NAME"
    assert refreshed.status == "ACTIVE"
    assert refreshed.status_reason == "Name taken"



@pytest.mark.asyncio
async def test_claim_completion_requires_active_and_complete_step(session):
    onb = await _create(session, guild_id="108", user_id="208")
    await session.flush()
    # Status is ACTIVE but step is not COMPLETE
    result = await onb_repo.claim_completion(session, onb.id)
    assert result is False
    # Advance to COMPLETE
    await onb_repo.advance_step(session, onb.id, "COMPLETE")
    await session.flush()
    result = await onb_repo.claim_completion(session, onb.id)
    assert result is True
    # Second call returns False (already COMPLETING)
    result2 = await onb_repo.claim_completion(session, onb.id)
    assert result2 is False
