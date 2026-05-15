"""Tests for handoff_read helper functions."""

from datetime import datetime, timedelta, timezone

import pytest

from vibe3.commands.handoff_read import _format_relative_time


@pytest.mark.parametrize(
    "seconds_offset,expected_output",
    [
        pytest.param(0, "just now", id="0_seconds"),
        pytest.param(30, "just now", id="30_seconds"),
        pytest.param(59, "just now", id="59_seconds"),
        pytest.param(60, "1 minute ago", id="60_seconds"),
        pytest.param(61, "1 minute ago", id="61_seconds"),
        pytest.param(120, "2 minutes ago", id="120_seconds"),
        pytest.param(3599, "59 minutes ago", id="3599_seconds"),
        pytest.param(3600, "1 hour ago", id="3600_seconds"),
        pytest.param(7200, "2 hours ago", id="7200_seconds"),
        pytest.param(86399, "23 hours ago", id="86399_seconds"),
        pytest.param(86400, "1 day ago", id="86400_seconds"),
        pytest.param(172800, "2 days ago", id="172800_seconds"),
        pytest.param(2591999, "29 days ago", id="2591999_seconds"),
        pytest.param(2592000, "1 month ago", id="2592000_seconds"),
        pytest.param(5184000, "2 months ago", id="5184000_seconds"),
    ],
)
def test_format_relative_time_boundary_values(seconds_offset, expected_output):
    """Test _format_relative_time at key boundaries.

    Verifies correct pluralization and unit transitions at:
    - 59s → 60s: just now → 1 minute ago
    - 59m → 60m: 59 minutes ago → 1 hour ago
    - 23h → 24h: 23 hours ago → 1 day ago
    - 29d → 30d: 29 days ago → 1 month ago
    """
    now = datetime.now(timezone.utc)
    timestamp = now - timedelta(seconds=seconds_offset)
    result = _format_relative_time(timestamp)
    assert result == expected_output


def test_format_relative_time_assumes_utc_for_naive_datetime():
    """Test that naive datetime (no timezone) is assumed to be UTC."""
    # Create a naive datetime 5 minutes ago
    now_utc = datetime.now(timezone.utc)
    naive_timestamp = (now_utc - timedelta(minutes=5)).replace(tzinfo=None)

    result = _format_relative_time(naive_timestamp)

    # Should treat it as UTC and return "5 minutes ago"
    assert result == "5 minutes ago"
