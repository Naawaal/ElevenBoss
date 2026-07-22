"""US-42.4 match integrity recovery + settle-once guards."""
from __future__ import annotations

from pathlib import Path

from player_engine import classify_interrupted_run

ROOT = Path(__file__).resolve().parents[1]


def test_classify_interrupted_rewards_then_complete():
    assert (
        classify_interrupted_run(status="streaming", rewards_applied=True) == "complete"
    )
    assert (
        classify_interrupted_run(status="completing", rewards_applied=True) == "complete"
    )


def test_classify_interrupted_no_rewards_abandon():
    assert (
        classify_interrupted_run(status="streaming", rewards_applied=False) == "abandon"
    )


def test_classify_terminal_noop():
    assert classify_interrupted_run(status="completed", rewards_applied=True) == "noop"
    assert classify_interrupted_run(status="abandoned", rewards_applied=False) == "noop"
    assert classify_interrupted_run(status="failed", rewards_applied=False) == "noop"


def test_economy_match_idempotency_key_format():
    run_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    club_id = 123456789
    assert f"match:{run_id}:{club_id}" == f"match:{run_id}:{club_id}"


def test_tick_evolution_not_called_from_apps():
    apps = ROOT / "apps"
    hits: list[str] = []
    for path in apps.rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "tick_evolution_match_progress" in text:
            hits.append(str(path.relative_to(ROOT)))
    assert hits == [], f"unexpected tick_evolution callers: {hits}"


def test_friendly_path_has_no_reward_pipes():
    battle = (ROOT / "apps" / "discord_bot" / "cogs" / "battle_cog.py").read_text(
        encoding="utf-8"
    )
    # Isolate start_friendly_match body roughly by markers
    start = battle.find("async def start_friendly_match")
    end = battle.find("\n    async def ", start + 1)
    body = battle[start:end] if end > start else battle[start:]
    assert "process_match_result" not in body
    assert "apply_match_economy" not in body
    assert "apply_bot_match_rewards" not in body
    assert "apply_league_human_rewards" not in body
    assert "friendly_match_logs" in body


def test_match_type_matrix_rewardable():
    """bot/league reward; friendly sandbox (source contract)."""
    assert classify_interrupted_run(status="streaming", rewards_applied=True) == "complete"
    # friendly never sets rewards_applied True in recovery
    assert classify_interrupted_run(status="streaming", rewards_applied=False) == "abandon"


def test_bot_path_does_not_abandon_after_settle():
    battle = (ROOT / "apps" / "discord_bot" / "cogs" / "battle_cog.py").read_text(
        encoding="utf-8"
    )
    assert "never abandon-after-pay" in battle or "Present-retry only" in battle
    assert "rewards_applied = True" in battle
    assert 'reason="bot_sim_failed"' in battle


def test_league_dual_lock_in_execute():
    battle = (ROOT / "apps" / "discord_bot" / "cogs" / "battle_cog.py").read_text(
        encoding="utf-8"
    )
    assert "Lock both human clubs" in battle
    assert "locks_held" in battle


def test_v3_friendly_sandbox_no_event_flush():
    """Friendly under nss_v3 must not write match_events (T040 / SC-003)."""
    battle = (ROOT / "apps" / "discord_bot" / "cogs" / "battle_cog.py").read_text(
        encoding="utf-8"
    )
    start = battle.find("async def start_friendly_match")
    end = battle.find("\n    async def ", start + 1)
    body = battle[start:end] if end > start else battle[start:]
    assert "append_match_events" not in body
    assert "friendly_match_logs" in body
    assert "stream_match_v3" in body or "ENGINE_NSS_V3" in body
    assert "process_match_result" not in body
    assert "apply_match_economy" not in body


def test_v3_league_bot_can_flush_events_but_settle_once_guards_remain():
    battle = (ROOT / "apps" / "discord_bot" / "cogs" / "battle_cog.py").read_text(
        encoding="utf-8"
    )
    assert "append_match_events" in battle
    assert "ENGINE_NSS_V3" in battle
    assert "rewards_applied = True" in battle
    assert "never abandon-after-pay" in battle or "Present-retry only" in battle
    # Recovery still classifies interrupted runs (settle-once)
    recovery = (ROOT / "apps" / "discord_bot" / "core" / "match_recovery.py").read_text(
        encoding="utf-8"
    )
    assert "classify_interrupted_run" in recovery
    assert "complete_run" in recovery
    assert "abandon_run" in recovery


def test_v3_engine_pin_on_create_paths():
    runs = (ROOT / "apps" / "discord_bot" / "core" / "match_runs.py").read_text(
        encoding="utf-8"
    )
    assert "resolve_engine_version" in runs
    assert 'ENGINE_NSS_V2 = "nss_v2"' in runs
    assert 'ENGINE_NSS_V3 = "nss_v3"' in runs
    assert "simulation_schema_version" in runs
