# packages/economy/economy/flows.py
"""Pure economy flow formulas — mirrors game_config defaults (US-25)."""
from __future__ import annotations

from dataclasses import dataclass

# Defaults mirror 028_economy_foundation.sql seed rows
DEFAULTS: dict[str, float | int | list[int]] = {
    "match_bot_win": 200,
    "match_bot_draw": 100,
    "match_bot_loss": 50,
    "match_friendly_win": 150,
    "match_league_win_min": 250,
    "match_league_win_max": 400,
    "league_entry_fee_coins": 1500,
    "league_entry_fee_per_division": 250,
    "league_auto_sim_coin_mult": 0.5,
    "league_join_min_matches": 10,
    "league_join_min_account_days": 7,
    "daily_login_base": 100,
    "daily_login_streak_bonus": 10,
    "daily_login_streak_cap": 50,
    "drill_basic_flat": 100,
    "drill_basic_ovr_mult": 2,
    "drill_basic_energy": 10,
    "drill_advanced_min_level": 10,
    "drill_advanced_flat": 300,
    "drill_advanced_ovr_mult": 3,
    "drill_advanced_energy": 15,
    "fusion_coins": 200,
    "energy_refill_costs": [200, 400, 600],
    "match_energy_bot": 20,
    "match_energy_friendly": 15,
    "match_energy_league": 10,
    # 062 P2P transfer market defaults
    "transfer_tax_bps": 1000,
    "transfer_price_floor_mult": 0.75,
    "transfer_price_ceil_mult": 2.5,
    "transfer_listing_slot_cap": 5,
    "transfer_listing_ttl_hours": 72,
    "transfer_relist_cooldown_hours": 6,
}

DIVISION_TIERS = {
    "Grassroots": 0,
    "Amateur": 1,
    "Semi-Pro": 2,
    "Professional": 3,
    "Elite": 4,
    "Legendary": 5,
}


@dataclass(frozen=True)
class EconomyConfig:
    """In-memory config; DB game_config overrides at runtime in RPCs."""

    match_bot_win: int = 200
    match_bot_draw: int = 100
    match_bot_loss: int = 50
    match_friendly_win: int = 150
    match_league_win_min: int = 250
    match_league_win_max: int = 400
    league_entry_fee_coins: int = 1500
    league_entry_fee_per_division: int = 250
    league_auto_sim_coin_mult: float = 0.5
    league_join_min_matches: int = 10
    league_join_min_account_days: int = 7
    daily_login_base: int = 100
    daily_login_streak_bonus: int = 10
    daily_login_streak_cap: int = 50
    drill_basic_flat: int = 100
    drill_basic_ovr_mult: int = 2
    drill_basic_energy: int = 10
    drill_advanced_min_level: int = 10
    drill_advanced_flat: int = 300
    drill_advanced_ovr_mult: int = 3
    drill_advanced_energy: int = 15
    fusion_coins: int = 200
    energy_refill_costs: tuple[int, ...] = (200, 400, 600)
    match_energy_bot: int = 20
    match_energy_friendly: int = 15
    match_energy_league: int = 10
    transfer_tax_bps: int = 1000
    transfer_price_floor_mult: float = 0.75
    transfer_price_ceil_mult: float = 2.5
    transfer_listing_slot_cap: int = 5
    transfer_listing_ttl_hours: int = 72
    transfer_relist_cooldown_hours: int = 6


def league_division_tier(division: str) -> int:
    return DIVISION_TIERS.get(division or "Grassroots", 0)


def bot_match_coins(result: str, division_win_coins: int, cfg: EconomyConfig | None = None) -> int:
    """Win coins scaled by global_divisions.win_coins / 100."""
    c = cfg or EconomyConfig()
    mult = max(division_win_coins, 100) / 100.0
    if result == "win":
        return int(c.match_bot_win * mult)
    if result == "draw":
        return c.match_bot_draw
    return c.match_bot_loss


def league_match_coins(division: str, cfg: EconomyConfig | None = None) -> int:
    c = cfg or EconomyConfig()
    tier = league_division_tier(division)
    return c.match_league_win_min + (c.match_league_win_max - c.match_league_win_min) * tier // 5


