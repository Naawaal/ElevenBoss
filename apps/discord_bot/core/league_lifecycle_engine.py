# apps/discord_bot/core/league_lifecycle_engine.py
"""LeagueLifecycleEngine — authoritative V1 lifecycle transitions (026)."""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from leagues import (
    assign_lifecycle_windows,
    double_forfeit,
    fixture_resolve,
    matchday_complete,
    matchday_lock,
    matchday_open,
    rebase_windows,
    season_activate,
    season_prepare,
    season_registration_close,
    season_settle,
    single_forfeit,
)

logger = logging.getLogger(__name__)

V1_RULESET = "lifecycle-v1"


def _utc(raw: Any) -> datetime | None:
    if isinstance(raw, datetime):
        return raw.astimezone(timezone.utc) if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    if isinstance(raw, str):
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
        except ValueError:
            return None
    return None


async def _run_once(
    db: Any,
    key: str,
    callback: Any,
    *,
    season_id: str,
    transition: str,
    trigger: str,
    metadata: dict | None = None,
    retryable: bool = False,
) -> bool:
    """Run one transition at most once and leave an auditable terminal record.

    When ``retryable=True``, failures delete the operation row so a later wake-up
    can re-acquire (infra/sim failures must not burn the lease forever).
    """
    if not await acquire_operation(db, key):
        return False
    try:
        await callback()
        await write_transition_journal(
            db, season_id=season_id, transition=transition, operation_key=key,
            trigger=trigger, ruleset_version=V1_RULESET, metadata=metadata,
        )
        await complete_operation(db, key, ok=True)
        return True
    except Exception as exc:
        logger.exception("lifecycle transition failed key=%s", key)
        if retryable:
            try:
                await db.table("league_operation_runs").delete().eq(
                    "operation_key", key
                ).execute()
            except Exception:
                logger.exception("failed to clear retryable op key=%s", key)
                await complete_operation(db, key, ok=False, error=str(exc)[:1000])
        else:
            await complete_operation(db, key, ok=False, error=str(exc)[:1000])
        return False


async def acquire_operation(db: Any, operation_key: str, *, worker_id: str | None = None) -> bool:
    """Insert operation run; return True if this worker acquired the key."""
    try:
        await (
            db.table("league_operation_runs")
            .insert({
                "operation_key": operation_key,
                "status": "started",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "worker_id": worker_id,
            })
            .execute()
        )
        return True
    except Exception:
        # Unique violation → already started
        logger.debug("operation already acquired: %s", operation_key)
        return False


async def complete_operation(
    db: Any,
    operation_key: str,
    *,
    ok: bool,
    error: str | None = None,
) -> None:
    await (
        db.table("league_operation_runs")
        .update({
            "status": "succeeded" if ok else "failed",
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "error": error,
        })
        .eq("operation_key", operation_key)
        .execute()
    )


async def write_transition_journal(
    db: Any,
    *,
    season_id: str | None,
    transition: str,
    operation_key: str,
    trigger: str,
    ruleset_version: str,
    metadata: dict | None = None,
) -> None:
    await (
        db.table("league_transition_journal")
        .insert({
            "season_id": season_id,
            "transition": transition,
            "operation_key": operation_key,
            "trigger": trigger,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "ruleset_version": ruleset_version,
            "metadata": metadata or {},
        })
        .execute()
    )


async def enqueue_outbox(
    db: Any,
    *,
    event_type: str,
    payload: dict,
    dedupe_key: str,
) -> None:
    try:
        await (
            db.table("league_outbox")
            .insert({
                "event_type": event_type,
                "payload": payload,
                "dedupe_key": dedupe_key,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "attempts": 0,
            })
            .execute()
        )
    except Exception:
        logger.debug("outbox dedupe hit: %s", dedupe_key)


