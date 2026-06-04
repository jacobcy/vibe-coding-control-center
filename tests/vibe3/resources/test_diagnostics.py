"""Tests for diagnostic message formatting."""

from __future__ import annotations

from vibe3.exceptions.diagnostic_errors import DiagnosticContext
from vibe3.utils.diagnostics import format_diagnostic_message


def test_format_diagnostic_message_contains_all_fields() -> None:
    """format_diagnostic_message should include all context fields."""
    context = DiagnosticContext(
        resource_type="test-resource",
        search_paths=["/path/1", "/path/2"],
        profile="test-profile",
        remediation="Test fix action",
        ref_issue=123,
    )
    message = format_diagnostic_message("test-resource", context)

    assert "Missing test-resource: test-resource" in message
    assert "Searched paths:" in message
    assert "/path/1" in message
    assert "/path/2" in message
    assert "Current profile: test-profile" in message
    assert "Suggested fix: Test fix action" in message
    assert "See issue #123" in message


def test_format_diagnostic_message_handles_none_profile() -> None:
    """format_diagnostic_message should handle profile=None."""
    context = DiagnosticContext(
        resource_type="test-resource",
        search_paths=["/path/1"],
        profile=None,
        remediation="Test fix",
        ref_issue=456,
    )
    message = format_diagnostic_message("test", context)

    assert "Missing test-resource: test" in message
    assert "Current profile" not in message
    assert "Suggested fix: Test fix" in message
    assert "See issue #456" in message


def test_format_diagnostic_message_handles_none_ref_issue() -> None:
    """format_diagnostic_message should handle ref_issue=None."""
    context = DiagnosticContext(
        resource_type="test-resource",
        search_paths=["/path/1"],
        profile="profile",
        remediation="Test fix",
        ref_issue=None,
    )
    message = format_diagnostic_message("test", context)

    assert "Missing test-resource: test" in message
    assert "Current profile: profile" in message
    assert "Suggested fix: Test fix" in message
    assert "See issue" not in message


def test_format_diagnostic_message_handles_both_none() -> None:
    """format_diagnostic_message should handle both profile and ref_issue being None."""
    context = DiagnosticContext(
        resource_type="test-resource",
        search_paths=["/path/1", "/path/2"],
        profile=None,
        remediation="Test fix",
        ref_issue=None,
    )
    message = format_diagnostic_message("test", context)

    assert "Missing test-resource: test" in message
    assert "Searched paths:" in message
    assert "/path/1" in message
    assert "/path/2" in message
    assert "Current profile" not in message
    assert "Suggested fix: Test fix" in message
    assert "See issue" not in message


def test_format_diagnostic_message_structure() -> None:
    """format_diagnostic_message should have proper structure."""
    context = DiagnosticContext(
        resource_type="config",
        search_paths=["/a", "/b"],
        profile="dev",
        remediation="Fix it",
        ref_issue=1,
    )
    message = format_diagnostic_message("config.yaml", context)
    lines = message.split("\n")

    # First line should be the header
    assert lines[0] == "Missing config: config.yaml"
    # Second line should be empty
    assert lines[1] == ""
    # Third line should start "Searched paths:"
    assert lines[2] == "Searched paths:"
    # Paths should be indented
    assert lines[3].startswith("  - ")
    assert lines[4].startswith("  - ")