def league_entry_fee(division: str, cfg: EconomyConfig | None = None) -> int:
    c = cfg or EconomyConfig()
    tier = league_division_tier(division)
    return c.league_entry_fee_coins + tier * c.league_entry_fee_per_division


def league_match_coins_for_result(
    result: str,
    division: str,
    *,
    auto_sim: bool = False,
    cfg: EconomyConfig | None = None,
) -> int:
    """Per-match league coins; auto-sim applies league_auto_sim_coin_mult (US-27)."""
    c = cfg or EconomyConfig()
    win_c = league_match_coins(division, c)
    if result == "win":
        base = win_c
    elif result == "draw":
        base = win_c // 3
    else:
        base = 0
    if auto_sim and base > 0:
        return int(base * c.league_auto_sim_coin_mult)
    return base


def friendly_match_coins(result: str, cfg: EconomyConfig | None = None) -> int:
    c = cfg or EconomyConfig()
    return c.match_friendly_win if result == "win" else 0


def drill_cost(ovr: int, player_level: int, cfg: EconomyConfig | None = None) -> tuple[int, int]:
    """Returns (coin_cost, energy_cost)."""
    c = cfg or EconomyConfig()
    if player_level >= c.drill_advanced_min_level:
        return c.drill_advanced_flat + c.drill_advanced_ovr_mult * ovr, c.drill_advanced_energy
    return c.drill_basic_flat + c.drill_basic_ovr_mult * ovr, c.drill_basic_energy


def evolution_start_cost(ovr: int, flat: int = 500, ovr_mult: int = 5, energy: int = 25) -> tuple[int, int]:
    return flat + ovr_mult * ovr, energy


def daily_login_reward(streak: int, cfg: EconomyConfig | None = None) -> int:
    c = cfg or EconomyConfig()
    bonus = min(c.daily_login_streak_cap, max(0, streak - 1) * c.daily_login_streak_bonus)
    return c.daily_login_base + bonus


def energy_refill_cost(refill_number: int, cfg: EconomyConfig | None = None) -> int:
    c = cfg or EconomyConfig()
    idx = min(max(refill_number, 1), len(c.energy_refill_costs)) - 1
    return c.energy_refill_costs[idx]


@dataclass
class DayBudget:
    income: int
    expenses: int

    @property
    def net(self) -> int:
        return self.income - self.expenses


def simulate_casual_day(ovr: int = 60, player_level: int = 5, wins: int = 5, drills: int = 5) -> DayBudget:
    """Casual archetype: bot wins + drills + daily login."""
    c = EconomyConfig()
    div_win = 100  # Bronze III baseline
    income = wins * bot_match_coins("win", div_win, c) + daily_login_reward(1, c)
    coin_per_drill, _ = drill_cost(ovr, player_level, c)
    expenses = drills * coin_per_drill
    return DayBudget(income=income, expenses=expenses)


def simulate_hardcore_day(
    ovr: int = 70,
    player_level: int = 12,
    wins: int = 10,
    drills: int = 10,
    fusions: int = 3,
    refills: int = 3,
) -> DayBudget:
    c = EconomyConfig()
    income = wins * bot_match_coins("win", 200, c) + daily_login_reward(3, c)
    coin_per_drill, _ = drill_cost(ovr, player_level, c)
    expenses = (
        drills * coin_per_drill
        + fusions * c.fusion_coins
        + sum(energy_refill_cost(i, c) for i in range(1, refills + 1))
    )
    return DayBudget(income=income, expenses=expenses)


def simulate_days(archetype: str, days: int = 30) -> list[int]:
    """Return cumulative net coin balance over days."""
    balance = 0
    series: list[int] = []
    for _ in range(days):
        if archetype == "casual":
            b = simulate_casual_day()
        elif archetype == "hardcore":
            b = simulate_hardcore_day()
        elif archetype == "gacha_farmer":
            b = DayBudget(income=1500, expenses=0)  # ponytail: agent sales estimate
        else:
            b = simulate_casual_day()
        balance += b.net
        series.append(balance)
    return series
