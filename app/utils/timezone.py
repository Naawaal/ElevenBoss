import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger = logging.getLogger("app.utils.timezone")

def parse_relative_deadline(input_str: str, tz_str: str) -> datetime:
    parts = input_str.strip().split()
    if len(parts) != 2:
        raise ValueError("Format must be 'YYYY-MM-DD HH:MM' or 'DayOfWeek HH:MM'")
    
    day_str, time_str = parts[0], parts[1]
    
    time_parts = time_str.split(":")
    if len(time_parts) != 2:
        raise ValueError("Time must be in HH:MM format")
    try:
        hour, minute = int(time_parts[0]), int(time_parts[1])
        if not (0 <= hour <= 23) or not (0 <= minute <= 59):
            raise ValueError()
    except ValueError:
        raise ValueError("Time hours must be 0-23 and minutes 0-59.")
    
    try:
        tz = ZoneInfo(tz_str)
    except ZoneInfoNotFoundError:
        raise ValueError(f"Invalid timezone: {tz_str}")
        
    now_local = datetime.now(tz)
    
    days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    target_day = day_str.lower()
    if target_day not in days:
        raise ValueError(f"Invalid day of week: {day_str}")
    
    target_day_idx = days.index(target_day)
    current_day_idx = now_local.weekday()
    
    days_ahead = target_day_idx - current_day_idx
    if days_ahead < 0:
        days_ahead += 7
    elif days_ahead == 0:
        temp = now_local.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if temp <= now_local:
            days_ahead = 7
            
    target_date = now_local + timedelta(days=days_ahead)
    target_dt_local = target_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return target_dt_local.astimezone(ZoneInfo("UTC"))

def parse_deadline_to_utc(input_str: str, timezone_str: str) -> datetime:
    """
    Parses a deadline input string to a UTC-aware datetime.
    Supports:
      - YYYY-MM-DD HH:MM (e.g. '2026-07-05 20:00')
      - DayOfWeek HH:MM (e.g. 'Sunday 20:00')
    """
    timezone_str = timezone_str.strip()
    try:
        ZoneInfo(timezone_str)
    except ZoneInfoNotFoundError:
        raise ValueError(f"Invalid timezone: {timezone_str}")

    try:
        dt = datetime.strptime(input_str.strip(), "%Y-%m-%d %H:%M")
        return dt.replace(tzinfo=ZoneInfo(timezone_str)).astimezone(ZoneInfo("UTC"))
    except ValueError:
        pass
        
    try:
        return parse_relative_deadline(input_str, timezone_str)
    except ValueError as e:
        raise ValueError(
            f"Could not parse deadline '{input_str}'. "
            f"Expected 'YYYY-MM-DD HH:MM' or 'DayOfWeek HH:MM' (e.g. 'Sunday 20:00'). Error: {e}"
        )
