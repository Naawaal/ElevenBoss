#!/usr/bin/env python3
"""League economy calibration — uses coded formulas only (no DB). US-27."""
from __future__ import annotations

from dataclasses import dataclass

from economy.flows import (
    EconomyConfig,
    league_entry_fee,
    league_match_coins_for_result,
    simulate_casual_day,
    simulate_hardcore_day,
)

POOL_BASE = 3500
PARTICIPATION = 150
MILESTONE_BONUS = 100
MATCHES_PER_SEASON = 14
SEASON_DAYS = 28
LEAGUE_ENERGY_MANUAL = 10
ENTRY_FEE_GRASSROOTS = 1500


@dataclass(frozen=True)
class SeasonScenario:
    label: str
    wins: int
    draws: int
    losses: int
    finish_pos: int


def season_prize(position: int, pool: int = POOL_BASE, participation: int = PARTICIPATION) -> int:
    if position == 1:
        return pool * 60 // 100
    if position == 2:
        return pool * 25 // 100
    if position == 3:
        return pool * 10 // 100
    return participation


def league_season_coins(
    scenario: SeasonScenario,
    *,
    division: str = "Grassroots",
    milestones_hit: int = 3,
    manual_plays: int = MATCHES_PER_SEASON,
    auto_sim_plays: int = 0,
    entry_fee: int = ENTRY_FEE_GRASSROOTS,
    refund_entry: bool = True,
) -> dict[str, int]:
    cfg = EconomyConfig()
    match_income = 0
    for _ in range(scenario.wins):
        match_income += league_match_coins_for_result("win", division, auto_sim=False, cfg=cfg)
    for _ in range(scenario.draws):
        match_income += league_match_coins_for_result("draw", division, auto_sim=False, cfg=cfg)
    for _ in range(auto_sim_plays):
        match_income += league_match_coins_for_result("win", division, auto_sim=True, cfg=cfg)

    prize = season_prize(scenario.finish_pos)
    milestones = milestones_hit * MILESTONE_BONUS
    gross = match_income + prize + milestones
    fee_net = 0 if refund_entry else -entry_fee
    return {
        "match_income": match_income,
        "season_prize": prize,
        "milestones": milestones,
        "entry_fee": -entry_fee,
        "total_league": gross + fee_net,
        "energy_spent": manual_plays * LEAGUE_ENERGY_MANUAL,
    }


def main() -> None:
    cfg = EconomyConfig()
    scenarios = [
        SeasonScenario("champion", 12, 1, 1, 1),
        SeasonScenario("mid_table", 7, 4, 3, 3),
        SeasonScenario("relegation", 3, 3, 8, 8),
    ]
    casual = simulate_casual_day()
    hardcore = simulate_hardcore_day()

    print("=== US-27 CALIBRATED LEAGUE REWARD TABLE ===")
    print(f"Season pool base: {POOL_BASE}")
    for pos in range(1, 9):
        print(f"  {pos}: {season_prize(pos)} coins")
    print(f"Milestone: 6+ pts/matchday -> {MILESTONE_BONUS} coins")
    print(f"Match win (Grassroots): {league_match_coins_for_result('win', 'Grassroots', cfg=cfg)}")
    print(f"Auto-sim win (Grassroots): {league_match_coins_for_result('win', 'Grassroots', auto_sim=True, cfg=cfg)}")
    print(f"Entry fee (Grassroots): {league_entry_fee('Grassroots', cfg)} (refunded on complete)")
    print()

    print("=== 4-WEEK SEASON (manual play, fee refunded) ===")
    for s in scenarios:
        r = league_season_coins(s)
        print(
            f"{s.label:12} match={r['match_income']} prize={r['season_prize']} "
            f"milestones={r['milestones']} total={r['total_league']} energy={r['energy_spent']}"
        )

    champ = league_season_coins(SeasonScenario("champion", 12, 1, 1, 1))
    print(f"\nChampion gross injection: {champ['total_league']} (pre-US-27 was ~7150)")

    auto = league_season_coins(
        SeasonScenario("champion", 10, 1, 1, 1),
        auto_sim_plays=2,
    )
    print(f"Champion (2 auto-sim wins): total={auto['total_league']}")

    print(f"\n=== 28-DAY BASELINE ===")
    print(f"Casual 28d: {casual.net * SEASON_DAYS}")
    print(f"Hardcore 28d: {hardcore.net * SEASON_DAYS}")


if __name__ == "__main__":
    main()
