"""Unit tests for IssueFlowService."""

import tempfile
from pathlib import Path
from unittest.mock import Mock

from vibe3.config.profile_convention import ProfileConvention
from vibe3.models.branch_convention import BranchConvention
from vibe3.services.issue.flow import IssueFlowService


class TestIssueFlowServiceConventionInjection:
    """Tests for ConventionResolver injection."""

    def test_service_uses_convention_for_canonical_branch(self) -> None:
        """Should use injected convention for branch generation."""
        convention = ProfileConvention(
            branch=BranchConvention(task_prefix="feature/", dev_prefix="dev/")
        )
        mock_resolver = Mock()
        mock_resolver.resolve.return_value = convention

        service = IssueFlowService(resolver=mock_resolver)
        assert service.canonical_branch_name(123) == "feature/123"

    def test_service_uses_convention_for_parsing(self) -> None:
        """Should use injected convention for parsing."""
        convention = ProfileConvention(
            branch=BranchConvention(task_prefix="task/", dev_prefix="dev/")
        )
        mock_resolver = Mock()
        mock_resolver.resolve.return_value = convention

        service = IssueFlowService(resolver=mock_resolver)
        assert service.parse_issue_number_any("task/456") == 456
        assert service.parse_issue_number_any("dev/789") == 789

    def test_service_uses_convention_for_is_task_branch(self) -> None:
        """Should use convention for task branch detection."""
        convention = ProfileConvention(
            branch=BranchConvention(task_prefix="feature/", dev_prefix="dev/")
        )
        mock_resolver = Mock()
        mock_resolver.resolve.return_value = convention

        service = IssueFlowService(resolver=mock_resolver)
        # With task_prefix="feature/", only feature/ branches are task branches
        assert service.is_task_branch("feature/123") is True
        assert service.is_task_branch("feature/123-extra") is True
        assert service.is_task_branch("dev/456") is False

    def test_service_uses_convention_for_is_issue_branch(self) -> None:
        """Should use convention for issue branch detection."""
        convention = ProfileConvention(
            branch=BranchConvention(task_prefix="task/", dev_prefix="dev/")
        )
        mock_resolver = Mock()
        mock_resolver.resolve.return_value = convention

        service = IssueFlowService(resolver=mock_resolver)
        # Both task/ and dev/ match the convention pattern
        assert service.is_issue_branch("task/123") is True
        assert service.is_issue_branch("dev/456") is True
        # Other branches don't match
        assert service.is_issue_branch("feature/test") is False


class TestIssueFlowServiceBranchNaming:
    """Tests for branch name generation and parsing."""

    def test_parse_issue_number_returns_none_for_non_canonical(self) -> None:
        """Should return None for non-canonical branches."""
        service = IssueFlowService()

        # Non-task branches
        assert service.parse_issue_number("dev/feature-123") is None
        assert service.parse_issue_number("main") is None
        assert service.parse_issue_number("release/v1.0") is None

        # Task branches with suffixes (non-canonical)
        assert service.parse_issue_number("task/issue-372-worktree") is None
        assert service.parse_issue_number("task/issue-372-v2") is None

        # Malformed task branches
        assert service.parse_issue_number("task/issue-") is None
        assert service.parse_issue_number("task/issue-abc") is None

    def test_is_task_branch_detects_task_prefix(self) -> None:
        """Should detect branches starting with task/issue-."""
        service = IssueFlowService()

        # Canonical and non-canonical task branches
        assert service.is_task_branch("task/issue-372") is True
        assert service.is_task_branch("task/issue-372-worktree") is True
        assert service.is_task_branch("task/issue-1-v2") is True

        # Non-task branches
        assert service.is_task_branch("dev/feature") is False
        assert service.is_task_branch("main") is False
        assert service.is_task_branch("release/v1.0") is False

    def test_is_canonical_task_branch_matches_correctly(self) -> None:
        """Should match canonical branch against issue number."""
        service = IssueFlowService()

        # Matching issue number
        assert service.is_canonical_task_branch("task/issue-372", 372) is True
        assert service.is_canonical_task_branch("task/issue-1", 1) is True

        # Non-matching issue number
        assert service.is_canonical_task_branch("task/issue-372", 999) is False
        assert service.is_canonical_task_branch("task/issue-372", None) is False

        # Non-canonical branch (with suffix)
        assert service.is_canonical_task_branch("task/issue-372-worktree", 372) is False


