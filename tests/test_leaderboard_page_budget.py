"""Structural budgets for 050 leaderboard / market hot paths."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


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


def test_division_embed_uses_page_rpc_not_unbounded_select() -> None:
    src = _func_source(
        ROOT / "apps/discord_bot/cogs/leaderboard_cog.py", "_division_embed"
    )
    assert "get_division_leaderboard_page" in src
    assert ".table(\"players\")" not in src or "get_division_leaderboard_page" in src
    # Must not pull full division without RPC
    assert "order(\"league_points\"" not in src


def test_global_embed_uses_page_rpc() -> None:
    src = _func_source(
        ROOT / "apps/discord_bot/cogs/leaderboard_cog.py", "_global_embed"
    )
    assert "get_global_leaderboard_page" in src


def test_board_listings_uses_browse_rpc_not_fetch50_filter() -> None:
    src = _func_source(
        ROOT / "apps/discord_bot/views/marketplace_transfer.py", "_board_listings"
    )
    assert "browse_transfer_market" in src
    assert ".limit(50)" not in src
    assert "BANDS[\"ovr\"][ovr]" not in src


def test_sell_menu_uses_eligibility_rpc() -> None:
    src = _func_source(
        ROOT / "apps/discord_bot/cogs/marketplace_cog.py", "show_sell_menu"
    )
    assert "get_market_sell_eligible_cards" in src


def test_marketplace_hub_uses_hub_state_rpc() -> None:
    src = _func_source(
        ROOT / "apps/discord_bot/cogs/marketplace_cog.py", "show_marketplace_hub"
    )
    assert "get_marketplace_hub_state" in src


def test_cursor_roundtrip() -> None:
    from apps.discord_bot.core.cursors import decode_cursor, encode_cursor

    token = encode_cursor({"k": "div", "lp": 10, "gd": 2, "id": 99})
    assert decode_cursor(token) == {"k": "div", "lp": 10, "gd": 2, "id": 99}
    assert decode_cursor("not-a-cursor") is None
