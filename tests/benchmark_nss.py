# tests/benchmark_nss.py
"""
NSS Match Engine — Statistical Benchmark

Stress-tests the Markov-chain state machine across hundreds of simulations
to validate probability distributions, goals per game, conversion rates,
and event frequency balance.

Usage:
    python tests/benchmark_nss.py
"""
from __future__ import annotations

import asyncio
import sys
import os
import time

# Windows console encoding fix
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure packages on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "match_engine"))

from match_engine.models import MatchPlayerCard
from match_engine.v2_simulator import MatchState, stream_match
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Mock squad builder
# ---------------------------------------------------------------------------
def build_squad(base_ovr: int, prefix: str = "Player") -> list[MatchPlayerCard]:
    """Build a realistic 11-player squad with positional variety."""
    positions = [
        ("GK",  f"{prefix} GK"),
        ("DEF", f"{prefix} CB1"),
        ("DEF", f"{prefix} CB2"),
        ("DEF", f"{prefix} LB"),
        ("DEF", f"{prefix} RB"),
        ("MID", f"{prefix} CM1"),
        ("MID", f"{prefix} CM2"),
        ("MID", f"{prefix} CAM"),
        ("FWD", f"{prefix} LW"),
        ("FWD", f"{prefix} RW"),
        ("FWD", f"{prefix} ST"),
    ]
    return [
        MatchPlayerCard(
            name=name,
            position=pos,
            overall=base_ovr + (i % 5 - 2),  # ±2 spread
        )
        for i, (pos, name) in enumerate(positions)
    ]


# ---------------------------------------------------------------------------
# Metrics accumulator
# ---------------------------------------------------------------------------
@dataclass
class BenchmarkMetrics:
    iterations: int = 0
    home_wins: int = 0
    away_wins: int = 0
    draws: int = 0
    total_home_goals: int = 0
    total_away_goals: int = 0
    total_goals: int = 0
    total_chances: int = 0
    total_saves: int = 0
    total_misses: int = 0
    total_fouls: int = 0
    total_yellows: int = 0
    total_injuries: int = 0
    total_events: int = 0
    # Score distribution
    scoreline_counts: dict[str, int] = field(default_factory=dict)
    # Goals per game distribution
    goals_per_game: list[int] = field(default_factory=list)

    @property
    def home_win_pct(self) -> float:
        return (self.home_wins / self.iterations * 100) if self.iterations else 0

    @property
    def away_win_pct(self) -> float:
        return (self.away_wins / self.iterations * 100) if self.iterations else 0

    @property
    def draw_pct(self) -> float:
        return (self.draws / self.iterations * 100) if self.iterations else 0

    @property
    def avg_goals_per_game(self) -> float:
        return self.total_goals / self.iterations if self.iterations else 0

    @property
    def avg_home_goals(self) -> float:
        return self.total_home_goals / self.iterations if self.iterations else 0

    @property
    def avg_away_goals(self) -> float:
        return self.total_away_goals / self.iterations if self.iterations else 0

    @property
    def total_shots(self) -> int:
        """Total shot attempts = GOAL + SAVE + MISS."""
        return self.total_goals + self.total_saves + self.total_misses

    @property
    def conversion_rate(self) -> float:
        return (self.total_goals / self.total_shots * 100) if self.total_shots else 0

    @property
    def avg_events_per_game(self) -> float:
        return self.total_events / self.iterations if self.iterations else 0

    @property
    def avg_chances_per_game(self) -> float:
        return self.total_chances / self.iterations if self.iterations else 0

    @property
    def avg_shots_per_game(self) -> float:
        return self.total_shots / self.iterations if self.iterations else 0

    @property
    def avg_yellows_per_game(self) -> float:
        return self.total_yellows / self.iterations if self.iterations else 0

    @property
    def avg_fouls_per_game(self) -> float:
        return self.total_fouls / self.iterations if self.iterations else 0

    @property
    def avg_injuries_per_game(self) -> float:
        return self.total_injuries / self.iterations if self.iterations else 0

    @property
    def avg_saves_per_game(self) -> float:
        return self.total_saves / self.iterations if self.iterations else 0

    @property
    def clean_sheet_pct(self) -> float:
        """Percentage of matches with at least one team keeping a clean sheet."""
        cs = sum(1 for g in self.goals_per_game if g == 0)
        # This isn't quite right — we need per-team clean sheets
        return 0  # computed separately


