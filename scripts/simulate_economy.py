#!/usr/bin/env python3
"""30-day economy supply simulation for US-25 archetypes."""
from __future__ import annotations

import argparse

from economy.flows import simulate_days, simulate_casual_day, simulate_hardcore_day


ARCHETYPES = ("casual", "hardcore", "gacha_farmer")


def main() -> int:
    parser = argparse.ArgumentParser(description="Simulate ElevenBoss economy over N days")
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()

    print(f"Economy simulation — {args.days} days\n")
    for name in ARCHETYPES:
        series = simulate_days(name, args.days)
        net = series[-1] if series else 0
        flag = "INFLATION RISK" if net > 100_000 else "OK"
        print(f"  {name:14} cumulative net: {net:>8,} coins  [{flag}]")

    casual = simulate_casual_day()
    hardcore = simulate_hardcore_day()
    print(f"\nSingle-day casual:   income {casual.income:,}  expenses {casual.expenses:,}  net {casual.net:,}")
    print(f"Single-day hardcore: income {hardcore.income:,}  expenses {hardcore.expenses:,}  net {hardcore.net:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
