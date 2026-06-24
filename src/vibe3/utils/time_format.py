"""Time formatting utilities for age-aware display."""

from datetime import datetime, timezone


def format_age_aware_time(
    utc_time: datetime | str,
    now: datetime | None = None,
) -> str:
    """Format datetime with age-aware Chinese display.

    4-tier time format based on calendar days:
    - Today: HH:MM:SS
    - Yesterday: 昨天 HH:MM
    - <7 days: X天前 HH:MM
    - ≥7 days: MM-DD HH:MM

    Args:
        utc_time: UTC datetime or ISO format string
            (e.g., "2026-05-16 10:30:00")
        now: Optional fixed timestamp for testing
            (defaults to datetime.now(timezone.utc))

    Returns:
        Age-aware formatted time string in Chinese

    Examples:
        >>> from datetime import datetime, timezone, timedelta
        >>> now = datetime(2026, 5, 16, 12, 0, 0, tzinfo=timezone.utc)
        >>> format_age_aware_time(now, now=now)
        '20:00:00'  # Today (converted to local timezone)
        >>> yesterday = now - timedelta(days=1)
        >>> format_age_aware_time(yesterday, now=now)
        '昨天 20:00'
    """
    # Use fixed now for testing or real clock
    if now is None:
        now = datetime.now(timezone.utc)

    # Parse time if string provided
    parsed_time: datetime
    if isinstance(utc_time, str):
        if len(utc_time) < 19:
            # Fallback: return original string
            return utc_time
        try:
            parsed_time = datetime.strptime(utc_time[:19], "%Y-%m-%d %H:%M:%S")
            parsed_time = parsed_time.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            # Fallback: extract time part (chars 11:19)
            # Type checker knows utc_time is str here
            return utc_time[11:19]
    else:
        # Already a datetime
        parsed_time = utc_time

    # Convert to system local timezone
    local_time = parsed_time.astimezone()
    now_local = now.astimezone()

    # Calculate age in calendar days
    calendar_days = (now_local.date() - local_time.date()).days

    # Apply 4-tier time format based on age
    if calendar_days == 0:
        # Today: HH:MM:SS
        return local_time.strftime("%H:%M:%S")
    elif calendar_days == 1:
        # Yesterday: 昨天 HH:MM
        return f"昨天 {local_time.strftime('%H:%M')}"
    elif calendar_days < 7:
        # <7 days: X天前 HH:MM
        time_part = local_time.strftime("%H:%M")
        return f"{calendar_days}天前 {time_part}"
    else:
        # ≥7 days: MM-DD HH:MM
        return local_time.strftime("%m-%d %H:%M")


def format_timestamp_local(ts_str: str) -> str:
    """Convert ISO timestamp string to local time for display.

    Handles both UTC timestamps from SQLite (e.g. +00:00) and
    already-local timestamps from handoff files (e.g. +08:00).

    Args:
        ts_str: ISO 8601 timestamp string

    Returns:
        Local time formatted as "YYYY-MM-DD HH:MM"
    """
    try:
        dt = datetime.fromisoformat(ts_str)
        local_dt = dt.astimezone()
        return local_dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, KeyError):
        # Fallback: raw string extraction
        return ts_str[:16].replace("T", " ")