async def open_registration_season(
    db: Any,
    *,
    league_id: str,
    guild_id: int,
    registration_hours: int = 48,
    trigger: str = "admin",
) -> dict[str, Any]:
    """Open a V1 ``registration_open`` season with phase deadlines (idempotent-ish)."""
    now = datetime.now(timezone.utc)
    living = await (
        db.table("league_seasons")
        .select("id,status,pacing_mode")
        .eq("league_id", league_id)
        .in_(
            "status",
            [
                "registration",
                "registration_open",
                "registration_locked",
                "preparing",
                "active",
                "paused",
                "settling",
            ],
        )
        .execute()
    )
    if living.data:
        return {"ok": False, "error": "A season is already in progress for this league."}

    seasons_res = await (
        db.table("league_seasons")
        .select("season_number")
        .eq("league_id", league_id)
        .order("season_number", desc=True)
        .limit(1)
        .execute()
    )
    next_num = (seasons_res.data[0]["season_number"] + 1) if seasons_res.data else 1
    closes = now + timedelta(hours=max(1, int(registration_hours)))
    deadlines = {
        "registration_end": closes.isoformat(),
    }
    insert = await db.table("league_seasons").insert({
        "league_id": league_id,
        "season_number": next_num,
        "status": "registration_open",
        "current_matchday": 0,
        "total_matchdays": 14,
        "duration_days": 14,
        "end_time": closes.isoformat(),
        "pacing_mode": "lifecycle_v1",
        "ruleset_version": V1_RULESET,
        "phase_deadlines": deadlines,
        "config_json": {
            "max_clubs": 8,
            "duration_days": 14,
            "bot_fill": True,
            "entry_fee_coins": 0,
            "registration_hours": registration_hours,
            "opened_by": trigger,
        },
    }).execute()
    season_row = (insert.data or [{}])[0]
    season_id = season_row.get("id")
    if season_id:
        await enqueue_outbox(
            db,
            event_type="registration_open",
            payload={"season_id": season_id, "guild_id": guild_id, "closes_at": closes.isoformat()},
            dedupe_key=f"{season_id}:registration_open",
        )
    await db.table("guild_config").update({
        "next_auto_registration_at": None,
        "league_status": "registration",
        "automation_last_error": None,
    }).eq("guild_id", guild_id).execute()
    return {
        "ok": True,
        "season_id": season_id,
        "season_number": next_num,
        "closes_at": closes,
    }


async def lock_registration(db: Any, season: dict, *, trigger: str = "deadline") -> bool:
    season_id = season["id"]

    async def transition() -> None:
        await db.table("league_registrations").update({"status": "locked"}).eq(
            "season_id", season_id
        ).eq("status", "registered").execute()
        await db.table("league_seasons").update({"status": "registration_locked"}).eq(
            "id", season_id
        ).execute()
        await enqueue_outbox(
            db, event_type="registration_locked", payload={"season_id": season_id},
            dedupe_key=f"{season_id}:registration_locked",
        )

    return await _run_once(
        db, season_registration_close(season_id), transition, season_id=season_id,
        transition="REGISTRATION_OPEN_TO_LOCKED", trigger=trigger,
    )


async def cancel_under_min(db: Any, season: dict, *, trigger: str = "deadline") -> bool:
    """Cancel a V1 registration; it is deliberately never a completed season."""
    season_id = season["id"]
    key = f"{season_id}:cancel_under_min"

    async def transition() -> None:
        await db.table("league_seasons").update({"status": "cancelled"}).eq(
            "id", season_id
        ).execute()
        await enqueue_outbox(
            db, event_type="registration_under_min",
            payload={"season_id": season_id}, dedupe_key=f"{season_id}:under_min",
        )

    return await _run_once(
        db, key, transition, season_id=season_id,
        transition="REGISTRATION_LOCKED_TO_CANCELLED", trigger=trigger,
    )


