"""Tests for age-aware time formatting utility."""

from datetime import datetime, timedelta, timezone

import pytest

from vibe3.utils.time_format import format_age_aware_time


@pytest.mark.parametrize(
    "days_offset,expected_pattern",
    [
        pytest.param(0, r"^\d{2}:\d{2}:\d{2}$", id="today"),
        pytest.param(1, r"^昨天 \d{2}:\d{2}$", id="yesterday"),
        pytest.param(2, r"^2天前 \d{2}:\d{2}$", id="2_days_ago"),
        pytest.param(6, r"^6天前 \d{2}:\d{2}$", id="6_days_ago"),
        pytest.param(7, r"^\d{2}-\d{2} \d{2}:\d{2}$", id="7_days_ago"),
        pytest.param(30, r"^\d{2}-\d{2} \d{2}:\d{2}$", id="30_days_ago"),
    ],
)
def test_format_age_aware_time_boundary_values(days_offset, expected_pattern):
    """Test format_age_aware_time at key boundaries.

    Verifies correct format transitions at:
    - Today: HH:MM:SS
    - Yesterday: 昨天 HH:MM
    - 2-6 days: X天前 HH:MM
    - ≥7 days: MM-DD HH:MM
    """
    # Use fixed clock for deterministic testing
    fixed_now = datetime(2026, 5, 16, 12, 0, 0, tzinfo=timezone.utc)
    past_time = fixed_now - timedelta(days=days_offset)

    result = format_age_aware_time(past_time, now=fixed_now)

    import re

    assert re.match(
        expected_pattern, result
    ), f"Result '{result}' doesn't match pattern '{expected_pattern}'"


def test_format_age_aware_time_string_input():
    """Test that string input is parsed correctly."""
    fixed_now = datetime(2026, 5, 16, 12, 0, 0, tzinfo=timezone.utc)

    # Today: should return local time (HH:MM:SS format)
    time_str = "2026-05-16 10:30:00"
    result = format_age_aware_time(time_str, now=fixed_now)
    # Should convert to local timezone and display as HH:MM:SS
    import re

    assert re.match(r"^\d{2}:\d{2}:\d{2}$", result)
    # Verify it's in "today" format (not 昨天 or X天前)
    assert "昨天" not in result and "天前" not in result

    # Yesterday: should return 昨天 HH:MM format
    time_str = "2026-05-15 10:30:00"
    result = format_age_aware_time(time_str, now=fixed_now)
    assert "昨天" in result
    import re

    assert re.match(r"^昨天 \d{2}:\d{2}$", result)


def test_format_age_aware_time_short_string_fallback():
    """Test fallback behavior for malformed strings."""
    # Too short: should return original string
    time_str = "short"
    result = format_age_aware_time(time_str)
    assert result == "short"

    # Valid length but invalid format: should extract time part (chars 11:19)
    time_str = "invalid-format-here-but-19chars"
    result = format_age_aware_time(time_str)
    # str[11:19] extracts characters at indices 11-18
    assert result == time_str[11:19]  # "here-but-"


def test_format_age_aware_time_real_clock():
    """Test that function works with real clock (no now parameter)."""
    # Create a datetime 1 minute ago
    past_time = datetime.now(timezone.utc) - timedelta(minutes=1)

    result = format_age_aware_time(past_time)

    # Should be "today" format since it's only 1 minute ago
    import re

    assert re.match(r"^\d{2}:\d{2}:\d{2}$", result)


def test_format_age_aware_time_timezone_conversion():
    """Test that UTC time is properly converted to local timezone."""
    fixed_now = datetime(2026, 5, 16, 12, 0, 0, tzinfo=timezone.utc)

    # UTC time should be converted to local timezone
    utc_time = datetime(2026, 5, 16, 4, 0, 0, tzinfo=timezone.utc)
    result = format_age_aware_time(utc_time, now=fixed_now)

    # Should be in "today" format (HH:MM:SS)
    import re

    assert re.match(r"^\d{2}:\d{2}:\d{2}$", result)

    # The displayed time should be the local equivalent (not UTC 04:00)
    # We can't hardcode the local time because CI runs in UTC timezone
    # But we can verify that astimezone() was called (format differs from UTC input)
    local_time = utc_time.astimezone()
    expected_str = local_time.strftime("%H:%M:%S")
    assert result == expected_str
