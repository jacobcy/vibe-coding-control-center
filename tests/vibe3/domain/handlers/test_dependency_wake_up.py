"""Unit tests for dependency wake-up handler."""

from unittest.mock import MagicMock, patch

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.domain.events.flow_lifecycle import DependencySatisfied
from vibe3.domain.handlers.dependency_wake_up import (
    _find_waiting_flows,
    _get_all_dependencies,
    _is_issue_satisfied,
    _wake_up_flow,
    handle_dependency_satisfied,
)


class TestHandleDependencySatisfied:
    """Tests for handle_dependency_satisfied handler."""

    def test_single_dependency_wake_up(self) -> None:
        """Flow waiting on single dependency should wake up when satisfied."""
        event = DependencySatisfied(
            issue_number=301,
            branch="task/issue-301",
            pr_number=42,
        )

        # Mock store with waiting flow
        store = SQLiteClient()
        store.update_flow_state(
            "task/issue-300",
            flow_slug="test-300",
            flow_status="waiting",
            blocked_by_issue=301,
            blocked_reason="Waiting for dependencies: [301]",
        )

        with patch(
            "vibe3.domain.handlers.dependency_wake_up.SQLiteClient",
            return_value=store,
        ):
            with patch(
                "vibe3.domain.handlers.dependency_wake_up._find_waiting_flows"
            ) as mock_find:
                with patch(
                    "vibe3.domain.handlers.dependency_wake_up._wake_up_flow"
                ) as mock_wake:
                    mock_find.return_value = [
                        {
                            "branch": "task/issue-300",
                            "blocked_by_issue": 301,
                        }
                    ]

                    # Mock all dependencies satisfied
                    with patch(
                        "vibe3.domain.handlers.dependency_wake_up._get_all_dependencies",
                        return_value=[301],
                    ):
                        with patch(
                            "vibe3.domain.handlers.dependency_wake_up._is_issue_satisfied",
                            return_value=True,
                        ):
                            handle_dependency_satisfied(event)

                            # Should wake up the flow
                            mock_wake.assert_called_once()

    def test_multiple_dependencies_partial_satisfied_no_wake_up(self) -> None:
        """Flow with multiple dependencies (partial satisfied) should NOT wake up."""
        event = DependencySatisfied(
            issue_number=301,
            branch="task/issue-301",
            pr_number=42,
        )

        store = SQLiteClient()

        with patch(
            "vibe3.domain.handlers.dependency_wake_up.SQLiteClient",
            return_value=store,
        ):
            with patch(
                "vibe3.domain.handlers.dependency_wake_up._find_waiting_flows"
            ) as mock_find:
                with patch(
                    "vibe3.domain.handlers.dependency_wake_up._wake_up_flow"
                ) as mock_wake:
                    mock_find.return_value = [
                        {
                            "branch": "task/issue-300",
                            "blocked_by_issue": 301,
                        }
                    ]

                    # Mock multiple dependencies (301 satisfied, 302 not)
                    with patch(
                        "vibe3.domain.handlers.dependency_wake_up._get_all_dependencies",
                        return_value=[301, 302],
                    ):
                        with patch(
                            "vibe3.domain.handlers.dependency_wake_up._is_issue_satisfied"
                        ) as mock_satisfied:
                            # 301 satisfied, 302 not
                            mock_satisfied.side_effect = lambda gh, issue: issue == 301

                            handle_dependency_satisfied(event)

                            # Should NOT wake up (one dependency unsatisfied)
                            mock_wake.assert_not_called()

    def test_multiple_dependencies_all_satisfied_wake_up(self) -> None:
        """Flow with multiple dependencies (all satisfied) should wake up."""
        event = DependencySatisfied(
            issue_number=301,
            branch="task/issue-301",
            pr_number=42,
        )

        store = SQLiteClient()

        with patch(
            "vibe3.domain.handlers.dependency_wake_up.SQLiteClient",
            return_value=store,
        ):
            with patch(
                "vibe3.domain.handlers.dependency_wake_up._find_waiting_flows"
            ) as mock_find:
                with patch(
                    "vibe3.domain.handlers.dependency_wake_up._wake_up_flow"
                ) as mock_wake:
                    mock_find.return_value = [
                        {
                            "branch": "task/issue-300",
                            "blocked_by_issue": 301,
                        }
                    ]

                    # Mock all dependencies satisfied
                    with patch(
                        "vibe3.domain.handlers.dependency_wake_up._get_all_dependencies",
                        return_value=[301, 302],
                    ):
                        with patch(
                            "vibe3.domain.handlers.dependency_wake_up._is_issue_satisfied",
                            return_value=True,
                        ):
                            handle_dependency_satisfied(event)

                            # Should wake up (all dependencies satisfied)
                            mock_wake.assert_called_once()


