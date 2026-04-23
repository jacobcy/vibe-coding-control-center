"""Tests for StateLabelDispatchService dependency checking logic."""

import asyncio
from unittest.mock import MagicMock, patch

from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueState
from vibe3.orchestra.services.state_label_dispatch import StateLabelDispatchService
from vibe3.roles.manager import MANAGER_ROLE


class TestDependencyChecking:
    """Tests for dependency checking in dispatcher."""

    def test_issue_without_dependencies_is_ready(self) -> None:
        """Issue without dependencies should be collected as ready."""
        config = OrchestraConfig(manager_usernames=["manager-bot"])
        github = MagicMock()
        github.list_issues.return_value = [
            {
                "number": 300,
                "title": "Issue without dependencies",
                "labels": [{"name": IssueState.READY.to_label()}],
                "assignees": [{"login": "manager-bot"}],
                "state": "open",
            }
        ]

        store = MagicMock()
        store.get_flows_by_issue.return_value = []  # No flows → no dependencies

        service = StateLabelDispatchService(
            config,
            github=github,
            role_def=MANAGER_ROLE,
        )
        service._store = store

        issues = asyncio.run(service.collect_ready_issues())

        assert len(issues) == 1
        assert issues[0].number == 300
        # Should NOT call _mark_issue_waiting
        store.update_flow_state.assert_not_called()
        store.add_event.assert_not_called()

    def test_issue_with_unresolved_dependency_marked_waiting(self) -> None:
        """Issue with unresolved dependency should be marked waiting."""
        config = OrchestraConfig(manager_usernames=["manager-bot"])
        github = MagicMock()
        github.list_issues.return_value = [
            {
                "number": 300,
                "title": "Issue with dependency",
                "labels": [{"name": IssueState.READY.to_label()}],
                "assignees": [{"login": "manager-bot"}],
                "state": "open",
            }
        ]

        # Mock dependency issue as NOT satisfied (open, no PR)
        github.view_issue.return_value = {
            "number": 301,
            "state": "open",
            "labels": [{"name": "state/ready"}],
            "body": "No PR reference",
        }

        store = MagicMock()
        store.get_flows_by_issue.return_value = [{"branch": "task/issue-300"}]

        service = StateLabelDispatchService(
            config,
            github=github,
            role_def=MANAGER_ROLE,
        )
        service._store = store

        # Mock _get_issue_dependencies to return [301]
        with patch.object(service, "_get_issue_dependencies", return_value=[301]):
            issues = asyncio.run(service.collect_ready_issues())

            # Should NOT collect this issue (it's waiting)
            assert len(issues) == 0

            # Should mark as waiting
            store.update_flow_state.assert_called_once()
            call_kwargs = store.update_flow_state.call_args[1]
            assert call_kwargs["flow_status"] == "waiting"
            assert call_kwargs["blocked_by_issue"] == 301
            assert "Waiting for dependencies" in call_kwargs["blocked_reason"]

            # Should add event
            store.add_event.assert_called_once()
            call_args = store.add_event.call_args[0]
            assert call_args[1] == "dependency_waiting"
            assert call_args[2] == "orchestra:dispatcher"

    def test_issue_with_satisfied_dependency_is_ready(self) -> None:
        """Issue with satisfied dependency should be collected as ready."""
        config = OrchestraConfig(manager_usernames=["manager-bot"])
        github = MagicMock()
        github.list_issues.return_value = [
            {
                "number": 300,
                "title": "Issue with satisfied dependency",
                "labels": [{"name": IssueState.READY.to_label()}],
                "assignees": [{"login": "manager-bot"}],
                "state": "open",
            }
        ]

        # Mock dependency issue as satisfied (closed)
        github.view_issue.return_value = {
            "number": 301,
            "state": "closed",
            "labels": [],
            "body": "Completed",
        }

        store = MagicMock()
        store.get_flows_by_issue.return_value = [{"branch": "task/issue-300"}]

        service = StateLabelDispatchService(
            config,
            github=github,
            role_def=MANAGER_ROLE,
        )
        service._store = store

        # Mock _get_issue_dependencies to return [301]
        with patch.object(service, "_get_issue_dependencies", return_value=[301]):
            issues = asyncio.run(service.collect_ready_issues())

            # Should collect this issue (dependency satisfied)
            assert len(issues) == 1
            assert issues[0].number == 300

            # Should NOT mark as waiting
            store.update_flow_state.assert_not_called()

    def test_issue_with_multiple_dependencies_partial_satisfied(self) -> None:
        """Multiple dependencies, partial satisfied: should remain waiting."""
        config = OrchestraConfig(manager_usernames=["manager-bot"])
        github = MagicMock()
        github.list_issues.return_value = [
            {
                "number": 300,
                "title": "Issue with multiple dependencies",
                "labels": [{"name": IssueState.READY.to_label()}],
                "assignees": [{"login": "manager-bot"}],
                "state": "open",
            }
        ]

        store = MagicMock()
        store.get_flows_by_issue.return_value = [{"branch": "task/issue-300"}]

        service = StateLabelDispatchService(
            config,
            github=github,
            role_def=MANAGER_ROLE,
        )
        service._store = store

        # Mock _get_issue_dependencies to return [301, 302]
        with patch.object(service, "_get_issue_dependencies", return_value=[301, 302]):
            # Mock view_issue for both dependencies
            def mock_view_issue(issue_number, repo=None):
                if issue_number == 301:
                    return {
                        "number": 301,
                        "state": "closed",  # Satisfied
                        "labels": [],
                        "body": "Completed",
                    }
                elif issue_number == 302:
                    return {
                        "number": 302,
                        "state": "open",  # Not satisfied
                        "labels": [{"name": "state/ready"}],
                        "body": "No PR reference",
                    }
                return None

            github.view_issue.side_effect = mock_view_issue

            issues = asyncio.run(service.collect_ready_issues())

            # Should NOT collect (one dependency unsatisfied)
            assert len(issues) == 0

            # Should mark as waiting
            store.update_flow_state.assert_called_once()
            call_kwargs = store.update_flow_state.call_args[1]
            assert call_kwargs["flow_status"] == "waiting"
            # Primary dependency should be first unresolved
            assert call_kwargs["blocked_by_issue"] == 302

    def test_issue_with_multiple_dependencies_all_satisfied(self) -> None:
        """Issue with multiple dependencies (all satisfied) should be ready."""
        config = OrchestraConfig(manager_usernames=["manager-bot"])
        github = MagicMock()
        github.list_issues.return_value = [
            {
                "number": 300,
                "title": "Issue with multiple satisfied dependencies",
                "labels": [{"name": IssueState.READY.to_label()}],
                "assignees": [{"login": "manager-bot"}],
                "state": "open",
            }
        ]

        store = MagicMock()
        store.get_flows_by_issue.return_value = [{"branch": "task/issue-300"}]

        service = StateLabelDispatchService(
            config,
            github=github,
            role_def=MANAGER_ROLE,
        )
        service._store = store

        # Mock _get_issue_dependencies to return [301, 302]
        with patch.object(service, "_get_issue_dependencies", return_value=[301, 302]):
            # Mock both dependencies as satisfied
            def mock_view_issue(issue_number, repo=None):
                return {
                    "number": issue_number,
                    "state": "closed",
                    "labels": [],
                    "body": "Completed",
                }

            github.view_issue.side_effect = mock_view_issue

            issues = asyncio.run(service.collect_ready_issues())

            # Should collect (all dependencies satisfied)
            assert len(issues) == 1
            assert issues[0].number == 300

            # Should NOT mark as waiting
            store.update_flow_state.assert_not_called()