class TestIssueFlowServiceFlowLookup:
    """Tests for issue-to-flow mapping."""

    def test_store_get_flows_by_issue_orders_active_canonical_first(self) -> None:
        """Should return active canonical flow before older done debug flows."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from vibe3.clients.sqlite_client import SQLiteClient

            db_path = Path(tmpdir) / "test.db"
            store = SQLiteClient(db_path=str(db_path))

            debug_branch = "debug/vibe-server-fix"
            canonical_branch = "task/issue-467"

            store.update_flow_state(
                debug_branch,
                flow_slug="debug-vibe-server-fix",
                flow_status="done",
                updated_at="2026-04-17T11:17:54.494008",
            )
            store.update_flow_state(
                canonical_branch,
                flow_slug="issue-467",
                flow_status="active",
                updated_at="2026-04-23T05:49:26.084364",
            )

            store.add_issue_link(debug_branch, 467, "task")
            store.add_issue_link(canonical_branch, 467, "task")

            flows = store.get_flows_by_issue(467, role="task")

            assert [flow["branch"] for flow in flows] == [
                canonical_branch,
                debug_branch,
            ]

    def test_find_active_flow_prefers_canonical(self) -> None:
        """Should prioritize active canonical flow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from vibe3.clients.sqlite_client import SQLiteClient

            db_path = Path(tmpdir) / "test.db"
            store = SQLiteClient(db_path=str(db_path))
            service = IssueFlowService(store=store)

            # Create canonical flow
            canonical_branch = "task/issue-372"
            store.update_flow_state(
                canonical_branch,
                flow_slug="issue-372",
                flow_status="active",
            )

            # Create non-canonical flow
            non_canonical_branch = "task/issue-372-worktree"
            store.update_flow_state(
                non_canonical_branch,
                flow_slug="issue-372-v2",
                flow_status="active",
            )

            # Link both to same issue
            store.add_issue_link(canonical_branch, 372, "task")
            store.add_issue_link(non_canonical_branch, 372, "task")

            # Should return canonical
            result = service.find_active_flow(372)
            assert result is not None
            assert result["branch"] == canonical_branch

    def test_find_active_flow_falls_back_to_non_canonical(self) -> None:
        """Should return non-canonical active flow if canonical not active."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from vibe3.clients.sqlite_client import SQLiteClient

            db_path = Path(tmpdir) / "test.db"
            store = SQLiteClient(db_path=str(db_path))
            service = IssueFlowService(store=store)

            # Create canonical flow (inactive)
            canonical_branch = "task/issue-372"
            store.update_flow_state(
                canonical_branch,
                flow_slug="issue-372",
                flow_status="done",
            )

            # Create non-canonical flow (active)
            non_canonical_branch = "task/issue-372-worktree"
            store.update_flow_state(
                non_canonical_branch,
                flow_slug="issue-372-v2",
                flow_status="active",
            )

            # Link both to same issue
            store.add_issue_link(canonical_branch, 372, "task")
            store.add_issue_link(non_canonical_branch, 372, "task")

            # Should return non-canonical active
            result = service.find_active_flow(372)
            assert result is not None
            assert result["branch"] == non_canonical_branch

    def test_find_active_flow_returns_none_if_no_flows(self) -> None:
        """Should return None if no flows linked to issue."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from vibe3.clients.sqlite_client import SQLiteClient

            db_path = Path(tmpdir) / "test.db"
            store = SQLiteClient(db_path=str(db_path))
            service = IssueFlowService(store=store)

            result = service.find_active_flow(999)
            assert result is None

    def test_find_active_flow_falls_back_to_first_available(self) -> None:
        """Should return first flow if no active flows."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from vibe3.clients.sqlite_client import SQLiteClient

            db_path = Path(tmpdir) / "test.db"
            store = SQLiteClient(db_path=str(db_path))
            service = IssueFlowService(store=store)

            # Create only inactive flows
            branch1 = "task/issue-372"
            store.update_flow_state(branch1, flow_slug="issue-372", flow_status="done")

            branch2 = "task/issue-372-v2"
            store.update_flow_state(
                branch2, flow_slug="issue-372-v2", flow_status="aborted"
            )

            # Link both to issue
            store.add_issue_link(branch1, 372, "task")
            store.add_issue_link(branch2, 372, "task")

            # Should return first flow (fallback)
            result = service.find_active_flow(372)
            assert result is not None
            # First flow in list (order may vary)
            assert result["branch"] in [branch1, branch2]


class TestIssueFlowServiceResolveTaskIssueNumber:
    """Tests for unified task issue number resolution."""

    def test_resolve_task_issue_number_from_db_links(self) -> None:
        """Should resolve issue number from DB links when available."""
        store = Mock()
        store.get_task_issue_number = Mock(return_value=123)

        service = IssueFlowService(store=store)

        result = service.resolve_task_issue_number("task/issue-456")
        assert result == 123
        store.get_task_issue_number.assert_called_once_with("task/issue-456")

    def test_resolve_task_issue_number_fallback_to_parsing(self) -> None:
        """Should fallback to branch parsing when DB links unavailable."""
        store = Mock()
        store.get_task_issue_number = Mock(return_value=None)

        service = IssueFlowService(store=store)

        result = service.resolve_task_issue_number("task/issue-789")
        assert result == 789
        store.get_task_issue_number.assert_called_once_with("task/issue-789")

    def test_resolve_task_issue_number_returns_none(self) -> None:
        """Should return None when neither DB nor parsing finds issue."""
        store = Mock()
        store.get_task_issue_number = Mock(return_value=None)

        service = IssueFlowService(store=store)

        result = service.resolve_task_issue_number("feature/my-branch")
        assert result is None
