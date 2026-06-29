"""Unit tests for DependencyResolutionService."""

from unittest.mock import MagicMock, patch

import pytest

from vibe3.services.shared.dependency_resolution import (
    DependencyResolution,
    DependencyResolutionService,
)


class TestDependencyResolutionService:
    """Tests for centralized dependency resolution."""

    def test_resolved_when_issue_closed(self) -> None:
        """Dependency is resolved when GitHub issue state is CLOSED."""
        github_client = MagicMock()
        github_client.view_issue.return_value = {
            "state": "CLOSED",
        }

        resolution = DependencyResolutionService.is_dependency_resolved(
            123, github_client=github_client, repo=None
        )

        assert resolution.resolved is True
        assert resolution.issue_number == 123
        assert resolution.github_state == "CLOSED"

    def test_not_resolved_when_issue_open_no_pr(self) -> None:
        """Dependency is not resolved when issue is OPEN without merged PR."""
        github_client = MagicMock()
        github_client.view_issue.return_value = {
            "state": "OPEN",
            "labels": [],
        }

        with patch(
            "vibe3.clients.pr_status_checker.get_merged_pr_for_issue",
            return_value=None,
        ):
            resolution = DependencyResolutionService.is_dependency_resolved(
                123,
                github_client=github_client,
                repo=None,
            )

        assert resolution.resolved is False
        assert resolution.issue_number == 123
        assert resolution.github_state == "OPEN"

    def test_not_resolved_when_issue_open_with_merged_pr(self) -> None:
        """OPEN issue not resolved even with merged PR (CLOSED-only)."""
        github_client = MagicMock()
        github_client.view_issue.return_value = {
            "state": "OPEN",
        }

        # Merged PR no longer confers resolved status — only CLOSED does
        result = DependencyResolutionService.is_dependency_resolved(
            123,
            github_client=github_client,
            repo=None,
        )

        assert result.resolved is False
        assert result.issue_number == 123
        assert result.github_state == "OPEN"

    def test_not_resolved_when_network_error(self) -> None:
        """Dependency is not resolved when GitHub API returns network_error."""
        github_client = MagicMock()
        github_client.view_issue.return_value = "network_error"

        resolution = DependencyResolutionService.is_dependency_resolved(
            123, github_client=github_client, repo=None
        )

        assert resolution.resolved is False
        assert resolution.issue_number == 123
        assert resolution.github_state is None

    def test_not_resolved_when_issue_not_found(self) -> None:
        """Dependency is not resolved when issue is not found (None)."""
        github_client = MagicMock()
        github_client.view_issue.return_value = None

        resolution = DependencyResolutionService.is_dependency_resolved(
            123, github_client=github_client, repo=None
        )

        assert resolution.resolved is False
        assert resolution.issue_number == 123
        assert resolution.github_state is None

    def test_not_resolved_when_view_issue_unexpected_result(self) -> None:
        """Dependency is not resolved when view_issue returns unexpected type."""
        github_client = MagicMock()
        github_client.view_issue.return_value = "unexpected_string"

        resolution = DependencyResolutionService.is_dependency_resolved(
            123, github_client=github_client, repo=None
        )

        assert resolution.resolved is False
        assert resolution.issue_number == 123
        assert resolution.github_state is None

    def test_not_resolved_when_merged_pr_check_fails(self) -> None:
        """Dependency is not resolved when merged PR check raises exception."""
        github_client = MagicMock()
        github_client.view_issue.return_value = {
            "state": "OPEN",
            "labels": [],
        }

        with patch(
            "vibe3.clients.pr_status_checker.get_merged_pr_for_issue",
            side_effect=RuntimeError("API error"),
        ):
            resolution = DependencyResolutionService.is_dependency_resolved(
                123,
                github_client=github_client,
                repo=None,
            )

        assert resolution.resolved is False
        assert resolution.issue_number == 123
        assert resolution.github_state == "OPEN"


class TestDependencyResolution:
    """Tests for DependencyResolution dataclass."""

    def test_dataclass_is_frozen(self) -> None:
        """DependencyResolution is immutable (frozen)."""
        resolution = DependencyResolution(
            resolved=True,
            issue_number=123,
            github_state="CLOSED",
        )
        with pytest.raises(AttributeError):
            resolution.resolved = False  # type: ignore[misc]

    def test_defaults_applied(self) -> None:
        """Optional fields have correct defaults."""
        resolution = DependencyResolution(
            resolved=False,
            issue_number=123,
        )
        assert resolution.github_state is None


def test_open_issue_with_merged_pr_is_not_resolved():
    """OPEN issue with merged PR must remain unresolved (CLOSED-only)."""
    github_client = MagicMock()
    github_client.view_issue.return_value = {
        "state": "OPEN",
    }

    with patch(
        "vibe3.clients.pr_status_checker.get_merged_pr_for_issue",
        return_value={"number": 999, "state": "MERGED", "title": "merged PR"},
    ):
        result = DependencyResolutionService.is_dependency_resolved(
            100, github_client=github_client
        )

    assert (
        result.resolved is False
    ), f"OPEN+merged PR must NOT resolve. Got: resolved={result.resolved}"