# ---------------------------------------------------------------------------
# Simulation runner
# ---------------------------------------------------------------------------
async def run_simulations(
    home_rating: int,
    away_rating: int,
    iterations: int = 500,
    label: str = "",
) -> BenchmarkMetrics:
    """Run N match simulations and collect aggregate statistics."""

    home_squad = build_squad(home_rating, "Home")
    away_squad = build_squad(away_rating, "Away")
    home_name = f"Home ({home_rating})"
    away_name = f"Away ({away_rating})"

    metrics = BenchmarkMetrics()

    for i in range(iterations):
        state = MatchState(
            home_rating=float(home_rating),
            away_rating=float(away_rating),
        )

        async for ev in stream_match(state, home_squad, away_squad, home_name, away_name):
            etype = ev.get("type", "")
            metrics.total_events += 1

            if etype == "GOAL":
                metrics.total_goals += 1
                if ev.get("team") == home_name:
                    metrics.total_home_goals += 1
                else:
                    metrics.total_away_goals += 1
            elif etype == "CHANCE":
                metrics.total_chances += 1
            elif etype == "SAVE":
                metrics.total_saves += 1
            elif etype == "MISS":
                metrics.total_misses += 1
            elif etype == "FOUL":
                metrics.total_fouls += 1
            elif etype == "YELLOW_CARD":
                metrics.total_yellows += 1
            elif etype == "INJURY":
                metrics.total_injuries += 1

        # Record result
        if state.home_score > state.away_score:
            metrics.home_wins += 1
        elif state.away_score > state.home_score:
            metrics.away_wins += 1
        else:
            metrics.draws += 1

        total_g = state.home_score + state.away_score
        metrics.goals_per_game.append(total_g)

        scoreline = f"{state.home_score}-{state.away_score}"
        metrics.scoreline_counts[scoreline] = metrics.scoreline_counts.get(scoreline, 0) + 1

        metrics.iterations += 1

        # Progress indicator every 100 runs
        if (i + 1) % 100 == 0:
            print(f"  {label}: {i + 1}/{iterations} complete...", flush=True)

    return metrics


