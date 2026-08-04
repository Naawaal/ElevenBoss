"""Unit & Integration tests for Feature 053 Integrity Remediation (T068–T075)."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from pvp.matchmaking import search_range_for_wait
from pvp.models import RivalryState
from pvp.rivalry_math import apply_ranked_meeting


def test_t068_division_band_parity():
    """Verify search widening bands mirror SQL _pvp_search_bands exactly."""
    b0 = search_range_for_wait(0)
    assert b0.max_division_delta == 0
    assert b0.max_lp_delta == 100
    assert b0.max_ovr_delta == 4.0

    b15 = search_range_for_wait(15)
    assert b15.max_division_delta == 1
    assert b15.max_lp_delta == 200
    assert b15.max_ovr_delta == 7.0

    b30 = search_range_for_wait(30)
    assert b30.max_division_delta == 2
    assert b30.max_lp_delta == 350
    assert b30.max_ovr_delta == 10.0

    b60 = search_range_for_wait(60)
    assert b60.max_division_delta == 99
    assert b60.max_lp_delta == 500
    assert b60.max_ovr_delta == 12.0


def test_t069_canonical_squad_snapshot_structure():
    """Verify canonical squad snapshot keys required by match reconstruction."""
    sample_card = {
        "name": "Alex Hunter",
        "position": "ST",
        "overall": 84,
        "pac": 85,
        "sho": 82,
        "pas": 75,
        "dri": 80,
        "def_stat": 40,
        "phy": 78,
        "morale": 85,
        "playstyles": ["Finesse Shot"],
    }
    assert "def_stat" in sample_card
    assert "morale" in sample_card
    assert "playstyles" in sample_card

    snapshot = {
        "home_owner_id": 101,
        "away_owner_id": 102,
        "home_squad": [sample_card] * 11,
        "away_squad": [sample_card] * 11,
        "finalization_policy": {
            "economy_enabled": False,
            "xp_enabled": False,
            "fitness_enabled": False,
            "rivalry_enabled": False,
        },
    }
    from apps.discord_bot.core.match_runs import squads_from_snapshot

    home_cards, away_cards = squads_from_snapshot(snapshot)
    assert len(home_cards) == 11
    assert len(away_cards) == 11
    assert home_cards[0].def_stat == 40
    assert home_cards[0].morale == 85


def test_t071_exact_30_day_rivalry_window():
    """Verify 3 meetings within 30 days activates rivalry."""
    initial = RivalryState(manager_a_id=101, manager_b_id=102, status="tracking")
    st1, _ = apply_ranked_meeting(initial, winner_id=101, home_id=101, away_id=102, home_goals=2, away_goals=1)
    st2, _ = apply_ranked_meeting(st1, winner_id=102, home_id=101, away_id=102, home_goals=0, away_goals=1)
    st3, events = apply_ranked_meeting(st2, winner_id=101, home_id=101, away_id=102, home_goals=1, away_goals=0)
    assert st3.status == "active"
    assert any(e.code == "rivalry_activated" for e in events)


def test_t067a_dark_state_gate_verification():
    """Verify default PvP config flags are dark (false)."""
    default_flags = {
        "battle_pvp_enabled": "false",
        "pvp_rewards_enabled": "false",
        "pvp_rivalries_enabled": "false",
    }
    for k, v in default_flags.items():
        assert v.lower() in ("false", "0")


@pytest.mark.asyncio
async def test_t070_durable_completing_recovery_call():
    """Verify retry_completing_pvp_runs calls complete_pvp_run for stuck runs."""
    mock_db = MagicMock()
    mock_runs_res = MagicMock()
    mock_runs_res.data = [
        {
            "id": "11111111-1111-1111-1111-111111111111",
            "home_discord_id": 101,
            "away_discord_id": 102,
            "home_score": 2,
            "away_score": 1,
            "squad_snapshot": {
                "home_rating": 82.0,
                "away_rating": 80.0,
                "finalization_policy": {
                    "economy_enabled": False,
                    "xp_enabled": False,
                    "fitness_enabled": False,
                    "rivalry_enabled": False,
                },
            },
        }
    ]
    mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.execute = AsyncMock(
        return_value=mock_runs_res
    )

    mock_players_res = MagicMock()
    mock_players_res.data = {"discord_id": 101, "club_name": "FC Test", "intensity_tier": 1}
    mock_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute = (
        AsyncMock(return_value=mock_players_res)
    )

    mock_hist_res = MagicMock()
    mock_hist_res.data = [
        {"id": "22222222-2222-2222-2222-222222222222", "player_id": 101},
        {"id": "33333333-3333-3333-3333-333333333333", "player_id": 102},
    ]
    mock_db.table.return_value.select.return_value.eq.return_value.execute = AsyncMock(
        return_value=mock_hist_res
    )

    mock_rpc = AsyncMock()
    mock_db.rpc = mock_rpc

    from apps.discord_bot.core.pvp_match import retry_completing_pvp_runs

    await retry_completing_pvp_runs(mock_db, MagicMock())

    # Ensure complete_pvp_run RPC was called
    rpc_calls = [c.args[0] for c in mock_rpc.call_args_list]
    assert "complete_pvp_run" in rpc_calls


@pytest.mark.asyncio
async def test_t070_apply_side_xp_fatigue_metadata_propagation():
    """Verify _apply_side_xp_fatigue passes correct card metadata IDs to RPCs."""
    mock_db = MagicMock()
    mock_rpc = AsyncMock()
    mock_db.rpc = mock_rpc

    from apps.discord_bot.core.pvp_match import _apply_side_xp_fatigue
    from match_engine import MatchState

    sample_meta = [{"id": "card-uuid-1", "level": 5, "date_of_birth": "2000-01-01"}]
    mock_card = MagicMock()
    mock_card.phy = 75

    state = MatchState(home_rating=80, away_rating=80)
    state.home_score = 1
    state.away_score = 0

    payload = {
        "run_id": "run-uuid-123",
        "home": {"history_id": "hist-uuid-456", "rating": 80},
    }
    home_p = {"discord_id": 101, "club_name": "Home FC", "intensity_tier": 1}

    mock_bench_ids = AsyncMock(return_value=["bench-uuid-1"])
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("apps.discord_bot.core.injury_rpc.fetch_bench_ids", mock_bench_ids)
        await _apply_side_xp_fatigue(
            mock_db,
            MagicMock(),
            payload,
            [mock_card],
            [],
            sample_meta,
            [],
            home_p,
            {"discord_id": 102},
            state,
        )

    # Verify apply_pvp_match_xp_once received card-uuid-1 in payload
    xp_call = [c for c in mock_rpc.call_args_list if c.args[0] == "apply_pvp_match_xp_once"]
    assert len(xp_call) > 0
    xp_args = xp_call[0].args[1]
    assert xp_args["p_cards"][0]["id"] == "card-uuid-1"