async def prepare_season(bot: Any, db: Any, season: dict, *, trigger: str = "deadline") -> bool:
    """Freeze config and build the V1 matchday calendar.

    Participant/bot creation remains delegated to the proven Dynamics start
    path until a single atomic V1 prepare RPC is introduced.  This handler
    only proceeds when registrations already produced participants.
    """
    from match_engine import generate_round_robin_fixtures

    season_id = season["id"]

    async def transition() -> None:
        league_res = await db.table("leagues").select("guild_id").eq(
            "id", season["league_id"]
        ).maybe_single().execute()
        guild_id = (league_res.data or {}).get("guild_id")
        cfg_res = await db.table("guild_config").select(
            "league_timezone,league_resolution_hour_local"
        ).eq("guild_id", guild_id).maybe_single().execute()
        cfg = cfg_res.data or {}
        from leagues.league_time import coalesce_league_time

        # 027: unconfigured guilds coalesce to UTC / 00:00 — never block preparation.
        eff = coalesce_league_time(cfg.get("league_timezone"), cfg.get("league_resolution_hour_local"))
        tz_name = eff.timezone
        hour = eff.resolution_hour_local
        if eff.used_defaults:
            logger.info(
                "prepare_season guild=%s using League Time defaults UTC/00:00",
                guild_id,
            )

        regs = await db.table("league_registrations").select(
            "player_id,registered_at,players(is_ai)"
        ).eq("season_id", season_id).eq("status", "locked").execute()
        humans = [r for r in (regs.data or []) if not (r.get("players") or {}).get("is_ai")]
        if len(humans) < 4:
            raise ValueError("minimum human registrations no longer met")

        import random

        from apps.discord_bot.cogs.league_cog import BOT_NAMES
        from leagues import seat_humans_into_divisions

        human_ids = [int(row["player_id"]) for row in humans]

        existing = await db.table("league_participants").select("player_id").eq(
            "season_id", season_id
        ).execute()
        if not (existing.data or []):
            await db.table("league_participants").insert([
                {
                    "season_id": season_id,
                    "player_id": pid,
                    "division_tier": 1,
                    "participant_type": "human",
                    "seed": index,
                }
                for index, pid in enumerate(human_ids, start=1)
            ]).execute()

            async def _next_ai_id() -> int:
                min_p = await db.table("players").select("discord_id").order(
                    "discord_id", desc=False
                ).limit(1).execute()
                current_min = min_p.data[0]["discord_id"] if min_p.data else 0
                if current_min > 0:
                    current_min = 0
                return int(current_min) - 1

            used_names: set[str] = set()
            next_ai = await _next_ai_id()
            tiers = seat_humans_into_divisions(human_ids, clubs_per_div=8) or [human_ids[:8]]
            for tier_idx, chunk in enumerate(tiers, start=1):
                clubs = list(chunk)
                await db.table("league_participants").update({
                    "division_tier": tier_idx,
                    "participant_type": "human",
                }).eq("season_id", season_id).in_("player_id", clubs).execute()
                while len(clubs) < 8:
                    available = [n for n in BOT_NAMES if n not in used_names] or list(BOT_NAMES)
                    bot_name = random.choice(available)
                    used_names.add(bot_name)
                    await db.table("players").insert({
                        "discord_id": next_ai,
                        "username": bot_name,
                        "club_name": bot_name,
                        "manager_name": "AI Coach",
                        "is_ai": True,
                        "ai_rating": 60.0,
                    }).execute()
                    await db.table("league_participants").insert({
                        "season_id": season_id,
                        "player_id": next_ai,
                        "division_tier": tier_idx,
                        "participant_type": "bot",
                        "seed": len(clubs) + 1,
                    }).execute()
                    clubs.append(next_ai)
                    next_ai -= 1
                div_res = await db.table("league_divisions").upsert(
                    {"season_id": season_id, "tier": tier_idx},
                    on_conflict="season_id,tier",
                ).execute()
                division = (div_res.data or [{}])[0]
                if division.get("id"):
                    await db.table("league_participants").update({
                        "division_id": division["id"],
                        "division_tier": tier_idx,
                    }).eq("season_id", season_id).in_("player_id", clubs).execute()

            try:
                await db.rpc("scale_season_ai_opponents", {"p_season_id": season_id}).execute()
            except Exception:
                logger.debug("scale_season_ai_opponents skipped", exc_info=True)

        parts_res = await db.table("league_participants").select(
            "player_id,participant_type,division_tier,players(is_ai)"
        ).eq("season_id", season_id).execute()
        all_parts = parts_res.data or []
        by_tier: dict[int, list] = {}
        for p in all_parts:
            by_tier.setdefault(int(p.get("division_tier") or 1), []).append(p)
        if 1 not in by_tier or len(by_tier[1]) != 8:
            raise ValueError(
                f"V1 prepare expected 8 clubs in tier 1, got {len(by_tier.get(1) or [])}"
            )

        now = datetime.now(timezone.utc)
        windows = assign_lifecycle_windows(
            first_matchday_local_date=now.astimezone(ZoneInfo(tz_name)).date() + timedelta(days=1),
            timezone_name=tz_name, resolution_hour_local=int(hour), season_open_utc=now,
        )
        await db.table("league_matchdays").upsert([
            {"season_id": season_id, "matchday_number": w.matchday_number,
             "window_start": w.window_start.isoformat(), "window_end": w.window_end.isoformat(),
             "status": "scheduled"}
            for w in windows
        ], on_conflict="season_id,matchday_number").execute()
        md_res = await db.table("league_matchdays").select("id,matchday_number,window_start,window_end").eq(
            "season_id", season_id
        ).execute()
        by_number = {int(row["matchday_number"]): row for row in (md_res.data or [])}

        existing_fx = await db.table("league_fixtures").select("id").eq(
            "season_id", season_id
        ).limit(1).execute()
        if not (existing_fx.data or []):
            rows = []
            for tier, participants in sorted(by_tier.items()):
                if len(participants) != 8:
                    raise ValueError(f"V1 prepare expected 8 clubs in tier {tier}, got {len(participants)}")
                fixtures = generate_round_robin_fixtures(
                    [str(p["player_id"]) for p in participants], double_round_robin=True
                )
                for f in fixtures:
                    rows.append({
                        "season_id": season_id,
                        "matchday": f.week,
                        "matchday_id": by_number[f.week]["id"],
                        "home_team_id": int(f.home_club_id),
                        "away_team_id": int(f.away_club_id),
                        "window_start": by_number[f.week]["window_start"],
                        "window_end": by_number[f.week]["window_end"],
                        "is_played": False,
                        "status": "scheduled",
                        "ruleset_version": V1_RULESET,
                    })
            if rows:
                await db.table("league_fixtures").insert(rows).execute()

        # Charge after participants exist (idempotent RPC).
        try:
            await db.rpc("charge_league_entry_fees", {"p_season_id": season_id}).execute()
        except Exception:
            logger.exception("charge_league_entry_fees failed season=%s", season_id)

        prep_end = (now + timedelta(hours=24)).isoformat()
        deadlines = dict(season.get("phase_deadlines") or {})
        deadlines["preparation_end"] = prep_end
        await db.table("league_seasons").update({
            "status": "preparing", "pacing_mode": "lifecycle_v1",
            "ruleset_version": V1_RULESET, "engine_version": "v1",
            "timezone": tz_name, "resolution_hour_local": int(hour),
            "total_matchdays": 14, "current_matchday": 1,
            "phase_deadlines": deadlines,
            "ruleset_snapshot": {"timezone": tz_name, "resolution_hour_local": int(hour)},
        }).eq("id", season_id).execute()

    return await _run_once(
        db, season_prepare(season_id), transition, season_id=season_id,
        transition="REGISTRATION_LOCKED_TO_PREPARING", trigger=trigger,
    )


