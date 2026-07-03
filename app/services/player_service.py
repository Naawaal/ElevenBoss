import logging
import uuid
import random
from dataclasses import dataclass, field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.session import get_session
from app.models.player import Player
from app.models.club import Club
from app.repositories import get_manager_by_discord_id, get_player_by_id, get_players_by_name
from app.engine.player_generator import generate_squad, generate_player
from app.engine.ratings import calculate_player_value, calculate_player_wage

logger = logging.getLogger("app.services.player_service")


@dataclass
class SquadGenerationResult:
    """Result returned by PlayerService.create_squad."""
    # GENERATED | ALREADY_EXISTS | REPAIRED
    status: str
    players: list[Player] = field(default_factory=list)


class PlayerService:

    @staticmethod
    async def create_squad(
        club_id: uuid.UUID, session: AsyncSession, *, seed: str | None = None
    ) -> SquadGenerationResult:
        """
        Generate and persist a full 25-player squad for a club.
        Idempotent: safe to call multiple times — will no-op if squad already exists,
        or repair a partial squad if the previous run was interrupted.
        """
        from app.repositories.squad_generation_repository import (
            get_generation_run, create_generation_run, mark_run_complete,
            mark_run_failed, delete_run,
        )

        club = await session.get(Club, club_id)
        if not club:
            raise ValueError(f"Club with ID {club_id} not found")

        # 1. Check for an existing completed run
        run = await get_generation_run(session, club_id)
        if run and run.status == "COMPLETED":
            existing = await PlayerService.get_squad(club_id, session)
            if len(existing) == 25:
                logger.info(f"create_squad_noop: club_id={club_id} already has 25 players")
                return SquadGenerationResult(status="ALREADY_EXISTS", players=existing)

        # 2. Detect and repair partial squad
        existing_players = await PlayerService.get_squad(club_id, session)
        if 0 < len(existing_players) < 25:
            logger.warning(
                f"create_squad_repair: club_id={club_id} has {len(existing_players)} players, "
                "deleting and regenerating"
            )
            for p in existing_players:
                await session.delete(p)
            if run:
                await delete_run(session, club_id)
            await session.flush()
            run = None

        # 3. Generate fresh squad
        # Convert string seed → deterministic integer seed
        int_seed: int | None = None
        if seed is not None:
            int_seed = hash(seed) & 0x7FFFFFFF

        generation_key = seed if seed else f"initial:{club_id}"
        try:
            await create_generation_run(session, club_id, generation_key)
        except Exception:
            # Concurrent call may have already inserted the run; re-read it
            run = await get_generation_run(session, club_id)
            if run and run.status == "COMPLETED":
                existing = await PlayerService.get_squad(club_id, session)
                return SquadGenerationResult(status="ALREADY_EXISTS", players=existing)
            raise

        logger.info(f"create_squad_started: guild_id={club.guild_id}, club_id={club.id}")
        try:
            players = generate_squad(club.guild_id, club.id, seed=int_seed)
            session.add_all(players)
            await session.flush()
            await mark_run_complete(session, club_id)
            logger.info(
                f"create_squad_success: guild_id={club.guild_id}, club_id={club.id}, size={len(players)}"
            )
            return SquadGenerationResult(status="GENERATED", players=players)
        except Exception as exc:
            await mark_run_failed(session, club_id)
            logger.error(f"create_squad_failed: club_id={club_id}, error={exc}", exc_info=exc)
            raise


    @staticmethod
    async def retire_squad(
        club_id: uuid.UUID, session: AsyncSession
    ) -> int:
        """
        Soft-retire all active players in a bot club's squad for seasonal reset.

        Sets is_retired=True and detaches club_id (sets to NULL) so active-squad queries
        no longer return these players, while historical MatchEvent rows referencing their
        IDs remain fully intact — no cascade wipe of goals, cards, or assist events.

        Also deletes the squad_generation_run record so PlayerService.create_squad() can
        run a fresh generation for this club without the idempotency guard blocking it.

        Returns the number of players retired.
        """
        from sqlalchemy import update as sa_update
        from app.repositories.squad_generation_repository import delete_run

        stmt = (
            sa_update(Player)
            .where(
                Player.club_id == club_id,
                Player.is_retired == False,
            )
            .values(is_retired=True, club_id=None)
            .execution_options(synchronize_session=False)
        )
        result = await session.execute(stmt)
        await session.flush()

        # Reset idempotency guard so create_squad() runs a fresh generation,
        # not the COMPLETED guard from the previous season.
        await delete_run(session, club_id)
        await session.flush()

        logger.info(f"retire_squad: club_id={club_id}, retired_count={result.rowcount}")
        return result.rowcount

    @staticmethod
    async def get_squad(club_id: uuid.UUID, session: AsyncSession) -> list[Player]:
        """
        All players belonging to a club.
        """
        stmt = select(Player).where(Player.club_id == club_id).order_by(Player.overall.desc())
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_available_players(club_id: uuid.UUID, session: AsyncSession) -> list[Player]:
        """
        Squad minus injured/suspended/retired players.
        Currently, filters out retired players since injury/suspension tracking is not in DB yet.
        """
        from app.repositories.player_repository import get_players_by_club_id
        return await get_players_by_club_id(session, club_id)

    @staticmethod
    async def age_players(season_id: uuid.UUID, session: AsyncSession) -> None:
        """
        Bulk age/growth/decline pass for all players of clubs participating in the given season.
        """
        # Query all active players in clubs participating in the season
        stmt = select(Player).join(Club).where(
            Club.season_id == season_id,
            Player.is_retired == False
        )
        result = await session.execute(stmt)
        players = result.scalars().all()
        
        logger.info(f"age_players_started: season_id={season_id}, player_count={len(players)}")
        
        retired_count = 0
        backfill_count = 0
        
        for player in players:
            # 1. Increment age
            player.age += 1
            
            # 2. Apply growth/decline
            await PlayerService.apply_growth(player)
            
            # 3. Check retirement
            if await PlayerService.check_retirement(player):
                player.is_retired = True
                retired_count += 1
                
                # Fetch player's club relation (eager load or check via session/query)
                club = await session.get(Club, player.club_id)
                if club and club.is_bot_controlled:
                    # NOTE (Option A — Bot Squad Seasonal Reset): Under normal operation,
                    # bot squads are fully replaced at season bootstrap via retire_squad() +
                    # create_squad() before age_players() runs for the new season.
                    # This branch is therefore unreachable for bot clubs in the happy path.
                    # It is retained as a safety net for any edge case where a bot player
                    # survives into age_players() unexpectedly (e.g. missed bootstrap).
                    replacement_overall = random.randint(50, 58)
                    replacement = generate_player(
                        guild_id=player.guild_id,
                        club_id=player.club_id,
                        position=player.position,
                        overall=replacement_overall
                    )
                    session.add(replacement)
                    backfill_count += 1
                    logger.info(
                        f"player_retirement_backfill: club_id={player.club_id} (bot), "
                        f"retired={player.display_name} ({player.position}, age={player.age}), "
                        f"replacement={replacement.display_name} (overall={replacement.overall})"
                    )
        
        await session.flush()
        logger.info(
            f"age_players_success: season_id={season_id}, retired_count={retired_count}, "
            f"bot_backfill_count={backfill_count}"
        )

    @staticmethod
    async def apply_growth(player: Player) -> Player:
        """
        Single-player growth/decline calculation. Updates overall, potential, value, and wage.
        """
        # Apply piecewise age-based growth/decline formula
        if player.age <= 23:
            # Young: grow toward potential, faster when younger and gap is larger
            max_gain = min(4, player.potential - player.overall)
            if max_gain > 0:
                growth = round(random.triangular(0, max_gain, max_gain * 0.6))
                player.overall = min(player.potential, player.overall + growth)
        elif player.age <= 29:
            # Prime: minor drift toward potential, mostly stable
            if player.overall < player.potential:
                player.overall = min(player.potential, player.overall + random.choice([0, 0, 1]))
        elif player.age <= 32:
            # Plateau / early decline
            if random.random() < 0.3:
                player.overall -= 1
        else:
            # Decline
            player.overall = max(40, player.overall - random.randint(1, 3))

        # Recalculate value and wage
        player.value = calculate_player_value(player.overall, player.potential, player.age)
        player.wage = calculate_player_wage(player.overall, player.age)
        return player

    @staticmethod
    async def check_retirement(player: Player) -> bool:
        """
        Retirement threshold check.
        Retires if age >= 36 and overall <= 55, or if age >= 38.
        """
        if player.age >= 36 and player.overall <= 55:
            return True
        if player.age >= 38:
            return True
        return False

    @staticmethod
    async def get_player_detail(guild_id: int | str, discord_user_id: int | str, player_id: str | uuid.UUID) -> dict | None:
        """
        Fetch a player by ID and ensure they belong to the requesting manager's club.
        Returns None if validation fails or player is not found.
        """
        try:
            if isinstance(player_id, str):
                try:
                    player_uuid = uuid.UUID(player_id)
                except ValueError:
                    return None
            else:
                player_uuid = player_id

            async with get_session() as session:
                manager = await get_manager_by_discord_id(session, guild_id, discord_user_id)
                if not manager or not manager.club_id:
                    return None
                
                player = await get_player_by_id(session, player_uuid)
                if not player or player.club_id != manager.club_id:
                    return None
                
                return {
                    "id": str(player.id),
                    "display_name": player.display_name,
                    "first_name": player.first_name,
                    "last_name": player.last_name,
                    "position": player.position,
                    "age": player.age,
                    "overall": player.overall,
                    "potential": player.potential,
                    "fitness": player.fitness,
                    "morale": player.morale,
                    "value": player.value,
                    "wage": player.wage,
                    "sharpness": player.sharpness,
                    "preferred_foot": player.preferred_foot,
                    "weak_foot": player.weak_foot,
                    "skill_moves": player.skill_moves,
                    "traits": player.traits or {"list": []},
                    "nationality": player.nationality
                }
        except Exception as e:
            logger.error(f"Failed to fetch player detail: {e}", exc_info=e)
            from app.error_reporting import capture_exception
            capture_exception(e)
            raise e

    @staticmethod
    async def search_player_by_name(guild_id: int | str, discord_user_id: int | str, query: str) -> list[dict] | None:
        """
        Searches for players in the manager's club by name query.
        Returns None if not registered.
        """
        try:
            async with get_session() as session:
                manager = await get_manager_by_discord_id(session, guild_id, discord_user_id)
                if not manager or not manager.club_id:
                    return None
                
                players = await get_players_by_name(session, manager.club_id, query)
                return [
                    {
                        "id": str(p.id),
                        "display_name": p.display_name,
                        "position": p.position,
                        "age": p.age,
                        "overall": p.overall,
                        "potential": p.potential,
                        "fitness": p.fitness,
                        "morale": p.morale,
                        "value": p.value,
                        "wage": p.wage,
                        "sharpness": p.sharpness,
                        "preferred_foot": p.preferred_foot,
                        "weak_foot": p.weak_foot,
                        "skill_moves": p.skill_moves,
                        "traits": p.traits or {"list": []},
                        "nationality": p.nationality
                    }
                    for p in players
                ]
        except Exception as e:
            logger.error(f"Failed to search player: {e}", exc_info=e)
            from app.error_reporting import capture_exception
            capture_exception(e)
            raise e

# Module-level exports for backwards compatibility
async def get_player_detail(guild_id: int | str, discord_user_id: int | str, player_id: str | uuid.UUID) -> dict | None:
    return await PlayerService.get_player_detail(guild_id, discord_user_id, player_id)

async def search_player_by_name(guild_id: int | str, discord_user_id: int | str, query: str) -> list[dict] | None:
    return await PlayerService.search_player_by_name(guild_id, discord_user_id, query)
