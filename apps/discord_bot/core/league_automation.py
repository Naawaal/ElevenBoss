# apps/discord_bot/core/league_automation.py
"""League Automation orchestrator + shared Dynamics season start (021)."""
from __future__ import annotations

import logging
import random
from datetime import datetime, timezone
from typing import Any

import discord
from discord.ext import commands
from match_engine import generate_round_robin_fixtures

from apps.discord_bot.db.client import get_client
from leagues import (
    assign_dynamics_windows,
    can_open_auto_registration,
    evaluate_registration_close,
    next_monday_0005_utc,
    registration_closes_at,
    seat_humans_into_divisions,
)

logger = logging.getLogger(__name__)


def _parse_dt(raw: Any) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        if raw.tzinfo is None:
            return raw.replace(tzinfo=timezone.utc)
        return raw.astimezone(timezone.utc)
    if isinstance(raw, str):
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _cfg(season: dict) -> dict:
    raw = season.get("config_json") or {}
    return dict(raw) if isinstance(raw, dict) else {}


async def _count_registered_humans(db: Any, guild_id: int) -> int:
    regs_res = await (
        db.table("league_members")
        .select("player_id, players(is_ai)")
        .eq("guild_id", guild_id)
        .execute()
    )
    n = 0
    for r in regs_res.data or []:
        if not (r.get("players") or {}).get("is_ai"):
            n += 1
    return n


async def _resolve_guild(bot: commands.Bot, guild_id: int) -> discord.Guild | None:
    guild = bot.get_guild(int(guild_id))
    if guild:
        return guild
    try:
        return await bot.fetch_guild(int(guild_id))
    except Exception:
        return None


async def open_auto_registration(bot: commands.Bot, db: Any, guild_id: int) -> bool:
    """Open a 48h automation-owned registration season. Returns True on success."""
    from apps.discord_bot.core.economy_rpc import get_game_config_int, guild_automation_effective
    from apps.discord_bot.core.league_announce import (
        post_registration_open,
        resolve_announce_targets,
        _set_automation_error,
    )

    if not await guild_automation_effective(db, guild_id):
        return False

    guild = await _resolve_guild(bot, guild_id)
    if not guild:
        await _set_automation_error(db, guild_id, "Guild not reachable for auto registration")
        return False

    channel, _, config = await resolve_announce_targets(db, guild)
    if not channel:
        await _set_automation_error(db, guild_id, "League announce channel missing — cannot open registration")
        return False

    now = datetime.now(timezone.utc)
    next_at = _parse_dt(config.get("next_auto_registration_at"))

    await db.table("leagues").upsert(
        {"guild_id": guild_id, "name": guild.name},
        on_conflict="guild_id",
    ).execute()
    league_res = await db.table("leagues").select("id").eq("guild_id", guild_id).maybe_single().execute()
    if not league_res or not league_res.data:
        return False
    league_id = league_res.data["id"]

    existing = await (
        db.table("league_seasons")
        .select("id")
        .eq("league_id", league_id)
        .in_("status", ["active", "registration", "paused"])
        .execute()
    )
    has_active_or_reg = bool(existing.data)
    if not can_open_auto_registration(now, next_at, has_active_or_reg):
        return False

    hours = await get_game_config_int(db, "league_automation_registration_hours", 48)
    closes = registration_closes_at(now, hours)
    seasons_res = await (
        db.table("league_seasons")
        .select("season_number")
        .eq("league_id", league_id)
        .order("season_number", desc=True)
        .limit(1)
        .execute()
    )
    next_num = (seasons_res.data[0]["season_number"] + 1) if seasons_res.data else 1

    await db.table("league_seasons").insert({
        "league_id": league_id,
        "season_number": next_num,
        "status": "registration",
        "current_matchday": 0,
        "total_matchdays": 0,
        "duration_days": 14,
        "end_time": closes.isoformat(),
        "pacing_mode": "dynamics",
        "config_json": {
            "automation": True,
            "registration_closes_at": closes.isoformat(),
            "max_clubs": 8,
            "duration_days": 14,
            "bot_fill": True,
            "entry_fee_coins": 0,
        },
    }).execute()

    await db.table("guild_config").update({
        "next_auto_registration_at": None,
        "automation_last_error": None,
        "league_status": "registration",
    }).eq("guild_id", guild_id).execute()

    await post_registration_open(bot, db, guild, season_number=next_num, closes_at=closes)
    logger.info("Opened auto registration Season %s for guild %s", next_num, guild_id)
    return True


