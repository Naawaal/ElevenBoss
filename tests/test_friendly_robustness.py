import pytest
import uuid
import asyncio
import discord
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

import pytest_asyncio
from app.db.session import get_session
from app.repositories import friendly_repository as friendly_repo
from app.models.friendly import FriendlyThreadBreadcrumb, FriendlyCooldown
from app.scheduler.friendly_sweeper import sweep_friendly_threads
from app.ui.handlers.friendly_handler import handle_friendly_challenge, expire_invite_after_delay
from app.ui.handlers.session import ui_session_manager
from app.ui.components import V2View

@pytest_asyncio.fixture(autouse=True)
async def cleanup_database_connections():
    """
    Ensure the database engine pool is fully disposed after each test
    to prevent asyncpg connection state reuse issues (another operation in progress).
    """
    yield
    from app.db.engine import get_engine
    engine = get_engine()
    if engine:
        await engine.dispose()

@pytest.mark.asyncio
async def test_friendly_cooldown_database_persistence():
    guild_id = "test_guild_1"
    challenger_id = "test_user_1"
    opponent_id = "test_user_2"
    
    # 1. Verify no initial cooldown
    async with get_session() as session:
        c = await friendly_repo.get_friendly_cooldown(session, guild_id, challenger_id, opponent_id)
        assert c is None
        
    # 2. Set cooldown for 5 minutes
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=5)
    async with get_session() as session:
        await friendly_repo.set_friendly_cooldown(session, guild_id, challenger_id, opponent_id, expires_at)
        await session.commit()
        
    # 3. Retrieve active cooldown
    async with get_session() as session:
        c = await friendly_repo.get_friendly_cooldown(session, guild_id, challenger_id, opponent_id)
        assert c is not None
        assert c.expires_at == expires_at
        
    # 4. Override cooldown to be expired
    async with get_session() as session:
        await friendly_repo.set_friendly_cooldown(
            session, guild_id, challenger_id, opponent_id, now - timedelta(seconds=1)
        )
        await session.commit()

    # 5. Verify expired cooldown is not returned as active
    async with get_session() as session:
        c = await friendly_repo.get_friendly_cooldown(session, guild_id, challenger_id, opponent_id)
        assert c is None
        
    # 6. Clean expired cooldowns
    async with get_session() as session:
        await friendly_repo.clean_expired_cooldowns(session)
        await session.commit()

@pytest.mark.asyncio
async def test_friendly_thread_breadcrumb_lifecycle():
    thread_id = str(uuid.uuid4())
    guild_id = "test_guild_2"
    participant_ids = [123, 456]
    
    # 1. Create breadcrumb
    async with get_session() as session:
        crumb = await friendly_repo.create_thread_breadcrumb(
            session=session,
            thread_id=thread_id,
            parent_message_id="998877",
            guild_id=guild_id,
            participant_ids=participant_ids,
            status="PLAYING"
        )
        await session.commit()
        assert crumb.status == "PLAYING"
        
    # 2. Verify playing breadcrumb is not due for cleanup
    async with get_session() as session:
        due = await friendly_repo.get_cleanup_due_breadcrumbs(session)
        assert not any(x.thread_id == thread_id for x in due)
        
    # 3. Transition to COMPLETED with cleanup_after in the past
    past_time = datetime.now(timezone.utc) - timedelta(minutes=1)
    async with get_session() as session:
        updated = await friendly_repo.update_breadcrumb_status(session, thread_id, "COMPLETED", past_time)
        assert updated is not None
        assert updated.status == "COMPLETED"
        assert updated.cleanup_after == past_time
        await session.commit()

    # 4. Verify it is now due for cleanup
    async with get_session() as session:
        due = await friendly_repo.get_cleanup_due_breadcrumbs(session)
        assert any(x.thread_id == thread_id for x in due)
        
        # Delete breadcrumb
        target = next(x for x in due if x.thread_id == thread_id)
        await friendly_repo.delete_breadcrumb(session, target.id)
        await session.commit()

    # 5. Verify it was deleted
    async with get_session() as session:
        due = await friendly_repo.get_cleanup_due_breadcrumbs(session)
        assert not any(x.thread_id == thread_id for x in due)

