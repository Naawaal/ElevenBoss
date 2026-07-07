# packages/leagues/leagues/prizes.py
"""Season prize pool distribution (US-26)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SeasonPrize:
    finish_position: int
    player_id: int
    coins: int
    award_type: str  # champion, runner_up, third, participation, golden_boot


FINISH_SHARES = {1: 0.60, 2: 0.25, 3: 0.10}
GOLDEN_BOOT_BONUS_PCT = 0.05


def distribute_finish_prizes(
    standings: list[dict],
    pool_base: int,
    participation_coins: int,
) -> list[SeasonPrize]:
    """Split pool among finishers; everyone else gets participation."""
    prizes: list[SeasonPrize] = []
    for idx, row in enumerate(standings, 1):
        pid = row["discord_id"]
        if row.get("is_ai"):
            continue
        if idx in FINISH_SHARES:
            coins = int(pool_base * FINISH_SHARES[idx])
            award = {1: "champion", 2: "runner_up", 3: "third"}[idx]
            prizes.append(SeasonPrize(idx, pid, coins, award))
        else:
            prizes.append(SeasonPrize(idx, pid, participation_coins, "participation"))
    return prizes


def golden_boot_bonus(pool_base: int) -> int:
    return max(50, int(pool_base * GOLDEN_BOOT_BONUS_PCT))