async def start_dynamics_season_from_registration(
    bot: commands.Bot,
    db: Any,
    guild: discord.Guild,
    *,
    automation: bool,
    interaction: discord.Interaction | None = None,
) -> dict:
    """Shared season start — Dynamics when ``automation`` or dynamics flag on.

    Returns ``{ok, error, season_id, season_number, division_count, ...}``.
    """
    from apps.discord_bot.cogs.league_cog import BOT_NAMES, fetch_standings, send_league_announcement
    from apps.discord_bot.core.economy_rpc import league_dynamics_enabled
    from apps.discord_bot.core.league_announcement import build_season_start_message
    from apps.discord_bot.core.league_journal import create_season_threads
    from leagues import format_standings_table

    guild_id = guild.id
    dynamics = True if automation else await league_dynamics_enabled(db)

    if dynamics:
        regs_res = await (
            db.table("league_members")
            .select("player_id, seasonal_division_tier, registered_at, players(*)")
            .eq("guild_id", guild_id)
            .execute()
        )
        regs = regs_res.data or []
        regs.sort(
            key=lambda r: (
                int(r.get("seasonal_division_tier") or 1),
                r.get("registered_at") or "",
            )
        )
        guild_members = [r["players"] for r in regs if r.get("players")]
    else:
        regs_res = await db.table("league_members").select("player_id, players(*)").eq(
            "guild_id", guild_id
        ).execute()
        regs = regs_res.data or []
        guild_members = [r["players"] for r in regs if r.get("players")]

    if len(guild_members) < 2:
        return {
            "ok": False,
            "error": (
                f"Cannot start season. At least **2 registered managers** required "
                f"(current: **{len(guild_members)}**)."
            ),
        }

    h_count = len(guild_members)

    await db.table("leagues").upsert(
        {"guild_id": guild_id, "name": guild.name},
        on_conflict="guild_id",
    ).execute()
    league_res = await db.table("leagues").select("id").eq("guild_id", guild_id).maybe_single().execute()
    if not league_res or not league_res.data:
        return {"ok": False, "error": "Failed to retrieve league record."}
    league_id = league_res.data["id"]

    reg_season_res = await (
        db.table("league_seasons")
        .select("*")
        .eq("league_id", league_id)
        .eq("status", "registration")
        .maybe_single()
        .execute()
    )
    reg_season = reg_season_res.data if reg_season_res else None
    cfg = _cfg(reg_season) if reg_season else {}
    bot_fill = cfg.get("bot_fill", True)
    warning_str = ""
    target_size = 8
    ai_needed = 0

    if dynamics:
        duration_days = 14
        total_weeks = 14
        pacing_mode = "dynamics"
        cfg["duration_days"] = 14
        cfg["max_clubs"] = 8
        if not bot_fill:
            return {"ok": False, "error": "Dynamics seasons require bot fill (8 clubs per division)."}
        bot_fill = True
        cfg["bot_fill"] = True
    else:
        pacing_mode = "legacy"
        if cfg.get("max_clubs"):
            target_size = int(cfg["max_clubs"])
        elif h_count <= 8:
            target_size = 8
        elif h_count <= 10:
            target_size = 10
        elif h_count <= 12:
            target_size = 12
        else:
            target_size = 16

        duration_days = int(cfg.get("duration_days", 28))

        if h_count > 16:
            guild_members = guild_members[:16]
            h_count = 16
            warning_str = "⚠️ **Note**: Guild has more than 16 registered managers. Limiting to the first 16.\n\n"

        ai_needed = target_size - h_count if bot_fill else 0
        if h_count + ai_needed < 2:
            return {"ok": False, "error": "Need at least 2 clubs to start."}
        if not bot_fill and h_count < target_size:
            return {
                "ok": False,
                "error": f"Need **{target_size}** registered managers (have {h_count}). Enable bot fill or wait.",
            }
        total_weeks = (target_size - 1) * 2

    if automation:
        cfg["automation"] = True

    if reg_season:
        await db.table("league_seasons").delete().eq("id", reg_season["id"]).execute()

    seasons_res = await (
        db.table("league_seasons")
        .select("season_number")
        .eq("league_id", league_id)
        .order("season_number", desc=True)
        .limit(1)
        .execute()
    )
    next_season_num = 1
    if seasons_res.data:
        next_season_num = seasons_res.data[0]["season_number"] + 1

    now = datetime.now(timezone.utc)
    season_insert = await db.table("league_seasons").insert({
        "league_id": league_id,
        "season_number": next_season_num,
        "status": "active",
        "current_matchday": 1,
        "total_matchdays": total_weeks,
        "duration_days": duration_days,
        "start_time": now.isoformat(),
        "pacing_mode": pacing_mode,
        "config_json": cfg or {
            "max_clubs": 8 if dynamics else target_size,
            "duration_days": duration_days,
            "bot_fill": bot_fill,
            **({"automation": True} if automation else {}),
        },
    }).execute()

    season_id = season_insert.data[0]["id"]
    used_bot_names: set[str] = set()

    # Local AI helpers (avoid circular import with admin_cog)
    async def _next_ai_discord_id() -> int:
        min_p_res = await db.table("players").select("discord_id").order(
            "discord_id", desc=False
        ).limit(1).execute()
        current_min = min_p_res.data[0]["discord_id"] if min_p_res.data else 0
        if current_min > 0:
            current_min = 0
        return current_min - 1

    async def _insert_ai_club(*, ai_id: int) -> dict:
        available = [n for n in BOT_NAMES if n not in used_bot_names] or list(BOT_NAMES)
        bot_name = random.choice(available)
        used_bot_names.add(bot_name)
        ai_p = {
            "discord_id": ai_id,
            "username": bot_name,
            "club_name": bot_name,
            "manager_name": "AI Coach",
            "is_ai": True,
            "ai_rating": 60.0,
        }
        await db.table("players").insert(ai_p).execute()
        return ai_p

    next_ai_id = await _next_ai_discord_id()
    tier_club_ids: dict[int, list[int]] = {}

    async def _seat_and_insert(human_ids: list[int]) -> dict[int, list[int]]:
        nonlocal next_ai_id
        tiers_map: dict[int, list[int]] = {}
        if dynamics:
            human_tiers = seat_humans_into_divisions(human_ids, clubs_per_div=8)
            for tier_idx, chunk in enumerate(human_tiers, start=1):
                clubs = list(chunk)
                need = 8 - len(clubs)
                for _ in range(need):
                    ai_p = await _insert_ai_club(ai_id=next_ai_id)
                    next_ai_id -= 1
                    clubs.append(ai_p["discord_id"])
                tiers_map[tier_idx] = clubs
                for pid in clubs:
                    await db.table("league_participants").insert({
                        "season_id": season_id,
                        "player_id": pid,
                        "division_tier": tier_idx,
                    }).execute()
        else:
            clubs = list(human_ids)
            for _ in range(ai_needed):
                ai_p = await _insert_ai_club(ai_id=next_ai_id)
                next_ai_id -= 1
                clubs.append(ai_p["discord_id"])
            tiers_map[1] = clubs
            for pid in clubs:
                await db.table("league_participants").insert({
                    "season_id": season_id,
                    "player_id": pid,
                    "division_tier": 1,
                }).execute()
        return tiers_map

    human_ids = [int(p["discord_id"]) for p in guild_members]
    if dynamics:
        ai_needed = 0

    tier_club_ids = await _seat_and_insert(human_ids)

    fee_res = await db.rpc("charge_league_entry_fees", {"p_season_id": season_id}).execute()
    fee_data = fee_res.data or {}
    skipped = fee_data.get("skipped") or []
    charged = fee_data.get("charged") or []

    parts_res = await db.table("league_participants").select(
        "player_id, division_tier, players(is_ai)"
    ).eq("season_id", season_id).execute()
    remaining_humans = [
        p for p in (parts_res.data or [])
        if not (p.get("players") or {}).get("is_ai")
    ]
    if len(remaining_humans) < 2:
        await db.table("league_seasons").delete().eq("id", season_id).execute()
        skip_note = ""
        if skipped:
            skip_note = f"\nSkipped ({len(skipped)}): insufficient coins for entry fee."
        return {
            "ok": False,
            "error": (
                "Season aborted: fewer than **2** managers remain after entry fee collection."
                + skip_note
            ),
        }

    if skipped:
        rem_ids = [int(p["player_id"]) for p in remaining_humans]
        if dynamics:
            order_index = {hid: i for i, hid in enumerate(human_ids)}
            rem_ids.sort(key=lambda x: order_index.get(x, 10**9))
        await db.table("league_participants").delete().eq("season_id", season_id).execute()
        if not dynamics:
            h_count = len(rem_ids)
            if cfg.get("max_clubs"):
                target_size = int(cfg["max_clubs"])
            elif h_count <= 8:
                target_size = 8
            elif h_count <= 10:
                target_size = 10
            elif h_count <= 12:
                target_size = 12
            else:
                target_size = 16
            ai_needed = max(0, target_size - h_count) if bot_fill else 0
            total_weeks = (len(rem_ids) + ai_needed - 1) * 2
            await db.table("league_seasons").update({"total_matchdays": total_weeks}).eq(
                "id", season_id
            ).execute()
        tier_club_ids = await _seat_and_insert(rem_ids)

    parts_res = await db.table("league_participants").select(
        "player_id, division_tier, players(is_ai)"
    ).eq("season_id", season_id).execute()
    remaining_humans = [
        p for p in (parts_res.data or [])
        if not (p.get("players") or {}).get("is_ai")
    ]
    participant_ids = [int(p["player_id"]) for p in (parts_res.data or [])]
    h_count = len(remaining_humans)
    ai_count = len(participant_ids) - h_count
    target_size = len(participant_ids)

    tier_club_ids = {}
    for p in parts_res.data or []:
        tier = int(p.get("division_tier") or 1)
        tier_club_ids.setdefault(tier, []).append(int(p["player_id"]))
    division_count = len(tier_club_ids) if tier_club_ids else 1

    fee_lines = ""
    if charged:
        fee_lines += f"\n💰 Entry fees collected from **{len(charged)}** manager(s)."
    if skipped:
        fee_lines += f"\n⚠️ **{len(skipped)}** manager(s) skipped (insufficient coins)."

    await db.rpc("scale_season_ai_opponents", {"p_season_id": season_id}).execute()

    from datetime import timedelta

    if dynamics:
        windows = assign_dynamics_windows(now, 14)
        window_by_md = {w["matchday"]: w for w in windows}
        for _tier, clubs in sorted(tier_club_ids.items()):
            generated = generate_round_robin_fixtures(
                [str(pid) for pid in clubs], double_round_robin=True
            )
            for gf in generated:
                w = window_by_md[gf.week]
                await db.table("league_fixtures").insert({
                    "season_id": season_id,
                    "matchday": gf.week,
                    "home_team_id": int(gf.home_club_id),
                    "away_team_id": int(gf.away_club_id),
                    "window_start": w["window_start"].isoformat(),
                    "window_end": w["window_end"].isoformat(),
                    "is_played": False,
                }).execute()
        total_weeks = 14
    else:
        generated = generate_round_robin_fixtures(
            [str(pid) for pid in participant_ids], double_round_robin=True
        )
        window_duration = timedelta(days=duration_days) / total_weeks
        for gf in generated:
            w_start = now + (gf.week - 1) * window_duration
            w_end = now + gf.week * window_duration
            await db.table("league_fixtures").insert({
                "season_id": season_id,
                "matchday": gf.week,
                "home_team_id": int(gf.home_club_id),
                "away_team_id": int(gf.away_club_id),
                "window_start": w_start.isoformat(),
                "window_end": w_end.isoformat(),
                "is_played": False,
            }).execute()

    await db.table("guild_config").update({"league_status": "active"}).eq(
        "guild_id", guild_id
    ).execute()

    if dynamics:
        div_note = (
            f"Divisions: **{division_count}** (8 clubs each)\n"
            if division_count > 1
            else "Division: **1** table (8 clubs)\n"
        )
        success_body = (
            f"{warning_str}🏆 **Season {next_season_num} Started!** (League Dynamics)\n"
            f"{div_note}"
            f"Total Clubs: **{target_size}** (Humans: {h_count}, AIs: {ai_count})\n"
            f"**14-day** season · **14** matchdays · hard close **00:00 UTC** each day\n"
            f"Fixtures generated per division with synced matchday windows.{fee_lines}"
        )
    else:
        success_body = (
            f"{warning_str}🏆 **Season {next_season_num} Started!**\n"
            f"Total Teams: **{target_size}** (Humans: {h_count}, AIs: {ai_count})\n"
            f"Matchdays: **{total_weeks}** (each lasting {duration_days * 24 / total_weeks:.1f} hours)\n"
            f"Fixtures and standings generated successfully.{fee_lines}"
        )

    # Announcement + dual threads (US-28)
    config_res = await db.table("guild_config").select("league_channel_id").eq(
        "guild_id", guild_id
    ).maybe_single().execute()
    chan_id = config_res.data.get("league_channel_id") if config_res and config_res.data else None
    if chan_id:
        league_name = guild.name
        league_row = await db.table("leagues").select("name").eq("guild_id", guild_id).maybe_single().execute()
        if league_row and league_row.data:
            league_name = league_row.data.get("name") or league_name

        if automation:
            from apps.discord_bot.core.league_announce import post_season_start_digest

            await post_season_start_digest(
                bot, db, guild,
                season_number=next_season_num,
                division_count=division_count,
                total_matchdays=total_weeks,
            )
            # Still create threads when channel exists — use announce message if any
            channel = guild.get_channel(int(chan_id))
            if channel:
                fixtures_res = await db.table("league_fixtures").select("*").eq(
                    "season_id", season_id
                ).execute()
                all_fixtures = fixtures_res.data or []
                if dynamics and division_count > 1:
                    chunks = []
                    for t in sorted(tier_club_ids.keys()):
                        st = await fetch_standings(db, season_id, division_tier=t)
                        chunks.append(
                            f"— Division {t} —\n{format_standings_table(st, all_fixtures, limit=8)}"
                        )
                    table_text = "\n\n".join(chunks)
                else:
                    standings = await fetch_standings(
                        db, season_id, division_tier=1 if dynamics else None
                    )
                    table_text = format_standings_table(standings, all_fixtures, limit=10)
                await create_season_threads(
                    bot, db, guild, channel,
                    season_id=season_id,
                    league_name=league_name,
                    initial_table_text=table_text,
                    announcement_message_id=None,
                )
        else:
            ann_body = build_season_start_message(
                league_name,
                next_season_num,
                total_weeks,
                dynamics=dynamics,
                division_count=division_count,
            )
            ann_msg = await send_league_announcement(guild, chan_id, None, ann_body)
            channel = guild.get_channel(int(chan_id))
            if channel and ann_msg:
                fixtures_res = await db.table("league_fixtures").select("*").eq(
                    "season_id", season_id
                ).execute()
                all_fixtures = fixtures_res.data or []
                if dynamics and division_count > 1:
                    chunks = []
                    for t in sorted(tier_club_ids.keys()):
                        st = await fetch_standings(db, season_id, division_tier=t)
                        chunks.append(
                            f"— Division {t} —\n{format_standings_table(st, all_fixtures, limit=8)}"
                        )
                    table_text = "\n\n".join(chunks)
                else:
                    standings = await fetch_standings(
                        db, season_id, division_tier=1 if dynamics else None
                    )
                    table_text = format_standings_table(standings, all_fixtures, limit=10)
                threads = await create_season_threads(
                    bot, db, guild, channel,
                    season_id=season_id,
                    league_name=league_name,
                    initial_table_text=table_text,
                    announcement_message_id=ann_msg.id,
                )
                if not threads:
                    logger.error(
                        "US-28: dual threads failed for guild %s season %s",
                        guild_id,
                        season_id,
                    )
            elif not ann_msg:
                logger.warning("Season announcement not sent — channel %s unavailable", chan_id)

    return {
        "ok": True,
        "error": None,
        "season_id": season_id,
        "season_number": next_season_num,
        "division_count": division_count,
        "total_matchdays": total_weeks,
        "success_body": success_body,
        "dynamics": dynamics,
        "h_count": h_count,
        "ai_count": ai_count,
    }


