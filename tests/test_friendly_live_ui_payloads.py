import unittest
from unittest.mock import MagicMock
import pytest

# Mock asyncio.get_running_loop() before importing any discord.ui components
mock_loop = MagicMock()
mock_loop.create_future.return_value = MagicMock()
import asyncio
asyncio.get_running_loop = MagicMock(return_value=mock_loop)

from app.ui.layouts.friendly_live import (
    build_friendly_invite_layout,
    build_friendly_practice_layout,
    build_live_kickoff_layout,
    build_live_chunk_layout,
    build_live_halftime_layout,
    build_live_fulltime_layout,
)
from app.ui.components import V2View

def test_friendly_live_invite_layout_payloads():
    view = build_friendly_invite_layout("Club A", "Club B", "<@123>", "nonce123", 1700000000)
    assert isinstance(view, V2View)
    payload = view.to_components()
    assert len(payload) == 2  # Container + Action Row
    
    # Verify Accept / Decline / Cancel buttons
    buttons = payload[1]["components"]
    assert len(buttons) == 3
    assert "friendly:accept:challenge:nonce123" in buttons[0]["custom_id"]
    assert "friendly:decline:challenge:nonce123" in buttons[1]["custom_id"]
    assert "friendly:cancel:challenge:nonce123" in buttons[2]["custom_id"]
    
    # Verify timer text is present
    container_text = payload[0]["components"][0]["content"]
    assert "Expires:" in container_text
    assert "<t:1700000000:R>" in container_text

def test_friendly_live_practice_layout_payloads():
    view = build_friendly_practice_layout("nonce123")
    assert isinstance(view, V2View)
    payload = view.to_components()
    assert len(payload) == 3  # Container + Select Menu Action Row + Close Action Row
    
    # Verify select options exist
    select_menu = payload[1]["components"][0]
    assert select_menu["type"] == 3 # STRING_SELECT
    assert "friendly:practice:select:nonce123" in select_menu["custom_id"]
    assert len(select_menu["options"]) == 5

def test_live_kickoff_layout_payloads():
    view = build_live_kickoff_layout("Club A", "Club B", "nonce123")
    assert isinstance(view, V2View)
    payload = view.to_components()
    assert len(payload) == 2  # Kickoff message container + Skip action row

def test_live_chunk_layout_payloads():
    view = build_live_chunk_layout("Club A", "Club B", 1, 0, 30, "Some events", "nonce123")
    assert isinstance(view, V2View)
    payload = view.to_components()
    assert len(payload) == 3  # Header Container + Events Container + Skip action row
    assert "Club A" in payload[0]["components"][0]["content"]
    assert "Some events" in payload[1]["components"][0]["content"]

def test_live_halftime_layout_payloads():
    view = build_live_halftime_layout("Club A", "Club B", 1, 1, "Events", "Stats", "nonce123")
    assert isinstance(view, V2View)
    payload = view.to_components()
    assert len(payload) == 4  # Header + Events + Stats + Skip action row
    assert "Stats" in payload[2]["components"][0]["content"]

def test_live_fulltime_layout_payloads():
    view = build_live_fulltime_layout("Club A", "Club B", 2, 1, "Messi", "Events", "Stats", "nonce123")
    assert isinstance(view, V2View)
    payload = view.to_components()
    assert len(payload) == 3  # Header + Stats + Events
    header_content = payload[0]["components"][0]["content"]
    assert "Messi" in header_content
    assert "**Winner:** **Club A**" in header_content