class TestDependencySatisfactionCheck:
    """Tests for _is_dependency_satisfied helper."""

    def test_closed_issue_satisfies_dependency(self) -> None:
        """Closed issue should be considered satisfied."""
        config = OrchestraConfig()
        github = MagicMock()
        github.view_issue.return_value = {
            "number": 301,
            "state": "closed",
            "labels": [],
            "body": "Completed",
        }

        service = StateLabelDispatchService(
            config,
            github=github,
            role_def=MANAGER_ROLE,
        )

        result = service._is_dependency_satisfied(301)
        assert result is True

    def test_issue_with_state_done_label_satisfies(self) -> None:
        """Issue with state/done label should be considered satisfied."""
        config = OrchestraConfig()
        github = MagicMock()
        github.view_issue.return_value = {
            "number": 301,
            "state": "open",
            "labels": [{"name": "state/done"}],
            "body": "No PR reference in body",
        }

        service = StateLabelDispatchService(
            config,
            github=github,
            role_def=MANAGER_ROLE,
        )

        result = service._is_dependency_satisfied(301)
        assert result is True

    def test_issue_with_state_merged_label_satisfies(self) -> None:
        """Issue with state/merged label should be considered satisfied."""
        config = OrchestraConfig()
        github = MagicMock()
        github.view_issue.return_value = {
            "number": 301,
            "state": "open",
            "labels": [{"name": "state/merged"}],
            "body": "No PR reference in body",
        }

        service = StateLabelDispatchService(
            config,
            github=github,
            role_def=MANAGER_ROLE,
        )

        result = service._is_dependency_satisfied(301)
        assert result is True

    def test_issue_with_pr_mention_in_body_satisfies(self) -> None:
        """Issue mentioning PR in body should be considered satisfied."""
        config = OrchestraConfig()
        github = MagicMock()
        github.view_issue.return_value = {
            "number": 301,
            "state": "open",
            "labels": [],
            "body": "This is completed in pull request #42",
        }

        service = StateLabelDispatchService(
            config,
            github=github,
            role_def=MANAGER_ROLE,
        )

        result = service._is_dependency_satisfied(301)
        assert result is True

    def test_open_issue_without_pr_does_not_satisfy(self) -> None:
        """Open issue without PR reference should NOT be considered satisfied."""
        config = OrchestraConfig()
        github = MagicMock()
        github.view_issue.return_value = {
            "number": 301,
            "state": "open",
            "labels": [{"name": "state/ready"}],
            "body": "Still in progress",
        }

        mock_store = MagicMock()
        mock_store.get_flows_by_issue.return_value = []

        service = StateLabelDispatchService(
            config,
            github=github,
            role_def=MANAGER_ROLE,
        )
        service._store = mock_store

        result = service._is_dependency_satisfied(301)
        assert result is False