async def _digest_candidate_matchday(season: dict) -> int | None:
    """Infer which matchday (if any) just settled for announce digests."""
    cfg = _cfg(season)
    last = int(cfg.get("last_digest_matchday") or 0)
    status = season.get("status")
    total = int(season.get("total_matchdays") or 0)
    curr = int(season.get("current_matchday") or 0)
    if status == "completed" and total > 0:
        candidate = total
    elif status in ("active", "paused") and curr > 1:
        candidate = curr - 1
    else:
        return None
    if candidate > last:
        return candidate
    return None


async def _phase_a_dynamics_ticks(
    bot: commands.Bot,
    db: Any,
    *,
    global_automation: bool,
) -> set[int]:
    """Tick all Dynamics seasons. Returns guild_ids to queue open-registration."""
    from apps.discord_bot.cogs.league_cog import auto_sim_expired_fixtures, update_current_matchday
    from apps.discord_bot.core.economy_rpc import guild_automation_effective
    from apps.discord_bot.core.league_announce import (
        post_daily_tick_digest,
        post_season_concluded,
        resolve_announce_targets,
    )

    queue_open: set[int] = set()
    seasons_res = await (
        db.table("league_seasons")
        .select("*")
        .eq("status", "active")
        .eq("pacing_mode", "dynamics")
        .execute()
    )
    for season in seasons_res.data or []:
        # Skip paused — query is status=active only; paused not included
        season_id = season["id"]
        league_res = await db.table("leagues").select("guild_id").eq(
            "id", season["league_id"]
        ).maybe_single().execute()
        guild_id = (league_res.data or {}).get("guild_id") if league_res else None
        if guild_id is None:
            continue
        guild_id = int(guild_id)

        try:
            await auto_sim_expired_fixtures(db, season_id, bot)
            await update_current_matchday(db, season_id, bot=bot)
        except Exception:
            logger.exception("Dynamics tick failed season=%s", season_id)
            continue

        season_res = await db.table("league_seasons").select("*").eq(
            "id", season_id
        ).maybe_single().execute()
        season = season_res.data if season_res else None
        if not season:
            continue

        cfg = _cfg(season)
        automation_owned = bool(cfg.get("automation"))
        if season.get("status") == "completed" and automation_owned:
            queue_open.add(guild_id)

        if not global_automation:
            continue

        effective = await guild_automation_effective(db, guild_id)
        if not effective:
            continue

        guild = await _resolve_guild(bot, guild_id)
        if not guild:
            continue
        channel, _, _ = await resolve_announce_targets(db, guild)
        if not channel:
            continue

        candidate = await _digest_candidate_matchday(season)
        if candidate is None:
            if season.get("status") == "completed" and automation_owned:
                await post_season_concluded(
                    bot, db, guild,
                    season_number=int(season.get("season_number") or 0),
                    registration_opening=True,
                )
            continue

        season_done = season.get("status") == "completed"
        try:
            ok = await post_daily_tick_digest(
                bot, db, guild,
                season_id=season_id,
                completed_matchday=candidate,
                total_matchdays=int(season.get("total_matchdays") or 14),
                season_completed=season_done,
            )
            if ok:
                cfg["last_digest_matchday"] = candidate
                await db.table("league_seasons").update({"config_json": cfg}).eq(
                    "id", season_id
                ).execute()
            if season_done and automation_owned:
                await post_season_concluded(
                    bot, db, guild,
                    season_number=int(season.get("season_number") or 0),
                    registration_opening=True,
                )
        except Exception:
            logger.exception("Digest post failed season=%s md=%s", season_id, candidate)

    return queue_open


