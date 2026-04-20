"""Integration tests for dependency wake-up end-to-end flow.

Tests the complete flow:
1. Flow A depends on Flow B
2. Flow A marked as waiting
3. Flow B creates PR
4. Flow A automatically woken up
"""

from unittest.mock import MagicMock, patch

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.services.pr_service import PRService


class TestDependencyWakeUpIntegration:
    """Integration tests for dependency wake-up mechanism."""

    def test_pr_create_triggers_wake_up_e2e(self) -> None:
        """End-to-end test: PR create → DependencySatisfied event → wake-up."""
        # Register event handlers
        from vibe3.domain import register_event_handlers
        from vibe3.domain.publisher import EventPublisher

        EventPublisher.reset()  # Clean state
        register_event_handlers()

        # Setup: Create two flows (A depends on B)
        # Use unique branch names to avoid data pollution
        import time

        unique_id = int(time.time() * 1000)

        store = SQLiteClient()

        # Flow A (dependent flow)
        branch_a = f"task/issue-300-{unique_id}"
        store.update_flow_state(branch_a, flow_slug=f"flow-a-{unique_id}")
        store.add_issue_link(branch_a, 300, "task")
        store.add_issue_link(branch_a, 301, "dependency")

        # Mark flow A as waiting
        store.update_flow_state(
            branch_a,
            flow_status="waiting",
            blocked_by_issue=301,
            blocked_reason="Waiting for dependencies: [301]",
        )
        store.add_event(
            branch_a,
            "dependency_waiting",
            "orchestra:dispatcher",
            detail="Waiting for dependencies: [301]",
            refs={"dependencies": ["301"]},
        )

        # Flow B (dependency flow)
        branch_b = f"task/issue-301-{unique_id}"
        store.update_flow_state(branch_b, flow_slug=f"flow-b-{unique_id}")
        store.add_issue_link(branch_b, 301, "task")

        # Mock GitHub client
        github_client = MagicMock()
        github_client.check_auth.return_value = True
        github_client.list_prs_for_branch.return_value = []  # No existing PR

        # Mock PR creation response
        pr_response = MagicMock()
        pr_response.number = 42
        pr_response.url = "https://github.com/owner/repo/pull/42"
        pr_response.title = "Test PR"
        pr_response.head_branch = branch_b
        pr_response.base_branch = "main"
        pr_response.draft = True
        github_client.create_pr.return_value = pr_response

        # Mock Git client
        git_client = MagicMock()
        git_client.get_current_branch.return_value = branch_b
        git_client.push_branch.return_value = None
        git_client.fetch.return_value = None  # Mock fetch
        git_client.check_merge_conflicts.return_value = False  # No conflicts

        # Mock dependency satisfaction check (issue 301 is now satisfied)
        with patch(
            "vibe3.domain.handlers.dependency_wake_up._is_issue_satisfied",
            return_value=True,
        ):
            # Create PR service with mocked clients
            pr_service = PRService(
                github_client=github_client,
                git_client=git_client,
                store=store,
            )

            # Execute: Create draft PR for flow B
            pr = pr_service.create_draft_pr(
                title="Implement feature B",
                body="This completes the dependency",
                base_branch="main",
            )

            # Verify: PR was created
            assert pr.number == 42
            assert pr.head_branch == branch_b

            # Verify: Flow A was woken up
            flow_a = store.get_flow_state(branch_a)
            assert flow_a is not None
            assert flow_a.get("flow_status") == "active"
            assert flow_a.get("blocked_by_issue") is None
            assert flow_a.get("blocked_reason") is None

            # Verify: Wake-up event was recorded
            events = store.get_events(branch_a)
            wake_up_events = [
                e for e in events if e.get("event_type") == "dependency_wake_up"
            ]
            assert len(wake_up_events) == 1

            wake_up_event = wake_up_events[0]
            assert wake_up_event.get("actor") == "orchestra:dependency_handler"
            assert wake_up_event.get("refs", {}).get("source_pr") == "42"

    def test_multiple_dependencies_partial_satisfied_no_wake_up_integration(
        self,
    ) -> None:
        """Integration test: Multiple dependencies, partial satisfied, no wake-up."""
        # Setup: Flow A depends on B and C
        store = SQLiteClient()

        branch_a = "task/issue-300"
        store.update_flow_state(branch_a, flow_slug="flow-a")
        store.add_issue_link(branch_a, 300, "task")
        store.add_issue_link(branch_a, 301, "dependency")
        store.add_issue_link(branch_a, 302, "dependency")

        # Mark flow A as waiting
        store.update_flow_state(
            branch_a,
            flow_status="waiting",
            blocked_by_issue=301,
            blocked_reason="Waiting for dependencies: [301, 302]",
        )

        # Flow B (one dependency)
        branch_b = "task/issue-301"
        store.update_flow_state(branch_b, flow_slug="flow-b")
        store.add_issue_link(branch_b, 301, "task")

        # Mock GitHub client
        github_client = MagicMock()
        github_client.check_auth.return_value = True
        github_client.list_prs_for_branch.return_value = []
        pr_response = MagicMock()
        pr_response.number = 42
        pr_response.url = "https://github.com/owner/repo/pull/42"
        pr_response.title = "Test PR"
        pr_response.head_branch = branch_b
        pr_response.base_branch = "main"
        pr_response.draft = True
        github_client.create_pr.return_value = pr_response

        # Mock Git client
        git_client = MagicMock()
        git_client.get_current_branch.return_value = branch_b
        git_client.push_branch.return_value = None
        git_client.fetch.return_value = None  # Mock fetch
        git_client.check_merge_conflicts.return_value = False  # No conflicts

        # Mock dependency satisfaction check
        def mock_satisfied(gh, issue_number):
            # 301 is satisfied (PR created), 302 is not
            return issue_number == 301

        with patch(
            "vibe3.domain.handlers.dependency_wake_up._is_issue_satisfied",
            side_effect=mock_satisfied,
        ):
            pr_service = PRService(
                github_client=github_client,
                git_client=git_client,
                store=store,
            )

            # Execute: Create PR for flow B
            pr = pr_service.create_draft_pr(
                title="Complete dependency B",
                body="This satisfies dependency 301",
            )

            # Verify: PR was created
            assert pr.number == 42

            # Verify: Flow A should still be waiting (302 not satisfied)
            flow_a = store.get_flow_state(branch_a)
            assert flow_a is not None
            assert flow_a.get("flow_status") == "waiting"
            assert (
                flow_a.get("blocked_by_issue") == 301
                or flow_a.get("blocked_by_issue") == 302
            )

    def test_event_handler_registration_integration(self) -> None:
        """Test that dependency wake-up handler is properly registered."""
        from vibe3.domain import register_event_handlers
        from vibe3.domain.publisher import EventPublisher

        # Reset publisher to clean state
        EventPublisher.reset()

        # Register handlers
        register_event_handlers()

        # Get publisher
        publisher = EventPublisher()

        # Verify handler is registered for DependencySatisfied
        assert "DependencySatisfied" in publisher._handlers
        assert len(publisher._handlers["DependencySatisfied"]) == 1

        # Clean up
        EventPublisher.reset()
