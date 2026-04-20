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

    def test_find_flows_with_dependency_link(self) -> None:
        """Should find waiting flows that have a dependency link to the issue."""
        import time

        uid = int(time.time() * 1000)
        store = SQLiteClient()

        # Create waiting flows with unique branch names
        branch_a = f"task/issue-wait-a-{uid}"
        branch_b = f"task/issue-wait-b-{uid}"

        store.update_flow_state(
            branch_a,
            flow_slug=f"test-wait-a-{uid}",
            flow_status="waiting",
            blocked_by_issue=301,
        )
        store.add_issue_link(branch_a, 300 + uid, "task")
        store.add_issue_link(branch_a, 301, "dependency")

        store.update_flow_state(
            branch_b,
            flow_slug=f"test-wait-b-{uid}",
            flow_status="waiting",
            blocked_by_issue=303,
        )
        store.add_issue_link(branch_b, 301 + uid, "task")
        store.add_issue_link(branch_b, 303, "dependency")

        # Find flows that depend on issue 301
        flows = _find_waiting_flows(store, 301)

        branch_names = [f["branch"] for f in flows]
        assert branch_a in branch_names
        assert branch_b not in branch_names

    def test_no_dependency_link_excludes_flow(self) -> None:
        """Waiting flow WITHOUT dependency link to the issue should NOT be found."""
        import time

        uid = int(time.time() * 1000)
        store = SQLiteClient()

        branch_a = f"task/issue-nolink-a-{uid}"
        branch_b = f"task/issue-nolink-b-{uid}"

        # Flow A: has dependency link to 301 → should be found
        store.update_flow_state(
            branch_a,
            flow_slug=f"test-nolink-a-{uid}",
            flow_status="waiting",
        )
        store.add_issue_link(branch_a, 400 + uid, "task")
        store.add_issue_link(branch_a, 301, "dependency")

        # Flow B: NO dependency link to 301 → should NOT be found
        store.update_flow_state(
            branch_b,
            flow_slug=f"test-nolink-b-{uid}",
            flow_status="waiting",
        )
        store.add_issue_link(branch_b, 401 + uid, "task")
        # No dependency link to 301 for branch_b

        flows = _find_waiting_flows(store, 301)

        branch_names = [f["branch"] for f in flows]
        assert branch_a in branch_names
        assert branch_b not in branch_names

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

        with patch(
            "vibe3.domain.handlers.dependency_wake_up.SQLiteClient"
        ) as mock_store_cls:
            mock_store = MagicMock()
            mock_store.get_flows_by_issue.return_value = []
            mock_store_cls.return_value = mock_store

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
