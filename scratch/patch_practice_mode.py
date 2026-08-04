"""One-shot patch: practice mode in execute_bot_battle."""
from __future__ import annotations

from pathlib import Path

p = Path(__file__).resolve().parents[1] / "apps" / "discord_bot" / "cogs" / "battle_cog.py"
text = p.read_text(encoding="utf-8")

needle = 'if not await acquire_match_lock(db, interaction.user.id, "bot"):'
if needle not in text:
    raise SystemExit("acquire_match_lock bot needle missing")

insert = '''practice_mode = False
        try:
            db = await get_client()

            try:
                from apps.discord_bot.core.economy_rpc import get_game_config_int

                # battle_pvp_enabled stored as JSON boolean; int helper treats true as missing → use rpc/hub
                hub = await db.rpc(
                    "get_battle_hub_state",
                    {"p_owner_id": interaction.user.id, "p_guild_id": interaction.guild_id or 0},
                ).execute()
                practice_mode = bool((hub.data or {}).get("battle_pvp_enabled")) if isinstance(hub.data, dict) else False
            except Exception:
                practice_mode = False

            lock_type = "practice" if practice_mode else "bot"
            if not await acquire_match_lock(db, interaction.user.id, lock_type):'''

# Only replace the first bot-battle acquire (execute_bot_battle), not other acquires
idx = text.find("async def execute_bot_battle")
if idx < 0:
    raise SystemExit("execute_bot_battle missing")
part = text[idx:]
# find try/db/acquire sequence
old = '''        state = None
        try:
            db = await get_client()

            if not await acquire_match_lock(db, interaction.user.id, "bot"):'''
if old not in part:
    raise SystemExit("old block missing in execute_bot_battle")
part2 = part.replace(old, '''        state = None
        practice_mode = False
        try:
            db = await get_client()

            try:
                hub = await db.rpc(
                    "get_battle_hub_state",
                    {"p_owner_id": interaction.user.id, "p_guild_id": interaction.guild_id or 0},
                ).execute()
                practice_mode = bool((hub.data or {}).get("battle_pvp_enabled")) if isinstance(hub.data, dict) else False
            except Exception:
                practice_mode = False

            lock_type = "practice" if practice_mode else "bot"
            if not await acquire_match_lock(db, interaction.user.id, lock_type):''', 1)

old_energy = '''            needed = await get_match_energy_cost(db, "bot", v2=v2)
            if curr_energy < needed:
                await interaction.followup.send(
                    embed=error_embed(
                        f"Insufficient energy. Bot matches require **{needed}** ⚡ (you have **{curr_energy}**)."
                    ),
                    ephemeral=True,
                )
                return'''
new_energy = '''            energy_key = "practice" if practice_mode else "bot"
            needed = await get_match_energy_cost(db, energy_key, v2=v2)
            if curr_energy < needed:
                label = "AI Practice" if practice_mode else "Bot"
                await interaction.followup.send(
                    embed=error_embed(
                        f"Insufficient energy. {label} matches require **{needed}** ⚡ (you have **{curr_energy}**)."
                    ),
                    ephemeral=True,
                )
                return'''
if old_energy not in part2:
    raise SystemExit("energy block missing")
part2 = part2.replace(old_energy, new_energy, 1)

old_run = 'run_type="bot",\n                active_discord_id=interaction.user.id,'
new_run = 'run_type="practice" if practice_mode else "bot",\n                active_discord_id=interaction.user.id,'
if old_run not in part2:
    raise SystemExit("run_type block missing")
part2 = part2.replace(old_run, new_run, 1)

# Rewards branch
old_rewards = '''            coins_earned, fitness_summary = await apply_bot_match_rewards(
                db,
                player_id=interaction.user.id,
                player_row=player,
                result_str=res_str,
                cards=active_cards,
                club_name=player["club_name"],
                team_rating=my_rating,
                opponent_rating=opp_rating,
                goals_for=state.home_score,
                goals_against=state.away_score,
                points_earned=points_earned,
                lp_change=lp_delta,
                division_win_coins=win_coins,
                run_id=bot_run_id,
                motm_name=motm,
                key_events=key_events_list,
                bench_ids=await fetch_bench_ids(
                    db, interaction.user.id, [str(c["id"]) for c in active_cards]
                ),
                tactics_modifier=float(getattr(state, "home_tactics_modifier", 1.0) or 1.0),
                bot=self.bot,
                recorded_injuries=recorded_for_side(state.recorded_injuries, "home"),
            )
            rewards_applied = True

            # Durable settle before Discord present (US-42.4)
            if bot_run_id:
                await complete_run(db, bot_run_id, home_score=state.home_score, away_score=state.away_score)
                settled = True'''

new_rewards = '''            if practice_mode and bot_run_id:
                is_new = int(player.get("matches_played") or 0) < 10
                prac = await db.rpc(
                    "finalize_ai_practice_match",
                    {
                        "p_run_id": bot_run_id,
                        "p_owner_id": interaction.user.id,
                        "p_result": res_str,
                        "p_home_score": state.home_score,
                        "p_away_score": state.away_score,
                        "p_my_rating": my_rating,
                        "p_opp_rating": opp_rating,
                        "p_is_new_manager": is_new,
                    },
                ).execute()
                prac_data = prac.data if isinstance(prac.data, dict) else {}
                coins_earned = int(prac_data.get("coins") or 0)
                fitness_summary = {"ok": True, "xp_line": None, "line": None}
                points_earned = 0
                lp_delta = 0
                actual_lp_change = 0
                new_lp = user_lp
                rewards_applied = True
                settled = True
                lock_acquired = False  # finalize released lock
            else:
                coins_earned, fitness_summary = await apply_bot_match_rewards(
                    db,
                    player_id=interaction.user.id,
                    player_row=player,
                    result_str=res_str,
                    cards=active_cards,
                    club_name=player["club_name"],
                    team_rating=my_rating,
                    opponent_rating=opp_rating,
                    goals_for=state.home_score,
                    goals_against=state.away_score,
                    points_earned=points_earned,
                    lp_change=lp_delta,
                    division_win_coins=win_coins,
                    run_id=bot_run_id,
                    motm_name=motm,
                    key_events=key_events_list,
                    bench_ids=await fetch_bench_ids(
                        db, interaction.user.id, [str(c["id"]) for c in active_cards]
                    ),
                    tactics_modifier=float(getattr(state, "home_tactics_modifier", 1.0) or 1.0),
                    bot=self.bot,
                    recorded_injuries=recorded_for_side(state.recorded_injuries, "home"),
                )
                rewards_applied = True

                # Durable settle before Discord present (US-42.4)
                if bot_run_id:
                    await complete_run(db, bot_run_id, home_score=state.home_score, away_score=state.away_score)
                    settled = True'''

if old_rewards not in part2:
    raise SystemExit("rewards block missing")
part2 = part2.replace(old_rewards, new_rewards, 1)

text = text[:idx] + part2
p.write_text(text, encoding="utf-8")
print("patched execute_bot_battle practice mode")
