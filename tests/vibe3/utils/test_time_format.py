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

    # Today: should return HH:MM:SS
    time_str = "2026-05-16 10:30:00"
    result = format_age_aware_time(time_str, now=fixed_now)
    assert result == "18:30:00"  # UTC 10:30 converted to local timezone (UTC+8)

    # Yesterday: should return 昨天 HH:MM
    time_str = "2026-05-15 10:30:00"
    result = format_age_aware_time(time_str, now=fixed_now)
    assert result == "昨天 18:30"


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

    # UTC 04:00 → Local 12:00 (UTC+8)
    utc_time = datetime(2026, 5, 16, 4, 0, 0, tzinfo=timezone.utc)
    result = format_age_aware_time(utc_time, now=fixed_now)
    # Local time at UTC+8 should be 12:00:00
    assert result == "12:00:00"
