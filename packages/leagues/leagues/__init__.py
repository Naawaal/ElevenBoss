# packages/leagues/leagues/__init__.py
from __future__ import annotations

from .models import LeagueEntry, PromotionResult
from .calculator import compute_promotions_relegations
from .standings import compute_form, format_standings_table, sort_standings, tie_breaker_footer
from .prizes import SeasonPrize, distribute_finish_prizes, golden_boot_bonus
from .familiarity import familiarity_multiplier, count_same_xi_streak, xi_streak_including_current
from .match_points import (
    FOOTBALL_PTS,
    GLOBAL_LP_DELTA,
    clamp_global_lp,
    division_rank_points,
    global_lp_delta,
    season_fixture_points,
)
from .weekly_tiers import (
    DEFAULT_THRESHOLDS,
    TIER_BRONZE,
    TIER_GOLD,
    TIER_ORDER,
    TIER_SILVER,
    highest_unclaimed_tier,
    iso_week_utc,
    tier_progress_label,
    tiers_reached,
    weekly_tier_coin_reward,
)
from .leaderboard_format import (
    format_rank_line,
    paginate_rows,
    promotion_zone_labels,
    viewer_page_index,
    weekly_reset_countdown,
    zone_suffix,
)
from .dynamics_windows import MatchdayWindow, assign_dynamics_windows, utc_day_floor
from .seasonal_divisions import (
    FixedPromoResult,
    compute_fixed_promo_relegation,
    seat_humans_into_divisions,
)
from .momd import MomdWinner, select_momd_winner
from .automation import (
    automation_effective,
    can_open_auto_registration,
    evaluate_registration_close,
    next_monday_0005_utc,
    registration_closes_at,
)

__all__ = [
    "LeagueEntry",
    "PromotionResult",
    "compute_promotions_relegations",
    "compute_form",
    "format_standings_table",
    "sort_standings",
    "tie_breaker_footer",
    "SeasonPrize",
    "distribute_finish_prizes",
    "golden_boot_bonus",
    "familiarity_multiplier",
    "count_same_xi_streak",
    "xi_streak_including_current",
    "FOOTBALL_PTS",
    "GLOBAL_LP_DELTA",
    "clamp_global_lp",
    "division_rank_points",
    "global_lp_delta",
    "season_fixture_points",
    "DEFAULT_THRESHOLDS",
    "TIER_BRONZE",
    "TIER_SILVER",
    "TIER_GOLD",
    "TIER_ORDER",
    "highest_unclaimed_tier",
    "iso_week_utc",
    "tier_progress_label",
    "tiers_reached",
    "weekly_tier_coin_reward",
    "format_rank_line",
    "paginate_rows",
    "promotion_zone_labels",
    "viewer_page_index",
    "weekly_reset_countdown",
    "zone_suffix",
    "MatchdayWindow",
    "assign_dynamics_windows",
    "utc_day_floor",
    "FixedPromoResult",
    "compute_fixed_promo_relegation",
    "seat_humans_into_divisions",
    "MomdWinner",
    "select_momd_winner",
    "automation_effective",
    "can_open_auto_registration",
    "evaluate_registration_close",
    "next_monday_0005_utc",
    "registration_closes_at",
]