async def _phase_b_close_registration(bot: commands.Bot, db: Any) -> None:
    from apps.discord_bot.core.economy_rpc import get_game_config_int
    from apps.discord_bot.core.league_announce import post_registration_failed_under_min

    now = datetime.now(timezone.utc)
    min_humans = await get_game_config_int(db, "league_min_humans", 2)

    seasons_res = await (
        db.table("league_seasons")
        .select("*")
        .eq("status", "registration")
        .execute()
    )
    for season in seasons_res.data or []:
        cfg = _cfg(season)
        if not cfg.get("automation"):
            continue
        closes = _parse_dt(cfg.get("registration_closes_at")) or _parse_dt(season.get("end_time"))
        if closes is None or now < closes:
            continue

        league_res = await db.table("leagues").select("guild_id").eq(
            "id", season["league_id"]
        ).maybe_single().execute()
        guild_id = (league_res.data or {}).get("guild_id") if league_res else None
        if guild_id is None:
            continue
        guild_id = int(guild_id)
        guild = await _resolve_guild(bot, guild_id)
        if not guild:
            continue

        human_count = await _count_registered_humans(db, guild_id)
        decision = evaluate_registration_close(human_count, min_humans)
        season_number = int(season.get("season_number") or 0)

        if decision == "start":
            result = await start_dynamics_season_from_registration(
                bot, db, guild, automation=True, interaction=None
            )
            if not result.get("ok"):
                logger.warning(
                    "Auto start failed guild=%s: %s", guild_id, result.get("error")
                )
            continue

        # fail under min
        next_at = next_monday_0005_utc(now)
        await db.table("league_seasons").delete().eq("id", season["id"]).execute()
        await db.table("guild_config").update({
            "next_auto_registration_at": next_at.isoformat(),
            "league_status": "inactive",
        }).eq("guild_id", guild_id).execute()
        await post_registration_failed_under_min(
            bot, db, guild,
            season_number=season_number,
            min_humans=min_humans,
            human_count=human_count,
            next_at=next_at,
        )
        logger.info(
            "Auto registration failed under min guild=%s had=%s next=%s",
            guild_id, human_count, next_at.isoformat(),
        )