class TestFindWaitingFlows:
    """Tests for _find_waiting_flows helper."""

    def test_find_flows_blocked_by_issue(self) -> None:
        """Should find flows blocked by specific issue."""
        store = SQLiteClient()

        # Create waiting flows
        store.update_flow_state(
            "task/issue-300",
            flow_slug="test-300",
            flow_status="waiting",
            blocked_by_issue=301,
        )
        store.update_flow_state(
            "task/issue-302",
            flow_slug="test-302",
            flow_status="waiting",
            blocked_by_issue=303,
        )

        # Find flows blocked by 301
        flows = _find_waiting_flows(store, 301)

        assert len(flows) == 1
        assert flows[0]["branch"] == "task/issue-300"
        assert flows[0]["blocked_by_issue"] == 301

    def test_no_waiting_flows(self) -> None:
        """Should return empty list if no waiting flows."""
        store = SQLiteClient()

        flows = _find_waiting_flows(store, 999)

        assert len(flows) == 0


class TestGetAllDependencies:
    """Tests for _get_all_dependencies helper."""

    def test_get_dependencies_for_branch(self) -> None:
        """Should get all dependency issue numbers for branch."""
        store = SQLiteClient()

        # Create flow and dependencies
        branch = "task/issue-300"
        store.update_flow_state(branch, flow_slug="test-300")
        store.add_issue_link(branch, 300, "task")
        store.add_issue_link(branch, 301, "dependency")
        store.add_issue_link(branch, 302, "dependency")

        deps = _get_all_dependencies(store, branch)

        assert len(deps) == 2
        assert 301 in deps
        assert 302 in deps

    def test_no_dependencies(self) -> None:
        """Should return empty list if no dependencies."""
        store = SQLiteClient()

        # Use unique branch name to avoid data pollution
        branch = "task/issue-unique-no-deps-999"
        store.update_flow_state(branch, flow_slug="test-unique-999")
        store.add_issue_link(branch, 999, "task")

        deps = _get_all_dependencies(store, branch)

        assert len(deps) == 0


class TestIsIssueSatisfied:
    """Tests for _is_issue_satisfied helper."""

    def test_closed_issue_satisfies(self) -> None:
        """Closed issue should be considered satisfied."""
        gh = MagicMock()
        gh.view_issue.return_value = {
            "number": 301,
            "state": "closed",
            "labels": [],
            "body": "Completed",
        }

        result = _is_issue_satisfied(gh, 301)
        assert result is True

    def test_state_done_label_satisfies(self) -> None:
        """Issue with state/done label should be satisfied."""
        gh = MagicMock()
        gh.view_issue.return_value = {
            "number": 301,
            "state": "open",
            "labels": [{"name": "state/done"}],
            "body": "Completed",
        }

        result = _is_issue_satisfied(gh, 301)
        assert result is True

    def test_state_merged_label_satisfies(self) -> None:
        """Issue with state/merged label should be satisfied."""
        gh = MagicMock()
        gh.view_issue.return_value = {
            "number": 301,
            "state": "open",
            "labels": [{"name": "state/merged"}],
            "body": "Merged",
        }

        result = _is_issue_satisfied(gh, 301)
        assert result is True

    def test_pr_mention_in_body_satisfies(self) -> None:
        """Issue mentioning PR in body should be satisfied."""
        gh = MagicMock()
        gh.view_issue.return_value = {
            "number": 301,
            "state": "open",
            "labels": [],
            "body": "Fixed in pull request #42",
        }

        result = _is_issue_satisfied(gh, 301)
        assert result is True

    def test_open_issue_without_pr_not_satisfied(self) -> None:
        """Open issue without PR should NOT be satisfied."""
        gh = MagicMock()
        gh.view_issue.return_value = {
            "number": 301,
            "state": "open",
            "labels": [{"name": "state/ready"}],
            "body": "In progress",
        }

        result = _is_issue_satisfied(gh, 301)
        assert result is False


class TestWakeUpFlow:
    """Tests for _wake_up_flow helper."""

    def test_wake_up_updates_flow_state(self) -> None:
        """Wake up should update flow_status to active."""
        store = SQLiteClient()
        gh = MagicMock()

        branch = "task/issue-300"
        store.update_flow_state(
            branch,
            flow_slug="test-300",
            flow_status="waiting",
            blocked_by_issue=301,
            blocked_reason="Waiting for dependencies",
        )
        store.add_issue_link(branch, 300, "task")

        _wake_up_flow(store, gh, branch, source_pr_number=42)

        # Check flow state updated
        flow = store.get_flow_state(branch)
        assert flow is not None
        assert flow.get("flow_status") == "active"
        assert flow.get("blocked_by_issue") is None
        assert flow.get("blocked_reason") is None

        # Check event recorded
        events = store.get_events(branch)
        assert any(e.get("event_type") == "dependency_wake_up" for e in events)

    def test_wake_up_updates_github_labels(self) -> None:
        """Wake up should update GitHub labels (remove blocked, add ready)."""
        store = SQLiteClient()
        gh = MagicMock()

        branch = "task/issue-300"
        store.update_flow_state(branch, flow_slug="test-300")
        store.add_issue_link(branch, 300, "task")

        with patch(
            "vibe3.domain.handlers.dependency_wake_up.GhIssueLabelPort"
        ) as mock_label_port:
            mock_port = MagicMock()
            mock_label_port.return_value = mock_port

            _wake_up_flow(store, gh, branch, source_pr_number=42)

            # Should remove state/blocked and add state/ready
            mock_port.remove_issue_label.assert_called_once_with(300, "state/blocked")
            mock_port.add_issue_label.assert_called_once_with(300, "state/ready")