async def activate_season(db: Any, season: dict, *, trigger: str = "deadline") -> bool:
    season_id = season["id"]

    async def transition() -> None:
        ready = await db.table("league_matchdays").select("id").eq("season_id", season_id).execute()
        if len(ready.data or []) != 14:
            raise ValueError("cannot activate season without complete matchday calendar")
        await db.table("league_seasons").update({
            "status": "active", "start_time": datetime.now(timezone.utc).isoformat(),
        }).eq("id", season_id).execute()
        await enqueue_outbox(
            db, event_type="schedule_released", payload={"season_id": season_id},
            dedupe_key=f"{season_id}:schedule_released",
        )

    return await _run_once(
        db, season_activate(season_id), transition, season_id=season_id,
        transition="PREPARING_TO_ACTIVE", trigger=trigger,
    )


async def _resolve_club_lineup_plan(db: Any, player_id: int, *, is_ai: bool):
    """Assistant priority: submitted (none in V1) → saved `/squad` → repair → emergency."""
    from leagues import LineupPlan, select_lineup_plan

    if is_ai:
        return LineupPlan(
            source="emergency",
            starter_ids=[f"ai-{i}" for i in range(11)],
            bench_ids=[],
            formation=None,
            legal=True,
        )

    from apps.discord_bot.core.squad_fetch import fetch_squad_xi

    formation, _, ordered = await fetch_squad_xi(db, int(player_id))
    saved = [str(c["id"]) for c in ordered if c.get("id")]
    pool_res = await (
        db.table("player_cards")
        .select("id")
        .eq("owner_id", int(player_id))
        .order("overall", desc=True)
        .execute()
    )
    pool = [str(c["id"]) for c in (pool_res.data or []) if c.get("id")]
    for sid in saved:
        if sid not in pool:
            pool.append(sid)
    # ponytail: no separate matchday-submit table in V1 — saved squad is the plan.
    return select_lineup_plan(
        submitted_starters=None,
        saved_starters=saved,
        eligible_pool=pool,
        formation=formation,
    )


