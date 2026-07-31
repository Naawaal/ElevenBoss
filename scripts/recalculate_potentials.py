#!/usr/bin/env python3
"""UNSAFE for 049 — do not use to "fix" POT after rarity caps.

This script called generate_potential and wrote potential/base_potential.
Illegal overall above rarity cap now raises; re-running against corrupted OVR
rows would fail or recreate bad states if the escape returned.

Use scripts/potential_cap_audit.py + scripts/potential_cap_repair.py instead.
"""
from __future__ import annotations

import sys


def main() -> int:
    print(
        "scripts/recalculate_potentials.py is retired for rarity-cap integrity (049).\n"
        "Use: python scripts/potential_cap_audit.py\n"
        "Then: python scripts/potential_cap_repair.py --batch BATCH --apply",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
