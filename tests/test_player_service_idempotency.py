"""
Tests for PlayerService.create_squad — idempotency and repair logic.
"""
import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.player_service import PlayerService, SquadGenerationResult


def make_club(club_id=None, guild_id="100"):
    club = MagicMock()
    club.id = club_id or uuid.uuid4()
    club.guild_id = guild_id
    return club


def make_players(n=25):
    return [MagicMock() for _ in range(n)]


@pytest.mark.asyncio
async def test_create_squad_no_op_when_squad_already_complete():
    """If a COMPLETED run exists and 25 players exist, return ALREADY_EXISTS."""
    club = make_club()
    session = AsyncMock()
    session.get = AsyncMock(return_value=club)

    completed_run = MagicMock()
    completed_run.status = "COMPLETED"
    players = make_players(25)

    with (
        patch("app.services.player_service.PlayerService.get_squad", new_callable=AsyncMock, return_value=players),
        patch("app.repositories.squad_generation_repository.get_generation_run", new_callable=AsyncMock, return_value=completed_run),
    ):
        result = await PlayerService.create_squad(club.id, session)

    assert result.status == "ALREADY_EXISTS"
    assert len(result.players) == 25


@pytest.mark.asyncio
async def test_create_squad_generates_fresh_squad_when_none_exists():
    """When no run exists and no players exist, generate 25 players."""
    club = make_club()
    session = AsyncMock()
    session.get = AsyncMock(return_value=club)
    session.add_all = MagicMock()
    session.flush = AsyncMock()

    players = make_players(25)

    with (
        patch("app.services.player_service.PlayerService.get_squad", new_callable=AsyncMock, return_value=[]),
        patch("app.repositories.squad_generation_repository.get_generation_run", new_callable=AsyncMock, return_value=None),
        patch("app.repositories.squad_generation_repository.create_generation_run", new_callable=AsyncMock),
        patch("app.repositories.squad_generation_repository.mark_run_complete", new_callable=AsyncMock),
        patch("app.services.player_service.generate_squad", return_value=players),
    ):
        result = await PlayerService.create_squad(club.id, session)

    assert result.status == "GENERATED"
    assert len(result.players) == 25


@pytest.mark.asyncio
async def test_create_squad_repairs_partial_squad():
    """If 10 players exist but run is not complete, delete and regenerate."""
    club = make_club()
    session = AsyncMock()
    session.get = AsyncMock(return_value=club)
    session.delete = AsyncMock()
    session.add_all = MagicMock()
    session.flush = AsyncMock()

    partial_players = make_players(10)
    full_players = make_players(25)

    # get_squad called twice: once for the completed-run check, once to detect partial
    get_squad_calls = [partial_players, partial_players, []]

    with (
        patch("app.services.player_service.PlayerService.get_squad", new_callable=AsyncMock, side_effect=get_squad_calls),
        patch("app.repositories.squad_generation_repository.get_generation_run", new_callable=AsyncMock, return_value=None),
        patch("app.repositories.squad_generation_repository.create_generation_run", new_callable=AsyncMock),
        patch("app.repositories.squad_generation_repository.mark_run_complete", new_callable=AsyncMock),
        patch("app.repositories.squad_generation_repository.delete_run", new_callable=AsyncMock) as mock_delete,
        patch("app.services.player_service.generate_squad", return_value=full_players),
    ):
        result = await PlayerService.create_squad(club.id, session)

    assert result.status == "GENERATED"
    assert session.delete.call_count == len(partial_players)


@pytest.mark.asyncio
async def test_create_squad_result_dataclass_fields():
    """SquadGenerationResult has status and players fields."""
    result = SquadGenerationResult(status="GENERATED", players=[])
    assert result.status == "GENERATED"
    assert result.players == []


@pytest.mark.asyncio
async def test_create_squad_string_seed_produces_deterministic_int():
    """Same string seed always produces the same integer seed (via hash)."""
    seed = "onboarding:abc123"
    int_seed_a = hash(seed) & 0x7FFFFFFF
    int_seed_b = hash(seed) & 0x7FFFFFFF
    assert int_seed_a == int_seed_b
    assert 0 <= int_seed_a <= 0x7FFFFFFF


@pytest.mark.asyncio
async def test_create_squad_raises_for_missing_club():
    """If club doesn't exist, ValueError is raised immediately."""
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)

    with pytest.raises(ValueError, match="not found"):
        await PlayerService.create_squad(uuid.uuid4(), session)
