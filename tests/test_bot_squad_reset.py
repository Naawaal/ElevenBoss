import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from app.models.player import Player
from app.models.club import Club
from app.services.player_service import PlayerService, SquadGenerationResult


def _make_player(club_id, is_retired=False, overall=70):
    p = MagicMock(spec=Player)
    p.id = uuid.uuid4()
    p.club_id = club_id
    p.is_retired = is_retired
    p.overall = overall
    return p


def _make_club(is_bot=True):
    c = MagicMock(spec=Club)
    c.id = uuid.uuid4()
    c.is_bot_controlled = is_bot
    c.overall_rating = None
    c.season_id = None
    return c


@pytest.mark.asyncio
async def test_retire_squad_soft_retires_and_clears_generation_run():
    club_id = uuid.uuid4()
    update_result = MagicMock()
    update_result.rowcount = 25

    session = AsyncMock()
    session.execute = AsyncMock(return_value=update_result)
    session.flush = AsyncMock()

    with patch("app.repositories.squad_generation_repository.delete_run", new_callable=AsyncMock) as mock_delete_run:
        count = await PlayerService.retire_squad(club_id, session)

    assert count == 25
    assert session.flush.await_count >= 1
    mock_delete_run.assert_awaited_once_with(session, club_id)


@pytest.mark.asyncio
async def test_retire_then_create_produces_fresh_squad():
    club_id = uuid.uuid4()
    session = AsyncMock()

    new_players = [_make_player(club_id) for _ in range(25)]

    update_result = MagicMock()
    update_result.rowcount = 25
    session.execute = AsyncMock(return_value=update_result)
    session.flush = AsyncMock()

    with (
        patch("app.repositories.squad_generation_repository.delete_run", new_callable=AsyncMock),
        patch.object(
            PlayerService, "create_squad",
            new_callable=AsyncMock,
            return_value=SquadGenerationResult(status="GENERATED", players=new_players),
        ) as mock_create,
    ):
        await PlayerService.retire_squad(club_id, session)
        result = await PlayerService.create_squad(club_id, session)

    assert result.status == "GENERATED"
    assert len(result.players) == 25


@pytest.mark.asyncio
async def test_bootstrap_resets_bot_clubs_skips_human_clubs():
    from app.services.league_lifecycle_service import LeagueLifecycleService
    from app.models.league import League, LeagueStatus
    from app.models.season import Season, SeasonStatus

    bot_club = _make_club(is_bot=True)
    human_club = _make_club(is_bot=False)

    fresh_players = [_make_player(bot_club.id, overall=75) for _ in range(25)]
    squad_result = SquadGenerationResult(status="GENERATED", players=fresh_players)

    mock_new_season = MagicMock(spec=Season)
    mock_new_season.id = uuid.uuid4()
    mock_new_season.status = SeasonStatus.ACTIVE
    mock_new_season.current_week = 1

    mock_league = MagicMock(spec=League)
    mock_league.id = uuid.uuid4()
    mock_league.guild_id = "123"
    mock_league.status = LeagueStatus.ACTIVE

    session = AsyncMock()
    session.flush = AsyncMock()

    with (
        patch("app.services.league_lifecycle_service.get_clubs_in_league", new_callable=AsyncMock, return_value=[bot_club, human_club]),
        patch("app.repositories.season_repository.create_season", new_callable=AsyncMock, return_value=mock_new_season),
        patch("app.services.standings_service.initialize_standings", new_callable=AsyncMock),
        patch("app.engine.fixture_generator.generate_round_robin_fixtures", return_value=[]),
        patch("app.repositories.fixture_repository.bulk_create_fixtures", new_callable=AsyncMock),
        patch.object(PlayerService, "retire_squad", new_callable=AsyncMock, return_value=25) as mock_retire,
        patch.object(PlayerService, "create_squad", new_callable=AsyncMock, return_value=squad_result) as mock_create,
    ):
        await LeagueLifecycleService._bootstrap_season_internal(session, "123", mock_league, 2)

    mock_retire.assert_awaited_once_with(bot_club.id, session)
    mock_create.assert_awaited_once_with(bot_club.id, session)
    assert bot_club.overall_rating == 75
    assert human_club.overall_rating is None