async def _phase_c_open_registration(
    bot: commands.Bot,
    db: Any,
    *,
    extra_guild_ids: set[int] | None = None,
) -> None:
    from apps.discord_bot.core.economy_rpc import guild_automation_effective
    from apps.discord_bot.core.league_announce import resolve_announce_targets, _set_automation_error

    now = datetime.now(timezone.utc)
    configs_res = await db.table("guild_config").select(
        "guild_id, league_channel_id, next_auto_registration_at, league_automation_enabled"
    ).execute()
    candidate_ids = {int(c["guild_id"]) for c in (configs_res.data or []) if c.get("guild_id")}
    if extra_guild_ids:
        candidate_ids |= {int(g) for g in extra_guild_ids}

    for guild_id in candidate_ids:
        try:
            if not await guild_automation_effective(db, guild_id):
                continue
            guild = await _resolve_guild(bot, guild_id)
            if not guild:
                continue
            channel, _, config = await resolve_announce_targets(db, guild)
            if not channel:
                await _set_automation_error(
                    db, guild_id, "League announce channel missing — cannot open registration"
                )
                continue
            next_at = _parse_dt(config.get("next_auto_registration_at"))

            league_res = await db.table("leagues").select("id").eq(
                "guild_id", guild_id
            ).maybe_single().execute()
            has_active_or_reg = False
            if league_res and league_res.data:
                existing = await (
                    db.table("league_seasons")
                    .select("id")
                    .eq("league_id", league_res.data["id"])
                    .in_("status", ["active", "registration", "paused"])
                    .execute()
                )
                has_active_or_reg = bool(existing.data)

            if not can_open_auto_registration(now, next_at, has_active_or_reg):
                continue

            await open_auto_registration(bot, db, guild_id)
        except Exception:
            logger.exception("Phase C open registration failed guild=%s", guild_id)


async def run_league_state_machine(bot: commands.Bot) -> None:
    """Daily 00:05 UTC orchestrator — Dynamics ticks + automation lifecycle."""
    from apps.discord_bot.core.economy_rpc import league_automation_enabled

    logger.info("Executing league state machine...")
    try:
        db = await get_client()
        global_on = await league_automation_enabled(db)

        # Phase A always runs Dynamics ticks (even when global flag off)
        queue_open = await _phase_a_dynamics_ticks(bot, db, global_automation=global_on)

        if not global_on:
            logger.info("League automation global flag off — skipped open/start/digest")
            return

        await _phase_b_close_registration(bot, db)
        await _phase_c_open_registration(bot, db, extra_guild_ids=queue_open)
        logger.info("League state machine completed.")
    except Exception:
        logger.exception("League state machine failed")
