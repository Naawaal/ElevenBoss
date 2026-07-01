# tests/test_schedule_service.py

import pytest
from datetime import datetime
from zoneinfo import ZoneInfo
from app.models.guild_config import GuildConfig
from app.services.schedule_service import ScheduleService

def test_is_matchday_due_disabled():
    config = GuildConfig(
        guild_id="123456",
        matchday_enabled=False,
        matchday_day="Sunday",
        matchday_time="18:00",
        matchday_timezone="Asia/Kathmandu"
    )
    # Sunday, July 5, 2026 18:00 Local Kathmandu is Sunday, July 5, 2026 12:15 UTC
    now_utc = datetime(2026, 7, 5, 12, 15, tzinfo=ZoneInfo("UTC"))
    assert not ScheduleService.is_matchday_due(config, now_utc)

def test_is_matchday_due_exact():
    config = GuildConfig(
        guild_id="123456",
        matchday_enabled=True,
        matchday_day="Sunday",
        matchday_time="18:00",
        matchday_timezone="Asia/Kathmandu"
    )
    # Sunday, July 5, 2026 18:00 Local Kathmandu is 12:15 UTC
    now_utc = datetime(2026, 7, 5, 12, 15, tzinfo=ZoneInfo("UTC"))
    assert ScheduleService.is_matchday_due(config, now_utc)

def test_is_matchday_due_within_tolerance():
    config = GuildConfig(
        guild_id="123456",
        matchday_enabled=True,
        matchday_day="Sunday",
        matchday_time="18:00",
        matchday_timezone="Asia/Kathmandu"
    )
    # 18:10 Local Kathmandu (12:25 UTC) is within 15 minutes tolerance
    now_utc = datetime(2026, 7, 5, 12, 25, tzinfo=ZoneInfo("UTC"))
    assert ScheduleService.is_matchday_due(config, now_utc)

def test_is_matchday_due_past_tolerance():
    config = GuildConfig(
        guild_id="123456",
        matchday_enabled=True,
        matchday_day="Sunday",
        matchday_time="18:00",
        matchday_timezone="Asia/Kathmandu"
    )
    # 18:20 Local Kathmandu (12:35 UTC) is past 15 minutes tolerance
    now_utc = datetime(2026, 7, 5, 12, 35, tzinfo=ZoneInfo("UTC"))
    assert not ScheduleService.is_matchday_due(config, now_utc)

def test_is_matchday_due_wrong_day():
    config = GuildConfig(
        guild_id="123456",
        matchday_enabled=True,
        matchday_day="Sunday",
        matchday_time="18:00",
        matchday_timezone="Asia/Kathmandu"
    )
    # Monday, July 6, 2026 18:00 Local Kathmandu is Monday, July 6, 2026 12:15 UTC
    now_utc = datetime(2026, 7, 6, 12, 15, tzinfo=ZoneInfo("UTC"))
    assert not ScheduleService.is_matchday_due(config, now_utc)

def test_get_last_scheduled_occurrence():
    config = GuildConfig(
        guild_id="123456",
        matchday_enabled=True,
        matchday_day="Sunday",
        matchday_time="18:00",
        matchday_timezone="Asia/Kathmandu"
    )
    # Tuesday, July 7, 2026 12:00 UTC
    # Last Sunday occurrence was July 5, 2026 18:00 local Kathmandu (12:15 UTC)
    now_utc = datetime(2026, 7, 7, 12, 0, tzinfo=ZoneInfo("UTC"))
    last_occ = ScheduleService.get_last_scheduled_occurrence(config, now_utc)
    assert last_occ is not None
    assert last_occ == datetime(2026, 7, 5, 12, 15, tzinfo=ZoneInfo("UTC"))