async def _resolve_fixture(bot: Any, db: Any, fixture: dict, *, guild: Any | None) -> bool:
    """Deadline resolve: forfeit if illegal XI, else NSS sim with deterministic seed."""
    key = fixture_resolve(fixture["id"])

    async def transition() -> None:
        f_res = await (
            db.table("league_fixtures")
            .select(
                "*, home:players!league_fixtures_home_team_id_fkey(*), "
                "away:players!league_fixtures_away_team_id_fkey(*)"
            )
            .eq("id", fixture["id"])
            .maybe_single()
            .execute()
        )
        f = f_res.data if f_res else None
        if not f or f.get("is_played"):
            return

        home_p = f.get("home") or {}
        away_p = f.get("away") or {}
        home_plan = await _resolve_club_lineup_plan(
            db, int(f["home_team_id"]), is_ai=bool(home_p.get("is_ai"))
        )
        away_plan = await _resolve_club_lineup_plan(
            db, int(f["away_team_id"]), is_ai=bool(away_p.get("is_ai"))
        )
        home_legal = home_plan.legal
        away_legal = away_plan.legal

        seed_hex = hashlib.sha256(f"{f['season_id']}:{f['id']}:v1".encode()).hexdigest()
        sim_seed = int(seed_hex[:8], 16)

        if not home_legal and not away_legal:
            outcome = double_forfeit()
            await db.table("league_fixtures").update({
                "home_score": outcome.home_score,
                "away_score": outcome.away_score,
                "is_played": True,
                "status": "forfeit",
                "result_type": "double_forfeit",
                "resolved_by": "forfeit_engine",
                "match_seed": seed_hex,
                "engine_version": "v1",
                "ruleset_version": V1_RULESET,
                "played_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", f["id"]).execute()
            return

        if not home_legal or not away_legal:
            outcome = single_forfeit(illegal_is_home=not home_legal)
            await db.table("league_fixtures").update({
                "home_score": outcome.home_score,
                "away_score": outcome.away_score,
                "is_played": True,
                "status": "forfeit",
                "result_type": "forfeit",
                "resolved_by": "forfeit_engine",
                "match_seed": seed_hex,
                "engine_version": "v1",
                "ruleset_version": V1_RULESET,
                "played_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", f["id"]).execute()
            return

        await db.table("league_fixtures").update({
            "match_seed": seed_hex,
            "engine_version": "v1",
            "ruleset_version": V1_RULESET,
            "status": "running",
        }).eq("id", f["id"]).execute()

        if guild is None:
            await db.table("league_fixtures").update({"status": "failed_retryable"}).eq(
                "id", f["id"]
            ).execute()
            raise RuntimeError("guild unavailable for fixture sim — retryable")

        from apps.discord_bot.cogs.battle_cog import LeagueMatchHandler, run_league_match_simulation
        from apps.discord_bot.core.league_journal import resolve_season_threads
        from apps.discord_bot.core.match_runs import get_active_fixture_run

        if await get_active_fixture_run(db, f["id"]):
            raise RuntimeError("active match run — retry later")

        from apps.discord_bot.middleware.match_lock import acquire_match_lock, release_match_lock

        home_id = int(f["home_team_id"])
        away_id = int(f["away_team_id"])
        locks: list[int] = []
        for club_id, is_ai in (
            (home_id, bool(home_p.get("is_ai"))),
            (away_id, bool(away_p.get("is_ai"))),
        ):
            if is_ai:
                continue
            if not await acquire_match_lock(db, club_id, "league"):
                for held in locks:
                    await release_match_lock(db, held)
                raise RuntimeError("club match lock busy — retry later")
            locks.append(club_id)

        season_threads = await resolve_season_threads(bot, db, guild, f["season_id"])
        silent = False
        if not season_threads:
            class _SilentHandler:
                commentary_thread = None
                season_id = f["season_id"]
                journal_thread = None
                journal_standings_msg_id = None

                async def start_match(self, *a, **k):
                    return None

                async def update_ticker(self, *a, **k):
                    return None

                async def finalize_match(self, *a, **k):
                    return None

            handler: Any = _SilentHandler()
            silent = True
        else:
            handler = LeagueMatchHandler(
                commentary_thread=season_threads.commentary_thread,
                fixture_id=f["id"],
                season_id=f["season_id"],
                journal_thread=season_threads.journal_thread,
                journal_standings_msg_id=season_threads.journal_standings_message_id,
            )

        home_override = (
            None if home_p.get("is_ai") or home_plan.source in ("saved", "submitted")
            else list(home_plan.starter_ids)
        )
        away_override = (
            None if away_p.get("is_ai") or away_plan.source in ("saved", "submitted")
            else list(away_plan.starter_ids)
        )

        try:
            await run_league_match_simulation(
                bot=bot,
                db=db,
                guild=guild,
                fixture=f,
                active_player_id=None,
                handler=handler,
                sim_seed=sim_seed,
                silent=silent,
                skip_xi_gate=True,
                home_card_ids=home_override,
                away_card_ids=away_override,
            )
        except Exception:
            await db.table("league_fixtures").update({"status": "failed_retryable"}).eq(
                "id", f["id"]
            ).eq("is_played", False).execute()
            raise
        finally:
            for held in locks:
                try:
                    await release_match_lock(db, held)
                except Exception:
                    logger.debug("release_match_lock failed club=%s", held, exc_info=True)

        check = await db.table("league_fixtures").select("is_played").eq(
            "id", f["id"]
        ).maybe_single().execute()
        if not (check.data or {}).get("is_played"):
            await db.table("league_fixtures").update({"status": "failed_retryable"}).eq(
                "id", f["id"]
            ).execute()
            raise RuntimeError("sim did not settle fixture — retryable")

    return await _run_once(
        db, key, transition, season_id=fixture["season_id"],
        transition="FIXTURE_RESOLVED", trigger="deadline",
        metadata={"fixture_id": fixture["id"]},
        retryable=True,
    )


async def _process_matchdays(
    bot: Any,
    db: Any,
    season: dict,
    now: datetime,
    stats: dict[str, int],
    *,
    guild: Any | None,
) -> None:
    matchdays = await db.table("league_matchdays").select("*").eq(
        "season_id", season["id"]
    ).execute()
    for md in matchdays.data or []:
        start, end = _utc(md.get("window_start")), _utc(md.get("window_end"))
        if not start or not end:
            continue
        if md["status"] == "scheduled" and now >= start:
            async def open_md(md=md) -> None:
                await db.table("league_matchdays").update({"status": "open"}).eq(
                    "id", md["id"]
                ).execute()
                await db.table("league_fixtures").update({"status": "available"}).eq(
                    "matchday_id", md["id"]
                ).execute()
                await enqueue_outbox(
                    db,
                    event_type="matchday_open",
                    payload={"season_id": season["id"], "matchday": md["matchday_number"]},
                    dedupe_key=f"{season['id']}:md{md['matchday_number']}:open",
                )

            if await _run_once(
                db, matchday_open(md["id"]), open_md, season_id=season["id"],
                transition="MATCHDAY_OPENED", trigger="deadline",
            ):
                stats["transitions"] += 1
        if md["status"] in ("scheduled", "open", "closing_soon") and now >= end:
            async def lock_md(md=md) -> None:
                await db.table("league_matchdays").update({"status": "locked"}).eq(
                    "id", md["id"]
                ).execute()

            if await _run_once(
                db, matchday_lock(md["id"]), lock_md, season_id=season["id"],
                transition="MATCHDAY_LOCKED", trigger="deadline",
            ):
                stats["transitions"] += 1
            fixtures = await db.table("league_fixtures").select("*").eq(
                "matchday_id", md["id"]
            ).eq("is_played", False).execute()
            for fixture in fixtures.data or []:
                if await _resolve_fixture(bot, db, fixture, guild=guild):
                    stats["transitions"] += 1
        terminal = await db.table("league_fixtures").select("id").eq(
            "matchday_id", md["id"]
        ).eq("is_played", False).execute()
        if now >= end and not (terminal.data or []):
            async def complete_md(md=md) -> None:
                await db.table("league_matchdays").update({"status": "completed"}).eq(
                    "id", md["id"]
                ).execute()
                try:
                    await db.rpc(
                        "award_manager_of_the_matchday",
                        {
                            "p_season_id": season["id"],
                            "p_matchday": int(md["matchday_number"]),
                        },
                    ).execute()
                except Exception:
                    logger.debug(
                        "MoMD skip season=%s md=%s",
                        season["id"],
                        md["matchday_number"],
                        exc_info=True,
                    )
                await db.table("league_seasons").update({
                    "current_matchday": int(md["matchday_number"]) + 1,
                }).eq("id", season["id"]).execute()

            if await _run_once(
                db, matchday_complete(md["id"]), complete_md, season_id=season["id"],
                transition="MATCHDAY_COMPLETED", trigger="deadline",
            ):
                stats["transitions"] += 1


async def settle_season(db: Any, season: dict, *, trigger: str = "deadline") -> bool:
    """Write finals, pay prizes once, apply human-first promo, mark completed."""
    from leagues import (
        compute_human_first_promo_relegation,
        counts_for_promo_eligibility,
        season_promotion,
        season_rewards,
    )
    from leagues.standings import apply_fixture_to_row, sort_standings

    season_id = season["id"]

    async def transition() -> None:
        # Stay ``active`` until finals are written — never park in ``settling``
        # so a failed settle op can retry without orphaning the season.
        parts = await db.table("league_participants").select(
            "player_id,participant_type,division_tier,division_id,players(club_name,is_ai)"
        ).eq("season_id", season_id).execute()
        fixtures = await db.table("league_fixtures").select("*").eq(
            "season_id", season_id
        ).eq("is_played", True).execute()
        fx = fixtures.data or []

        by_tier: dict[int, list[dict]] = {}
        for p in parts.data or []:
            tier = int(p.get("division_tier") or 1)
            row = {
                "discord_id": int(p["player_id"]),
                "club_name": (p.get("players") or {}).get("club_name") or str(p["player_id"]),
                "is_ai": bool((p.get("players") or {}).get("is_ai"))
                    or (p.get("participant_type") == "bot"),
                "matches_played": 0, "won": 0, "drawn": 0, "lost": 0,
                "goals_for": 0, "goals_against": 0, "goal_difference": 0, "points": 0,
                "division_id": p.get("division_id"),
                "participant_type": p.get("participant_type") or (
                    "bot" if (p.get("players") or {}).get("is_ai") else "human"
                ),
            }
            for f in fx:
                if row["discord_id"] in (f["home_team_id"], f["away_team_id"]):
                    apply_fixture_to_row(row, f, row["discord_id"])
            by_tier.setdefault(tier, []).append(row)

        league_res = await db.table("leagues").select("guild_id").eq(
            "id", season["league_id"]
        ).maybe_single().execute()
        guild_id = (league_res.data or {}).get("guild_id")

        for tier, rows in by_tier.items():
            ordered = sort_standings(rows, fx)
            human_sorted = [r["discord_id"] for r in ordered if not r.get("is_ai")]
            eligible: list[int] = []
            for hid in human_sorted:
                eligible_count = sum(
                    1 for f in fx
                    if hid in (f["home_team_id"], f["away_team_id"])
                    and counts_for_promo_eligibility(f.get("result_type"))
                )
                if eligible_count >= 7:
                    eligible.append(hid)
            promo = compute_human_first_promo_relegation(
                human_sorted, spots=2, eligible_ids=eligible
            )
            finals = []
            for pos, r in enumerate(ordered, start=1):
                movement = "stayed"
                pid = r["discord_id"]
                if pid == promo.champion_id:
                    movement = "champion"
                elif pid in promo.promoted_ids:
                    movement = "promoted"
                elif pid in promo.relegated_ids:
                    movement = "relegated"
                elif r.get("is_ai"):
                    movement = "none"
                finals.append({
                    "season_id": season_id,
                    "division_id": r.get("division_id"),
                    "player_id": pid,
                    "position": pos,
                    "played": r["matches_played"],
                    "won": r["won"],
                    "drawn": r["drawn"],
                    "lost": r["lost"],
                    "gf": r["goals_for"],
                    "ga": r["goals_against"],
                    "gd": r["goal_difference"],
                    "points": r["points"],
                    "movement": movement,
                    "participant_type": r["participant_type"],
                })
            if finals:
                await db.table("league_final_standings").upsert(
                    finals, on_conflict="season_id,player_id"
                ).execute()

            promo_key = season_promotion(f"{season_id}:t{tier}")
            if guild_id and await acquire_operation(db, promo_key):
                try:
                    for pid in promo.promoted_ids:
                        cur = await db.table("league_members").select(
                            "seasonal_division_tier"
                        ).eq("guild_id", guild_id).eq("player_id", pid).maybe_single().execute()
                        tier_now = int((cur.data or {}).get("seasonal_division_tier") or tier)
                        await db.table("league_members").update({
                            "seasonal_division_tier": max(1, tier_now - 1),
                        }).eq("guild_id", guild_id).eq("player_id", pid).execute()
                    for pid in promo.relegated_ids:
                        cur = await db.table("league_members").select(
                            "seasonal_division_tier"
                        ).eq("guild_id", guild_id).eq("player_id", pid).maybe_single().execute()
                        tier_now = int((cur.data or {}).get("seasonal_division_tier") or tier)
                        await db.table("league_members").update({
                            "seasonal_division_tier": tier_now + 1,
                        }).eq("guild_id", guild_id).eq("player_id", pid).execute()
                    await complete_operation(db, promo_key, ok=True)
                    await enqueue_outbox(
                        db,
                        event_type="promotion_relegation",
                        payload={
                            "season_id": season_id,
                            "tier": tier,
                            "promoted": promo.promoted_ids,
                            "relegated": promo.relegated_ids,
                            "champion": promo.champion_id,
                        },
                        dedupe_key=f"{season_id}:promo:t{tier}",
                    )
                except Exception as exc:
                    await complete_operation(db, promo_key, ok=False, error=str(exc)[:500])

        if await acquire_operation(db, season_rewards(season_id)):
            try:
                await db.rpc("distribute_season_prizes", {"p_season_id": season_id}).execute()
                await complete_operation(db, season_rewards(season_id), ok=True)
            except Exception as exc:
                await complete_operation(db, season_rewards(season_id), ok=False, error=str(exc)[:500])
                raise

        deadlines = dict(season.get("phase_deadlines") or {})
        deadlines["offseason_end"] = (datetime.now(timezone.utc) + timedelta(hours=72)).isoformat()
        await db.table("league_seasons").update({
            "status": "completed",
            "phase_deadlines": deadlines,
        }).eq("id", season_id).execute()
        await enqueue_outbox(
            db, event_type="season_completed", payload={"season_id": season_id},
            dedupe_key=f"{season_id}:completed",
        )

    return await _run_once(
        db, season_settle(season_id), transition, season_id=season_id,
        transition="ACTIVE_TO_COMPLETED", trigger=trigger,
        retryable=True,
    )


async def force_cancel_season(db: Any, season: dict, *, trigger: str = "admin") -> bool:
    """Admin force-end → cancelled (not natural completed); no prizes/promo."""
    season_id = season["id"]
    key = f"season:{season_id}:force_cancel"

    async def transition() -> None:
        await db.table("league_seasons").update({"status": "cancelled"}).eq("id", season_id).execute()
        await enqueue_outbox(
            db, event_type="season_cancelled", payload={"season_id": season_id},
            dedupe_key=f"{season_id}:cancelled",
        )

    return await _run_once(
        db, key, transition, season_id=season_id,
        transition="FORCE_CANCEL", trigger=trigger,
    )


async def pause_season(db: Any, season_id: str) -> None:
    await db.table("league_seasons").update({
        "status": "paused", "pause_started_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", season_id).eq("status", "active").execute()


async def resume_season(db: Any, season: dict) -> bool:
    paused_at = _utc(season.get("pause_started_at"))
    if not paused_at:
        return False
    delta = int((datetime.now(timezone.utc) - paused_at).total_seconds())
    if delta <= 0:
        return False
    from leagues.schedule import MatchdayUtcWindow

    matchdays = await db.table("league_matchdays").select("*").eq("season_id", season["id"]).in_(
        "status", ["scheduled", "open", "closing_soon", "locked", "resolution_failed"]
    ).execute()
    updates = []
    for row in matchdays.data or []:
        ws, we = _utc(row["window_start"]), _utc(row["window_end"])
        if not ws or not we:
            continue
        windows = rebase_windows([
            MatchdayUtcWindow(
                matchday_number=int(row["matchday_number"]),
                window_start=ws,
                window_end=we,
            )
        ], delta)
        w = windows[0]
        updates.append({"id": row["id"], "window_start": w.window_start.isoformat(), "window_end": w.window_end.isoformat()})
    if updates:
        await db.table("league_matchdays").upsert(updates, on_conflict="id").execute()
        for row in updates:
            await db.table("league_fixtures").update({
                "window_start": row["window_start"], "window_end": row["window_end"],
            }).eq("matchday_id", row["id"]).eq("is_played", False).execute()
    await db.table("league_seasons").update({
        "status": "active", "pause_started_at": None,
        "total_paused_seconds": int(season.get("total_paused_seconds") or 0) + delta,
    }).eq("id", season["id"]).execute()
    return True


async def process_due_transitions(bot: Any, db: Any, now: datetime | None = None) -> dict[str, int]:
    """
    Evaluate durable V1 league state and execute due transitions.
    Grandfather Dynamics/legacy seasons are skipped here (handled by existing tick paths).
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    stats = {"seasons_scanned": 0, "transitions": 0, "skipped": 0}
    try:
        res = await (
            db.table("league_seasons")
            .select("*")
            .eq("pacing_mode", "lifecycle_v1")
            .execute()
        )
    except Exception:
        logger.exception("process_due_transitions: failed to list V1 seasons")
        return stats

    rows = res.data or []
    stats["seasons_scanned"] = len(rows)
    for season in rows:
        status = season.get("status")
        if status == "cancelled":
            stats["skipped"] += 1
            continue
        if status == "completed":
            off_end = _utc((season.get("phase_deadlines") or {}).get("offseason_end"))
            if not off_end or now < off_end:
                stats["skipped"] += 1
                continue
            from leagues import season_next_registration

            key = season_next_registration(season["id"])

            async def open_next(s=season) -> None:
                league_res = await db.table("leagues").select("guild_id").eq(
                    "id", s["league_id"]
                ).maybe_single().execute()
                gid = (league_res.data or {}).get("guild_id")
                if not gid:
                    return
                result = await open_registration_season(
                    db,
                    league_id=s["league_id"],
                    guild_id=int(gid),
                    trigger="offseason",
                )
                # Living season = already opened (or Dynamics grandfather) — treat as done
                if not result.get("ok"):
                    logger.info(
                        "offseason next-registration skipped season=%s: %s",
                        s["id"],
                        result.get("error"),
                    )

            if await _run_once(
                db, key, open_next, season_id=season["id"],
                transition="OFFSEASON_TO_REGISTRATION", trigger="deadline",
            ):
                stats["transitions"] += 1
            else:
                stats["skipped"] += 1
            continue
        deadlines = season.get("phase_deadlines") or {}
        registration_end = _utc(deadlines.get("registration_end"))
        preparation_end = _utc(deadlines.get("preparation_end"))
        if status == "registration_open" and registration_end and now >= registration_end:
            if await lock_registration(db, season):
                stats["transitions"] += 1
        elif status == "registration_locked":
            regs = await db.table("league_registrations").select("player_id,players(is_ai)").eq(
                "season_id", season["id"]
            ).eq("status", "locked").execute()
            humans = [r for r in (regs.data or []) if not (r.get("players") or {}).get("is_ai")]
            if len(humans) < 4:
                if await cancel_under_min(db, season):
                    stats["transitions"] += 1
            elif await prepare_season(bot, db, season):
                stats["transitions"] += 1
        elif status == "preparing" and (not preparation_end or now >= preparation_end):
            if await activate_season(db, season):
                stats["transitions"] += 1
        elif status == "active":
            guild = None
            try:
                league_res = await db.table("leagues").select("guild_id").eq(
                    "id", season["league_id"]
                ).maybe_single().execute()
                gid = (league_res.data or {}).get("guild_id")
                if gid and bot is not None:
                    guild = bot.get_guild(int(gid))
                    if guild is None:
                        try:
                            guild = await bot.fetch_guild(int(gid))
                        except Exception:
                            guild = None
            except Exception:
                logger.debug("guild resolve failed for season %s", season.get("id"), exc_info=True)
            await _process_matchdays(bot, db, season, now, stats, guild=guild)
            md_left = await db.table("league_matchdays").select("id").eq(
                "season_id", season["id"]
            ).neq("status", "completed").execute()
            if not (md_left.data or []):
                if await settle_season(db, season):
                    stats["transitions"] += 1
    return stats