@pytest.mark.asyncio
async def test_friendly_sweeper_daemon():
    thread_id_completed = "123456789"
    thread_id_orphaned = "987654321"
    guild_id = "test_guild_3"
    
    # 1. Completed breadcrumb due for cleanup
    async with get_session() as session:
        await friendly_repo.create_thread_breadcrumb(
            session=session,
            thread_id=thread_id_completed,
            parent_message_id="1111",
            guild_id=guild_id,
            participant_ids=[11, 22],
            status="COMPLETED"
        )
        await session.commit()

    # Manually force cleanup_after in the past
    async with get_session() as session:
        await friendly_repo.update_breadcrumb_status(
            session, thread_id_completed, "COMPLETED", datetime.now(timezone.utc) - timedelta(minutes=1)
        )
        await session.commit()
        
    # 2. Orphans breadcrumb (PLAYING, but created > 10 minutes ago)
    old_time = datetime.now(timezone.utc) - timedelta(minutes=15)
    async with get_session() as session:
        await friendly_repo.create_thread_breadcrumb(
            session=session,
            thread_id=thread_id_orphaned,
            parent_message_id="2222",
            guild_id=guild_id,
            participant_ids=[33, 44],
            status="PLAYING",
            created_at=old_time
        )
        await session.commit()

    # Mock Discord Thread and Bot
    mock_thread_completed = MagicMock(spec=discord.Thread)
    mock_thread_completed.delete = AsyncMock()
    mock_thread_completed.parent = MagicMock()
    mock_thread_completed.parent.fetch_message = AsyncMock()
    
    mock_thread_orphaned = MagicMock(spec=discord.Thread)
    mock_thread_orphaned.delete = AsyncMock()
    mock_thread_orphaned.parent = MagicMock()
    mock_thread_orphaned.parent.fetch_message = AsyncMock()
    
    mock_bot = MagicMock(spec=discord.Client)
    
    async def mock_fetch(channel_id):
        if str(channel_id) == thread_id_completed:
            return mock_thread_completed
        elif str(channel_id) == thread_id_orphaned:
            return mock_thread_orphaned
        raise discord.NotFound(None, "Not Found")
        
    mock_bot.fetch_channel = AsyncMock(side_effect=mock_fetch)
    
    # Run the sweeper
    await sweep_friendly_threads(mock_bot)
    
    # Verify Discord thread delete was called for both
    mock_thread_completed.delete.assert_called_once()
    mock_thread_orphaned.delete.assert_called_once()
    
    # Verify parent messages were fetched/deleted
    mock_thread_completed.parent.fetch_message.assert_called_once()
    mock_thread_orphaned.parent.fetch_message.assert_called_once()

    # Verify database is clean (breadcrumbs deleted)
    async with get_session() as session:
        due = await friendly_repo.get_cleanup_due_breadcrumbs(session)
        assert not any(x.thread_id == thread_id_completed for x in due)
        
        dangling = await friendly_repo.get_dangling_breadcrumbs(session, max_duration_minutes=10)
        assert not any(x.thread_id == thread_id_orphaned for x in dangling)

@pytest.mark.asyncio
@patch("app.ui.handlers.friendly_handler.get_session")
@patch("app.ui.handlers.friendly_handler.get_user_club")
@patch("app.repositories.friendly_repository.get_friendly_cooldown")
@patch("app.repositories.friendly_repository.set_friendly_cooldown")
async def test_challenge_invite_expiry_workflow(
    mock_set_cooldown, mock_get_cooldown, mock_get_club, mock_get_session
):
    session_mock = AsyncMock()
    mock_get_session.return_value.__aenter__.return_value = session_mock
    mock_get_cooldown.return_value = None
    
    challenger = MagicMock(spec=discord.Member, id=111, display_name="Challenger")
    opponent = MagicMock(spec=discord.Member, id=222, display_name="Opponent", bot=False)
    
    from app.models.club import Club
    club_challenger = Club(id=uuid.uuid4(), name="Challenger FC", guild_id="12345")
    club_opponent = Club(id=uuid.uuid4(), name="Opponent FC", guild_id="12345")
    mock_get_club.side_effect = [club_challenger, club_opponent]
    
    interaction = MagicMock(spec=discord.Interaction)
    interaction.edit_original_response = AsyncMock()
    
    ui_session_manager._sessions.clear()
    
    # Call handle challenge without scheduling background task (or pass interaction=None to not trigger background task)
    view = await handle_friendly_challenge("12345", challenger, opponent, interaction=None)
    assert isinstance(view, V2View)
    
    # Retrieve generated session
    sessions = list(ui_session_manager._sessions.values())
    assert len(sessions) == 1
    ui_session = sessions[0]
    nonce = ui_session.session_id
    
    # Call the expiration task directly and await it
    await expire_invite_after_delay(interaction, nonce, delay_seconds=0)
    
    # Verify session is cleaned up and card is updated to expired state
    assert ui_session.metadata["status"] == "expired"
    assert nonce not in ui_session_manager._sessions
    interaction.edit_original_response.assert_called_once()
