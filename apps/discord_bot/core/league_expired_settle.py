# apps/discord_bot/core/league_expired_settle.py
"""Post-window league fixture settle: auto-sim or 026 forfeit (048 / US-42.5)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from leagues import (
    ExpiredSettleMode,
    decide_expired_settle,
    double_forfeit,
    single_forfeit,
)

from apps.discord_bot.core.squad_validity import human_club_xi_ok

logger = logging.getLogger(__name__)


async def _side_ok(db: Any, player: dict, team_id: int) -> bool:
    """AI always eligible; humans via human_club_xi_ok."""
    if player.get("is_ai"):
        return True
    return await human_club_xi_ok(db, int(team_id))


async def _write_forfeit(
    db: Any,
    fixture_id: str,
    *,
    home_score: int,
    away_score: int,
    result_type: str,
) -> None:
    await db.table("league_fixtures").update({
        "home_score": home_score,
        "away_score": away_score,
        "is_played": True,
        "status": "forfeit",
        "result_type": result_type,
        # CHECK only allows manual|auto_sim (064); forfeit distinguished via result_type
        "resolved_by": "auto_sim",
        "played_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", fixture_id).eq("is_played", False).execute()


async def settle_expired_fixture(
    bot: Any,
    db: Any,
    guild: Any,
    fixture: dict,
    *,
    season_threads: Any | None,
    silent: bool = False,
) -> bool:
    """
    Settle one expired unplayed fixture via auto-sim or forfeit.

    Returns True when the fixture ends played. Never forfeits for missing
    threads — use silent=True when guild is OK but threads are absent.
    """
    from apps.discord_bot.core.match_runs import get_active_fixture_run

    fixture_id = fixture["id"]
    check = await (
        db.table("league_fixtures")
        .select("is_played")
        .eq("id", fixture_id)
        .maybe_single()
        .execute()
    )
    if (check.data or {}).get("is_played"):
        return False

    if await get_active_fixture_run(db, fixture_id):
        logger.info("Skipping expired settle for fixture %s — active match run", fixture_id)
        return False

    home_p = fixture.get("home") or {}
    away_p = fixture.get("away") or {}
    home_ok = await _side_ok(db, home_p, int(fixture["home_team_id"]))
    away_ok = await _side_ok(db, away_p, int(fixture["away_team_id"]))
    mode = decide_expired_settle(home_ok=home_ok, away_ok=away_ok)

    if mode == ExpiredSettleMode.DOUBLE_FORFEIT:
        outcome = double_forfeit()
        await _write_forfeit(
            db,
            fixture_id,
            home_score=outcome.home_score,
            away_score=outcome.away_score,
            result_type="double_forfeit",
        )
        logger.info("Expired fixture %s settled double_forfeit 0-0", fixture_id)
        return True

    if mode == ExpiredSettleMode.FORFEIT_HOME:
        outcome = single_forfeit(illegal_is_home=True)
        await _write_forfeit(
            db,
            fixture_id,
            home_score=outcome.home_score,
            away_score=outcome.away_score,
            result_type="forfeit",
        )
        logger.info(
            "Expired fixture %s forfeit (home illegal) %s-%s",
            fixture_id,
            outcome.home_score,
            outcome.away_score,
        )
        return True

    if mode == ExpiredSettleMode.FORFEIT_AWAY:
        outcome = single_forfeit(illegal_is_home=False)
        await _write_forfeit(
            db,
            fixture_id,
            home_score=outcome.home_score,
            away_score=outcome.away_score,
            result_type="forfeit",
        )
        logger.info(
            "Expired fixture %s forfeit (away illegal) %s-%s",
            fixture_id,
            outcome.home_score,
            outcome.away_score,
        )
        return True

    # Both eligible → auto-sim (silent when threads missing)
    from apps.discord_bot.cogs.battle_cog import LeagueMatchHandler, run_league_match_simulation

    use_silent = silent or season_threads is None
    if use_silent:

        class _SilentHandler:
            commentary_thread = None
            season_id = fixture["season_id"]
            journal_thread = None
            journal_standings_msg_id = None

            async def start_match(self, *a, **k):
                return None

            async def update_ticker(self, *a, **k):
                return None

            async def finalize_match(self, *a, **k):
                return None

        handler: Any = _SilentHandler()
    else:
        handler = LeagueMatchHandler(
            commentary_thread=season_threads.commentary_thread,
            fixture_id=fixture_id,
            season_id=fixture["season_id"],
            journal_thread=season_threads.journal_thread,
            journal_standings_msg_id=season_threads.journal_standings_message_id,
        )

    try:
        await run_league_match_simulation(
            bot=bot,
            db=db,
            guild=guild,
            fixture=fixture,
            active_player_id=None,
            handler=handler,
            silent=use_silent,
        )
    except Exception:
        logger.exception("Expired auto-sim failed for fixture %s", fixture_id)
        active = await get_active_fixture_run(db, fixture_id)
        if active:
            from apps.discord_bot.core.match_runs import abandon_run

            try:
                await abandon_run(db, active["id"], reason="auto_sim_failed")
            except Exception:
                logger.exception("abandon_match_run failed for fixture %s", fixture_id)
        return False

    after = await (
        db.table("league_fixtures")
        .select("is_played")
        .eq("id", fixture_id)
        .maybe_single()
        .execute()
    )
    settled = bool((after.data or {}).get("is_played"))
    if not settled:
        logger.warning(
            "Expired sim did not settle fixture %s (unexpected skip)", fixture_id
        )
    return settled