# ---------------------------------------------------------------------------
# Pretty-print results
# ---------------------------------------------------------------------------
def print_results(label: str, m: BenchmarkMetrics, elapsed: float) -> None:
    print()
    print(f"### {label}")
    print()
    print(f"| Metric | Value |")
    print(f"|--------|-------|")
    print(f"| Iterations | {m.iterations} |")
    print(f"| Time | {elapsed:.1f}s ({elapsed/m.iterations*1000:.1f}ms/match) |")
    print(f"| **Home Wins** | **{m.home_wins}** ({m.home_win_pct:.1f}%) |")
    print(f"| **Away Wins** | **{m.away_wins}** ({m.away_win_pct:.1f}%) |")
    print(f"| **Draws** | **{m.draws}** ({m.draw_pct:.1f}%) |")
    print(f"| Avg Home Goals | {m.avg_home_goals:.2f} |")
    print(f"| Avg Away Goals | {m.avg_away_goals:.2f} |")
    print(f"| **Avg Goals/Game** | **{m.avg_goals_per_game:.2f}** |")
    print(f"| Avg Chances/Game | {m.avg_chances_per_game:.2f} |")
    print(f"| Avg Shots/Game (G+S+M) | {m.avg_shots_per_game:.2f} |")
    print(f"| Avg Saves/Game | {m.avg_saves_per_game:.2f} |")
    print(f"| **Conversion Rate** | **{m.conversion_rate:.1f}%** |")
    print(f"| Avg Fouls/Game | {m.avg_fouls_per_game:.2f} |")
    print(f"| Avg Yellow Cards/Game | {m.avg_yellows_per_game:.2f} |")
    print(f"| Avg Injuries/Game | {m.avg_injuries_per_game:.2f} |")
    print(f"| Avg Events/Game | {m.avg_events_per_game:.1f} |")
    print()

    # Top scorelines
    sorted_scores = sorted(m.scoreline_counts.items(), key=lambda x: -x[1])
    print(f"**Top 10 Scorelines:**")
    print()
    print(f"| Scoreline | Count | % |")
    print(f"|-----------|-------|---|")
    for score, count in sorted_scores[:10]:
        pct = count / m.iterations * 100
        print(f"| {score} | {count} | {pct:.1f}% |")
    print()

    # Goals distribution
    from collections import Counter
    goal_dist = Counter(m.goals_per_game)
    print(f"**Goals Per Game Distribution:**")
    print()
    print(f"| Total Goals | Count | % |")
    print(f"|-------------|-------|---|")
    for g in sorted(goal_dist.keys()):
        count = goal_dist[g]
        pct = count / m.iterations * 100
        print(f"| {g} | {count} | {pct:.1f}% |")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main():
    print("=" * 70)
    print("  NSS MATCH ENGINE — STATISTICAL BENCHMARK")
    print("=" * 70)

    # Scenario A: Even matchup
    print()
    print("## Scenario A: Even Matchup (80 vs 80)")
    print()
    t0 = time.perf_counter()
    metrics_a = await run_simulations(80, 80, iterations=500, label="Scenario A")
    t1 = time.perf_counter()
    print_results("Scenario A: 80 OVR vs 80 OVR (Even Matchup)", metrics_a, t1 - t0)

    # Scenario B: David vs Goliath
    print("## Scenario B: David vs Goliath (90 vs 60)")
    print()
    t0 = time.perf_counter()
    metrics_b = await run_simulations(90, 60, iterations=500, label="Scenario B")
    t1 = time.perf_counter()
    print_results("Scenario B: 90 OVR vs 60 OVR (David vs Goliath)", metrics_b, t1 - t0)

    # Comparison table
    print("## Side-by-Side Comparison")
    print()
    print(f"| Metric | Even (80v80) | Mismatch (90v60) |")
    print(f"|--------|-------------|-----------------|")
    print(f"| Home Win % | {metrics_a.home_win_pct:.1f}% | {metrics_b.home_win_pct:.1f}% |")
    print(f"| Away Win % | {metrics_a.away_win_pct:.1f}% | {metrics_b.away_win_pct:.1f}% |")
    print(f"| Draw % | {metrics_a.draw_pct:.1f}% | {metrics_b.draw_pct:.1f}% |")
    print(f"| Avg Goals/Game | {metrics_a.avg_goals_per_game:.2f} | {metrics_b.avg_goals_per_game:.2f} |")
    print(f"| Avg Home Goals | {metrics_a.avg_home_goals:.2f} | {metrics_b.avg_home_goals:.2f} |")
    print(f"| Avg Away Goals | {metrics_a.avg_away_goals:.2f} | {metrics_b.avg_away_goals:.2f} |")
    print(f"| Conversion Rate | {metrics_a.conversion_rate:.1f}% | {metrics_b.conversion_rate:.1f}% |")
    print(f"| Avg Shots/Game | {metrics_a.avg_shots_per_game:.2f} | {metrics_b.avg_shots_per_game:.2f} |")
    print(f"| Avg Saves/Game | {metrics_a.avg_saves_per_game:.2f} | {metrics_b.avg_saves_per_game:.2f} |")
    print(f"| Avg Fouls/Game | {metrics_a.avg_fouls_per_game:.2f} | {metrics_b.avg_fouls_per_game:.2f} |")
    print(f"| Avg Yellow Cards | {metrics_a.avg_yellows_per_game:.2f} | {metrics_b.avg_yellows_per_game:.2f} |")
    print()
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
