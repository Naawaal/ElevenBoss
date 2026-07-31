"""Annotated max RT expectations for 050 hub hot paths (structural)."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Contract budgets (contracts/round-trip-budgets.md) — after Phase 2 / US5:
# development hub ≤2 (sync_action_energy + get_development_hub_state)
# marketplace hub = 1 (get_marketplace_hub_state)
# leaderboard page = 1 page RPC
MAX_RT = {
    "development_hub": 2,
    "marketplace_hub": 1,
    "leaderboard_division": 1,
    "leaderboard_global": 1,
}


def _func_source(path: Path, func_name: str) -> str:
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.AsyncFunctionDef) and node.name == func_name:
            return ast.get_source_segment(src, node) or ""
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, ast.AsyncFunctionDef) and item.name == func_name:
                    return ast.get_source_segment(src, item) or ""
    raise AssertionError(f"{func_name} not found in {path}")


def test_development_hub_uses_hub_state_rpc_not_scatter_reads() -> None:
    src = _func_source(
        ROOT / "apps/discord_bot/cogs/development_cog.py", "show_hub"
    )
    assert "get_development_hub_state" in src
    assert "ensure_pending_legendary" not in src
    assert "unclaimed_reward_count" not in src
    assert "support_legendary_pending" not in src
    assert MAX_RT["development_hub"] <= 2


def test_skills_menu_uses_allocation_hub_rpc() -> None:
    src = _func_source(
        ROOT / "apps/discord_bot/cogs/development_cog.py", "show_skills_menu"
    )
    assert "get_skill_allocation_hub" in src
    assert '.table("player_cards")' not in src


def test_mentor_targets_uses_rpc() -> None:
    src = _func_source(
        ROOT / "apps/discord_bot/cogs/development_cog.py", "_load_mentor_targets"
    )
    assert "get_mentor_targets" in src
    assert "listed_card_ids" not in src


def test_marketplace_and_leaderboard_hub_budgets() -> None:
    mkt = _func_source(
        ROOT / "apps/discord_bot/cogs/marketplace_cog.py", "show_marketplace_hub"
    )
    assert "get_marketplace_hub_state" in mkt
    div = _func_source(
        ROOT / "apps/discord_bot/cogs/leaderboard_cog.py", "_division_embed"
    )
    assert "get_division_leaderboard_page" in div
    glob = _func_source(
        ROOT / "apps/discord_bot/cogs/leaderboard_cog.py", "_global_embed"
    )
    assert "get_global_leaderboard_page" in glob
    assert MAX_RT["marketplace_hub"] == 1
    assert MAX_RT["leaderboard_division"] == 1
