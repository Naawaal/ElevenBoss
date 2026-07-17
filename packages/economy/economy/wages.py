"""Weekly wage bill + payroll strike / contract grace helpers (019)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

DEFAULT_WAGE_SCALE = 1.2
DEFAULT_BILL_SCALE = 1.0
DEFAULT_FRIENDLY_STRIKE_BLOCK = 2
DEFAULT_MARKET_STRIKE_BLOCK = 3
DEFAULT_CONTRACT_GRACE_DAYS = 7

RARITY_WAGE_MULT: dict[str, float] = {
    "Common": 1.0,
    "Rare": 1.05,
    "Epic": 1.10,
    "Legendary": 1.15,
}


def card_weekly_wage(
    card: dict[str, Any],
    *,
    wage_scale_factor: float = DEFAULT_WAGE_SCALE,
    rarity_mults: dict[str, float] | None = None,
    age_mult: float = 1.0,
    pot_mult: float = 1.0,
) -> int:
    """Derive weekly wage for one card. Formula: (max(ovr,40)-40)^2 * scale + 10, then mults."""
    ovr = int(card.get("overall", card.get("base_rating", 50)) or 50)
    calc_ovr = max(40, ovr)
    base = (calc_ovr - 40) ** 2 * float(wage_scale_factor) + 10
    rarity = str(card.get("rarity") or "Common")
    mults = rarity_mults if rarity_mults is not None else RARITY_WAGE_MULT
    rarity_m = float(mults.get(rarity, 1.0))
    return int(base * rarity_m * float(age_mult) * float(pot_mult))


def calculate_xi_weekly_bill(
    squad: list[dict[str, Any]],
    *,
    wage_scale_factor: float = DEFAULT_WAGE_SCALE,
    bill_scale: float = DEFAULT_BILL_SCALE,
    rarity_mults: dict[str, float] | None = None,
    age_mult: float = 1.0,
    pot_mult: float = 1.0,
) -> int:
    """Sum derived wages for Starting XI cards, then apply bill_scale."""
    total = sum(
        card_weekly_wage(
            c,
            wage_scale_factor=wage_scale_factor,
            rarity_mults=rarity_mults,
            age_mult=age_mult,
            pot_mult=pot_mult,
        )
        for c in squad
    )
    return int(total * float(bill_scale))


def strike_blocks_friendly(
    strikes: int,
    *,
    threshold: int = DEFAULT_FRIENDLY_STRIKE_BLOCK,
) -> bool:
    return int(strikes) >= int(threshold)


def strike_blocks_market(
    strikes: int,
    *,
    threshold: int = DEFAULT_MARKET_STRIKE_BLOCK,
) -> bool:
    return int(strikes) >= int(threshold)


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def contract_in_grace(
    expires_at: datetime | None,
    now: datetime | None = None,
    *,
    grace_days: int = DEFAULT_CONTRACT_GRACE_DAYS,
) -> bool:
    """True when contract is expired but still within the grace window."""
    if expires_at is None:
        return False
    now_dt = _as_utc(now or datetime.now(timezone.utc))
    exp = _as_utc(expires_at)
    if now_dt < exp:
        return False
    grace_end = exp.timestamp() + int(grace_days) * 86400
    return now_dt.timestamp() < grace_end


def contract_blocks_xi(
    expires_at: datetime | None,
    now: datetime | None = None,
    *,
    grace_days: int = DEFAULT_CONTRACT_GRACE_DAYS,
) -> bool:
    """True when past grace — cannot assign to XI / cannot play."""
    if expires_at is None:
        return False
    now_dt = _as_utc(now or datetime.now(timezone.utc))
    exp = _as_utc(expires_at)
    grace_end = exp.timestamp() + int(grace_days) * 86400
    return now_dt.timestamp() >= grace_end


def payroll_outcome_after_pay(
    *,
    coins: int,
    debt_before: int,
    bill: int,
    strikes_before: int = 0,
) -> dict[str, int]:
    """Pure preview of debt/strikes after a payroll debit (debt first)."""
    obligation = max(0, int(debt_before)) + max(0, int(bill))
    paid = min(max(0, int(coins)), obligation)
    remaining = obligation - paid
    debt_after = remaining
    strikes_after = (int(strikes_before) + 1) if debt_after > 0 else 0
    return {
        "paid_coins": paid,
        "debt_after": debt_after,
        "strikes_after": strikes_after,
        "obligation": obligation,
    }
