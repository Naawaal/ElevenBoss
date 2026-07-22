"""US-42.7 economy registry + pipe guards."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPS = ROOT / "apps"
REGISTRY = (
    ROOT
    / "specs"
    / "035-integrity-remainder"
    / "contracts"
    / "economy-source-sink-registry.md"
)
BATTLE = ROOT / "apps" / "discord_bot" / "cogs" / "battle_cog.py"

REQUIRED_IDS = (
    "match_bot_payout",
    "match_league_payout",
    "friendly_sandbox",
    "season_prize",
    "daily_login",
    "energy_refill",
    "weekly_payroll",
    "transfer_buy",
    "transfer_sale",
    "transfer_tax_burn",
    "stat_drill",
    "fusion_fodder",
    "tokens_gems",
)


def test_registry_file_exists_with_required_ids():
    text = REGISTRY.read_text(encoding="utf-8")
    assert "apply_club_economy" in text
    for rid in REQUIRED_IDS:
        assert f"`{rid}`" in text or rid in text, f"missing registry id {rid}"


def test_no_direct_players_coins_update_in_apps():
    """Forbid app-level coin column writes; pipe only."""
    hits: list[str] = []
    for path in APPS.rglob("*.py"):
        raw = path.read_text(encoding="utf-8", errors="ignore")
        # table("players").update({... coins ...}) or SET coins
        if 'table("players")' in raw or "table('players')" in raw:
            if ".update(" in raw and "coins" in raw:
                # allow reads of coins in same file only if update doesn't set coins
                for i, line in enumerate(raw.splitlines(), 1):
                    if ".update(" in line and "coins" in line:
                        hits.append(f"{path.relative_to(ROOT)}:{i}:{line.strip()[:80]}")
        if "SET coins" in raw or "set coins" in raw:
            hits.append(str(path.relative_to(ROOT)))
    assert hits == [], f"direct coin updates: {hits}"


def test_friendly_path_still_sandbox():
    battle = BATTLE.read_text(encoding="utf-8")
    start = battle.find("async def start_friendly_match")
    assert start > 0
    end = battle.find("\n    async def ", start + 1)
    body = battle[start:end] if end > start else battle[start:]
    assert "apply_match_economy" not in body
    assert "apply_bot_match_rewards" not in body
    assert "process_match_result" not in body
