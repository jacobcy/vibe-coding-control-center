"""Tests for MissingResourceError and DiagnosticContext."""

from __future__ import annotations

from vibe3.exceptions import MissingResourceError, UserError
from vibe3.exceptions.diagnostic_errors import DiagnosticContext


def test_missing_resource_error_inherits_user_error() -> None:
    """MissingResourceError should inherit from UserError."""
    assert issubclass(MissingResourceError, UserError)


def test_missing_resource_error_is_recoverable() -> None:
    """MissingResourceError should be recoverable."""
    context = DiagnosticContext(
        resource_type="test-resource",
        search_paths=["/path/1", "/path/2"],
        profile="test-profile",
        remediation="Test fix",
        ref_issue=123,
    )
    error = MissingResourceError("test-resource", context)
    assert error.recoverable is True


def test_missing_resource_error_contains_diagnostic_context() -> None:
    """MissingResourceError should contain DiagnosticContext."""
    context = DiagnosticContext(
        resource_type="prompt-recipes",
        search_paths=["/path/to/recipes.yaml"],
        profile="dev",
        remediation="Run install script",
        ref_issue=456,
    )
    error = MissingResourceError("recipes.yaml", context)

    assert error.resource == "recipes.yaml"
    assert error.diagnostic is context
    assert error.diagnostic.resource_type == "prompt-recipes"
    assert error.diagnostic.search_paths == ["/path/to/recipes.yaml"]
    assert error.diagnostic.profile == "dev"
    assert error.diagnostic.remediation == "Run install script"
    assert error.diagnostic.ref_issue == 456


def test_missing_resource_error_message_format() -> None:
    """MissingResourceError message should contain all diagnostic fields."""
    context = DiagnosticContext(
        resource_type="config-file",
        search_paths=["/path/1", "/path/2"],
        profile="test",
        remediation="Create the config file",
        ref_issue=789,
    )
    error = MissingResourceError("config.yaml", context)

    # Check message contains all parts
    assert "Missing config-file: config.yaml" in error.message
    assert "Searched paths:" in error.message
    assert "/path/1" in error.message
    assert "/path/2" in error.message
    assert "Current profile: test" in error.message
    assert "Suggested fix: Create the config file" in error.message
    assert "See issue #789" in error.message


def test_diagnostic_context_with_no_profile() -> None:
    """DiagnosticContext should handle None profile."""
    context = DiagnosticContext(
        resource_type="test-resource",
        search_paths=["/path/1"],
        profile=None,
        remediation="Test fix",
        ref_issue=None,
    )
    error = MissingResourceError("test", context)

    assert "Current profile" not in error.message
    assert "See issue" not in error.message


def test_diagnostic_context_all_fields_present() -> None:
    """DiagnosticContext should pass through all fields."""
    context = DiagnosticContext(
        resource_type="type",
        search_paths=["path"],
        profile="profile",
        remediation="fix",
        ref_issue=123,
    )

    assert context.resource_type == "type"
    assert context.search_paths == ["path"]
    assert context.profile == "profile"
    assert context.remediation == "fix"
    assert context.ref_issue == 123
