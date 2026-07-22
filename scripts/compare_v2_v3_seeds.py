# scripts/compare_v2_v3_seeds.py
"""Thin CLI for offline calibration (never used by Discord)."""
from __future__ import annotations

from match_engine.calibration.dixon_coles_harness import run_dixon_coles_sample
from match_engine.calibration.run_corpus import run_corpus, write_baselines


def main() -> None:
    print("Dixon-Coles surface:", run_dixon_coles_sample())
    write_baselines()
    fails = run_corpus()
    print(f"Golden corpus failures: {len(fails)}")
    for f in fails[:5]:
        print(" ", f)
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
