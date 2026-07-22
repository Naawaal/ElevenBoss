# packages/match_engine/match_engine/calibration/run_corpus.py
"""Golden Corpus runner — Phase 0 sporting parity (v2 baseline vs v3)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from match_engine.models import MatchPlayerCard
from match_engine.v2_simulator import MatchState, generate_match_events
from match_engine.v3 import SimulationEngine, sporting_digest
from match_engine.v3.events import from_compat_dict

GOLDEN_DIR = Path(__file__).resolve().parent / "golden"


def _xi(ovr: int, tag: str) -> list[MatchPlayerCard]:
    roles = ["GK"] + ["DEF"] * 4 + ["MID"] * 4 + ["FWD"] * 2
    return [
        MatchPlayerCard(
            name=f"{tag}{i}",
            position=roles[i],
            overall=ovr,
            pac=ovr,
            sho=ovr,
            pas=ovr,
            dri=ovr,
            def_stat=ovr,
            phy=ovr,
            card_id=f"{tag}-{i}",
        )
        for i in range(11)
    ]


def fixture_matrix() -> list[dict[str, Any]]:
    """≥50 fixtures spanning even / underdog / seed variants."""
    rows: list[dict[str, Any]] = []
    pairs = [
        (70, 70), (75, 75), (80, 80), (65, 65), (72, 72),
        (78, 62), (85, 70), (60, 75), (90, 68), (55, 80),
        (73, 71), (68, 74), (77, 66), (64, 79), (82, 72),
    ]
    seeds = list(range(100, 140))
    i = 0
    for home_ovr, away_ovr in pairs:
        for seed in seeds[:4]:
            rows.append({
                "id": f"g{i:03d}",
                "seed": seed + home_ovr + away_ovr,
                "home_ovr": home_ovr,
                "away_ovr": away_ovr,
                "parity_class": "exact_parity",
                "match_kind": ("bot", "league", "friendly")[i % 3],
            })
            i += 1
            if len(rows) >= 60:
                return rows
    while len(rows) < 60:
        n = len(rows)
        rows.append({
            "id": f"g{n:03d}",
            "seed": 500 + n,
            "home_ovr": 70 + (n % 10),
            "away_ovr": 70 - (n % 8),
            "parity_class": "exact_parity",
            "match_kind": "bot",
        })
    return rows


def _v2_sporting(home_ovr: int, away_ovr: int, seed: int) -> tuple[str, int, int]:
    import random

    home, away = _xi(home_ovr, "H"), _xi(away_ovr, "A")
    state = MatchState(home_rating=float(home_ovr), away_rating=float(away_ovr))
    state.interactive_sides = []
    raw = list(generate_match_events(state, home, away, "Home", "Away", rng=random.Random(seed)))
    events = [from_compat_dict(e, seq=i + 1, engine_version="nss_v2") for i, e in enumerate(raw)]
    return sporting_digest(events, home_score=state.home_score, away_score=state.away_score), state.home_score, state.away_score


def _v3_sporting(home_ovr: int, away_ovr: int, seed: int) -> tuple[str, int, int]:
    home, away = _xi(home_ovr, "H"), _xi(away_ovr, "A")
    eng = SimulationEngine()
    ctx = eng.initial_context(
        home=home,
        away=away,
        home_name="Home",
        away_name="Away",
        home_rating=float(home_ovr),
        away_rating=float(away_ovr),
        seed=seed,
    )
    eng.run_to_completion(ctx)
    assert eng._state is not None
    d = eng.digests()["sporting"]
    return d, eng._state.home_score, eng._state.away_score


def write_baselines(path: Path | None = None) -> Path:
    out = path or (GOLDEN_DIR / "baselines.json")
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    fixtures = []
    for row in fixture_matrix():
        digest, hs, aws = _v2_sporting(row["home_ovr"], row["away_ovr"], row["seed"])
        fixtures.append({**row, "expected_sporting_digest": digest, "home_score": hs, "away_score": aws})
    out.write_text(json.dumps({"fixtures": fixtures}, indent=2), encoding="utf-8")
    return out


def run_corpus(path: Path | None = None) -> list[str]:
    """Return list of failure messages (empty = pass)."""
    p = path or (GOLDEN_DIR / "baselines.json")
    if not p.exists():
        write_baselines(p)
    data = json.loads(p.read_text(encoding="utf-8"))
    failures: list[str] = []
    for row in data["fixtures"]:
        d3, hs, aws = _v3_sporting(row["home_ovr"], row["away_ovr"], row["seed"])
        if row["parity_class"] == "exact_parity":
            if d3 != row["expected_sporting_digest"]:
                failures.append(
                    f"{row['id']}: sporting digest mismatch (scores v3={hs}-{aws} "
                    f"baseline={row.get('home_score')}-{row.get('away_score')})"
                )
            elif hs != row.get("home_score") or aws != row.get("away_score"):
                failures.append(f"{row['id']}: score mismatch")
    return failures


if __name__ == "__main__":
    out = write_baselines()
    fails = run_corpus(out)
    print(f"Wrote {out}; failures={len(fails)}")
    for f in fails[:10]:
        print(f)
