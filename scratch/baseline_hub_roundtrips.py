"""Static + optional live baseline of hub remote round-trips (US-43 T002/T014).

Counts await .execute() / sync_action_energy / get_game_config* in source for HP paths.
Live Discord timing is optional when BOT is running.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Estimated sequential remote calls BEFORE US-43 (from plan research)
BASELINE_EST = {
    "HP-1": ("training_drills", "apps/discord_bot/cogs/development_cog.py", "show_training_menu", 10),
    "HP-2": ("development_hub", "apps/discord_bot/cogs/development_cog.py", "show_hub", 6),
    "HP-3": ("store_hub", "apps/discord_bot/cogs/store_cog.py", "show_store", 4),
    "HP-4": ("profile", "apps/discord_bot/cogs/profile_cog.py", "show_profile", 5),
    "HP-5": ("squad", "apps/discord_bot/cogs/squad_cog.py", "fetch_squad_data", 5),
    "HP-6": ("league_hub", "apps/discord_bot/cogs/league_cog.py", "league_hub", 8),
}


def _count_awaits_in_func(path: Path, func_name: str) -> int | None:
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.AsyncFunctionDef) and node.name == func_name:
            return sum(isinstance(n, ast.Await) for n in ast.walk(node))
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, ast.AsyncFunctionDef) and item.name == func_name:
                    return sum(isinstance(n, ast.Await) for n in ast.walk(item))
    # Fallback: regex window (nested defs)
    m = re.search(rf"async def {func_name}\b[\s\S]*?(?=\nasync def |\nclass |\Z)", src)
    if not m:
        return None
    return m.group(0).count("await ")


def main() -> None:
    print("US-43 hub round-trip baseline (source await counts + research estimates)\n")
    print(f"{'ID':<6} {'name':<18} {'awaits':>8} {'est_RT':>8}")
    for hid, (name, rel, func, est) in BASELINE_EST.items():
        path = ROOT / rel
        awaits = _count_awaits_in_func(path, func) if path.exists() else None
        print(f"{hid:<6} {name:<18} {str(awaits):>8} {est:>8}")
    print("\nPaste into contracts/hot-path-catalog.md Baseline RTs (use est_RT for SC-004).")


if __name__ == "__main__":
    main()
