"""Tests for check_cleanup_service with live session filtering."""

from unittest.mock import MagicMock, patch

import pytest

from vibe3.clients import SQLiteClient
from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.services.check.cleanup import CheckCleanupService
from vibe3.services.orchestra.cleanup import (
    ExpiredResourceCleanupService,
)


@pytest.fixture
def mock_store():
    """Create a mock SQLiteClient."""
    return MagicMock(spec=SQLiteClient)


@pytest.fixture
def mock_git_client():
    """Create a mock GitClient."""
    client = MagicMock(spec=GitClient)
    client.get_current_branch.return_value = "feature/test-branch"
    client._run.return_value = "/path/to/.git"
    return client


@pytest.fixture
def mock_github_client():
    """Create a mock GitHubClient."""
    client = MagicMock(spec=GitHubClient)
    client.list_all_prs.return_value = []
    return client


@pytest.fixture
def cleanup_service(mock_store, mock_git_client, mock_github_client):
    """Create a CheckCleanupService instance with mocked dependencies."""
    return CheckCleanupService(
        store=mock_store,
        git_client=mock_git_client,
        github_client=mock_github_client,
    )


def test_clean_residual_branches_filters_live_sessions_before_cleanup() -> None:
    """Live session branches should be skipped before cleanup attempts."""
    store = MagicMock()
    git_client = MagicMock()

    # Mock terminal flows
    store.get_all_flows.return_value = [
        {
            "branch": "task/issue-123",
            "flow_status": "aborted",
        },
        {
            "branch": "task/issue-456",
            "flow_status": "done",
        },
        {
            "branch": "task/issue-789",
            "flow_status": "aborted",
        },
    ]

    service = CheckCleanupService(store=store, git_client=git_client)

    # Mock: issue-123 and issue-789 have live sessions
    with patch.object(
        service,
        "_get_branches_with_live_sessions",
        return_value={"task/issue-123", "task/issue-789"},
    ):
        with patch.object(service, "_process_terminal_flow") as mock_process:
            result = service.clean_residual_branches()

            # Verify: only issue-456 was processed (no live session)
            assert mock_process.call_count == 1
            mock_process.assert_called_once()

            # Verify result structure
            assert "skipped_live" in result
            assert set(result["skipped_live"]) == {
                "task/issue-123",
                "task/issue-789",
            }
            assert "task/issue-456" not in result["skipped_live"]


def test_clean_residual_branches_logs_skipped_branches() -> None:
    """Should log which branches were skipped due to live sessions."""
    store = MagicMock()
    git_client = MagicMock()

    store.get_all_flows.return_value = [
        {"branch": "task/issue-123", "flow_status": "aborted"},
        {"branch": "task/issue-456", "flow_status": "aborted"},
    ]

    service = CheckCleanupService(store=store, git_client=git_client)

    with patch("vibe3.environment.session_registry.SessionRegistryService") as registry:
        registry.return_value._store.list_live_runtime_sessions.return_value = [
            {
                "branch": "task/issue-123",
                "tmux_session": "vibe3-run-issue-123",
            },
        ]

        # Mock backend to say issue-123 has live session
        with patch.object(service, "_get_branches_with_live_sessions") as mock_get_live:
            mock_get_live.return_value = {"task/issue-123"}

            with patch.object(service, "_process_terminal_flow"):
                result = service.clean_residual_branches()

                # Verify summary includes skipped count
                assert "skipped 1 branches with live sessions" in str(result["summary"])


def test_get_branches_with_live_sessions_queries_once() -> None:
    """Should query live sessions only once, not per branch."""
    store = MagicMock()
    git_client = MagicMock()
    service = CheckCleanupService(store=store, git_client=git_client)

    with patch(
        "vibe3.environment.session_registry.SessionRegistryService"
    ) as registry_cls:
        registry = registry_cls.return_value
        # Mock the new method
        registry.get_all_branches_with_live_sessions.return_value = {
            "task/issue-123",
            "task/issue-456",
        }

        result = service._get_branches_with_live_sessions()

        # Verify: called once, not per branch
        registry.get_all_branches_with_live_sessions.assert_called_once()

        # Verify: both branches returned
        assert result == {"task/issue-123", "task/issue-456"}


def test_clean_residual_branches_handles_no_live_sessions() -> None:
    """Should work correctly when no live sessions exist."""
    store = MagicMock()
    git_client = MagicMock()

    store.get_all_flows.return_value = [
        {"branch": "task/issue-123", "flow_status": "aborted"},
        {"branch": "task/issue-456", "flow_status": "done"},
    ]

    service = CheckCleanupService(store=store, git_client=git_client)

    # Mock: no live sessions
    with patch.object(service, "_get_branches_with_live_sessions", return_value=set()):
        with patch.object(service, "_process_terminal_flow") as mock_process:
            result = service.clean_residual_branches()

            # All flows should be processed
            assert mock_process.call_count == 2
            assert result["skipped_live"] == []


def test_clean_residual_branches_integrates_all_cleanups() -> None:
    """Should call all cleanup methods when enabled."""
    store = MagicMock()
    git_client = MagicMock()
    service = CheckCleanupService(store=store, git_client=git_client)

    # Mock all dependencies
    store.get_all_flows.return_value = []
    git_client.get_current_branch.return_value = "main"

    with patch.object(
        ExpiredResourceCleanupService, "clean_expired_agent_worktrees"
    ) as mock_agent:
        with patch.object(
            ExpiredResourceCleanupService, "clean_expired_remote_branches"
        ) as mock_remote:
            with patch.object(
                ExpiredResourceCleanupService, "clean_expired_local_branches"
            ) as mock_local:
                mock_agent.return_value = {"cleaned": ["agent-old"]}
                mock_remote.return_value = {"cleaned": ["origin/feature-old"]}
                mock_local.return_value = {"cleaned": ["feature-old"]}

                result = service.clean_residual_branches()

                # Verify all called
                mock_agent.assert_called_once()
                mock_remote.assert_called_once()
                mock_local.assert_called_once()

                # Verify results include all sections
                assert "agent_worktrees" in result
                assert "remote_branches" in result
                assert "local_branches" in result

                # Verify summary includes expired cleanup counts
                summary = str(result["summary"])
                assert "agent_worktrees cleaned 1" in summary
                assert "remote_branches cleaned 1" in summary
                assert "local_branches cleaned 1" in summary


def test_cleanup_detached_worktrees_removes_orphaned_worktrees() -> None:
    """Detached HEAD worktrees inside repo root should be removed during cleanup."""
    store = MagicMock()
    git_client = MagicMock()
    service = CheckCleanupService(store=store, git_client=git_client)

    repo_root = "/repo/main"
    # Both detached worktrees are inside the repo root
    porcelain_output = f"""worktree {repo_root}/.worktrees/wt1
HEAD abc123def456
detached

worktree {repo_root}/.worktrees/wt2
branch refs/heads/feature

worktree {repo_root}/.worktrees/wt3
HEAD def456abc123
detached
"""

    # Mock git client methods
    git_client._run.return_value = porcelain_output
    git_client.get_worktree_root.return_value = repo_root
    store.get_all_flows.return_value = []

    result = service._cleanup_detached_worktrees()

    # Verify: 2 detached worktrees (inside repo) removed
    assert len(result["cleaned"]) == 2
    assert f"{repo_root}/.worktrees/wt1" in result["cleaned"]
    assert f"{repo_root}/.worktrees/wt3" in result["cleaned"]
    assert len(result["failed"]) == 0


def test_cleanup_detached_worktrees_skips_current_cwd() -> None:
    """Never delete current working directory even if it is a detached worktree."""
    import os

    store = MagicMock()
    git_client = MagicMock()
    service = CheckCleanupService(store=store, git_client=git_client)

    current_cwd = os.getcwd()
    # other-wt is inside the same root so it IS eligible for cleanup
    other_wt = current_cwd + "/.worktrees/orphan-wt"

    porcelain_output = f"""worktree {current_cwd}
HEAD abc123def456
detached

worktree {other_wt}
HEAD def456abc123
detached
"""

    # Mock git client methods
    git_client._run.return_value = porcelain_output
    git_client.get_worktree_root.return_value = current_cwd
    store.get_all_flows.return_value = []

    result = service._cleanup_detached_worktrees()

    # Verify: only non-CWD worktree removed
    assert other_wt in result["cleaned"]
    assert current_cwd in result["skipped_self"]
    # Verify: only one remove call (not for CWD)
    remove_calls = [
        c
        for c in git_client._run.call_args_list
        if c[0][0][:2] == ["worktree", "remove"]
    ]
    assert len(remove_calls) == 1


class TestCleanResidualBranches:
    """Tests for clean_residual_branches method in CheckCleanupService."""

    def test_clean_residual_branches_removes_done_flow_branches(
        self, cleanup_service, mock_store, mock_git_client
    ):
        """Should clean physical resources for done flows and soft-delete flow
        record."""
        mock_store.get_all_flows.return_value = [
            {"branch": "feature/done-branch", "flow_status": "done"},
            {"branch": "feature/active-branch", "flow_status": "active"},
        ]
        # Simulate local branch exists for done branch
        mock_git_client._run.return_value = "feature/done-branch"
        mock_git_client.find_worktree_path_for_branch.return_value = None

        result = cleanup_service.clean_residual_branches()

        # Done flow should be in cleaned (both physical resources and record deleted)
        assert "feature/done-branch" in result["cleaned"]
        assert "feature/done-branch" in result["cleaned_done"]
        assert result["total_flows_checked"] == 1

    def test_clean_residual_branches_skips_when_no_resources(
        self, cleanup_service, mock_store, mock_git_client
    ):
        """Should soft-delete done/merged flow records even without physical resources.

        Done/merged flows now soft-delete their records to allow
        clean_expired_local_branches to clean residual branches.
        """
        mock_store.get_all_flows.return_value = [
            {"branch": "feature/done-branch", "flow_status": "done"},
        ]
        # Simulate no resources exist
        mock_git_client._run.return_value = ""
        mock_git_client.find_worktree_path_for_branch.return_value = None

        result = cleanup_service.clean_residual_branches()

        # Done flow record should be soft-deleted (in cleaned list)
        assert len(result["cleaned"]) == 1
        assert "feature/done-branch" in result["cleaned"]
        assert "feature/done-branch" in result["cleaned_done"]
        assert result["total_flows_checked"] == 1

    def test_clean_residual_branches_aborted_deletes_record(
        self, cleanup_service, mock_store, mock_git_client
    ):
        """Should delete aborted flow records to allow issue restart."""
        mock_store.get_all_flows.return_value = [
            {"branch": "feature/aborted-branch", "flow_status": "aborted"},
        ]
        # Simulate no resources exist
        mock_git_client._run.return_value = ""
        mock_git_client.find_worktree_path_for_branch.return_value = None

        result = cleanup_service.clean_residual_branches()

        # Aborted flow record should be deleted (in cleaned)
        assert len(result["cleaned"]) == 1
        assert "feature/aborted-branch" in result["cleaned"]
        assert "feature/aborted-branch" in result["cleaned_aborted"]
        assert result["total_flows_checked"] == 1

    def test_clean_residual_branches_removes_invalid_records(
        self, cleanup_service, mock_store, mock_git_client
    ):
        """Should remove HEAD records from database."""
        mock_store.get_all_flows.return_value = [
            {"branch": "HEAD", "flow_status": "done"},
            {"branch": "HEAD~1", "flow_status": "aborted"},
        ]

        result = cleanup_service.clean_residual_branches()

        assert len(result["removed_invalid"]) == 2
        assert mock_store.delete_flow.call_count == 2

    def test_clean_residual_branches_handles_partial_failures(
        self, cleanup_service, mock_store, mock_git_client
    ):
        """Should continue cleaning even if some fail."""
        mock_store.get_all_flows.return_value = [
            {"branch": "feature/branch-1", "flow_status": "done"},
            {"branch": "feature/branch-2", "flow_status": "done"},
        ]
        # First branch succeeds, second fails
        call_count = [0]

        def mock_run(cmd):
            call_count[0] += 1
            if call_count[0] <= 1:
                return "feature/branch-1"  # First call for branch-1
            elif call_count[0] <= 2:
                raise RuntimeError("git error")  # First call for branch-2 fails
            return ""  # Subsequent calls

        mock_git_client._run.side_effect = mock_run
        mock_git_client.find_worktree_path_for_branch.return_value = None

        result = cleanup_service.clean_residual_branches()

        # Should have some result despite failures
        assert "failed" in result
        assert result["total_flows_checked"] == 2


def test_clean_terminal_flows_resumes_aborted_to_ready() -> None:
    """Aborted flow with --clean-branch should resume issue to READY."""
    store = MagicMock()
    git_client = MagicMock()
    github_client = MagicMock()

    # Mock aborted flow
    store.get_all_flows.return_value = [
        {
            "branch": "task/issue-200",
            "flow_status": "aborted",
            "blocked_reason": "PR #123 closed without merge",
        }
    ]
    # Mock no DB issue link (fallback to branch parsing)
    store.get_task_issue_number.return_value = None

    # Mock issue open
    github_client.view_issue.return_value = {
        "state": "open",
    }

    service = CheckCleanupService(
        store=store,
        git_client=git_client,
        github_client=github_client,
    )

    with patch("vibe3.services.flow.cleanup.FlowCleanupService") as mock_cleanup_cls:
        mock_cleanup = MagicMock()
        mock_cleanup.cleanup_flow_scene.return_value = {
            "flow_record": True,
            "worktree": True,
            "local_branch": True,
        }
        mock_cleanup_cls.return_value = mock_cleanup

        with patch(
            "vibe3.services.check.cleanup.TaskResumeOperations"
        ) as mock_operations_cls:
            mock_operations = MagicMock()
            mock_operations_cls.return_value = mock_operations

            results = service._clean_terminal_flows()

    # Verify TaskResumeOperations.reset_issue_to_ready was called
    mock_operations.reset_issue_to_ready.assert_called_once()
    call_args = mock_operations.reset_issue_to_ready.call_args
    assert call_args.kwargs["issue_number"] == 200
    assert call_args.kwargs["label_state"] == ""

    # Verify cleanup happened
    assert "Cleaned 1 aborted flows" in results["summary"]


def test_resume_blocked_issue_adds_cleanup_comment() -> None:
    """Resume should add comment explaining cleanup and recommendations."""
    store = MagicMock()
    git_client = MagicMock()
    github_client = MagicMock()

    # Mock no DB issue link (fallback to branch parsing)
    store.get_task_issue_number.return_value = None

    service = CheckCleanupService(
        store=store,
        git_client=git_client,
        github_client=github_client,
    )

    github_client.view_issue.return_value = {
        "state": "open",
    }

    with patch("vibe3.services.check.cleanup.TaskResumeOperations"):
        service._resume_blocked_issue("task/issue-300")

    # Verify comment added
    github_client.add_comment.assert_called_once()
    call_args = github_client.add_comment.call_args
    assert call_args[0][0] == 300  # issue_number

    comment_body = call_args[0][1]
    assert "旧 flow 已清理" in comment_body
    assert "follow-up issue" in comment_body.lower()
    assert "不建议" in comment_body


def test_resume_blocked_issue_uses_task_resume_operations() -> None:
    """check --clean-branch restores labels through the same resume operation."""
    from unittest.mock import MagicMock, patch

    from vibe3.services.check.cleanup import CheckCleanupService

    store = MagicMock()
    git = MagicMock()
    github = MagicMock()
    github.view_issue.return_value = {"state": "OPEN"}
    # Mock no DB issue link (fallback to branch parsing)
    store.get_task_issue_number.return_value = None
    service = CheckCleanupService(store=store, git_client=git, github_client=github)

    with patch("vibe3.services.check.cleanup.TaskResumeOperations") as operations_cls:
        operations = MagicMock()
        operations_cls.return_value = operations

        service._resume_blocked_issue("task/issue-300")

        operations.reset_issue_to_ready.assert_called_once()
        call = operations.reset_issue_to_ready.call_args.kwargs
        assert call["issue_number"] == 300
        assert call["label_state"] == ""


def test_check_cleanup_service_accepts_backend_parameter():
    """CheckCleanupService should accept BackendProtocol in constructor."""
    from unittest.mock import MagicMock

    from vibe3.clients.protocols.backend import BackendProtocol

    mock_backend = MagicMock(spec=BackendProtocol)
    mock_store = MagicMock()
    mock_git = MagicMock()

    service = CheckCleanupService(
        store=mock_store,
        git_client=mock_git,
        backend=mock_backend,
    )

    assert service._backend is mock_backend


def test_backend_propagated_to_session_registry():
    """Backend should be passed to SessionRegistryService."""
    from unittest.mock import MagicMock, patch

    from vibe3.clients.protocols.backend import BackendProtocol

    mock_backend = MagicMock(spec=BackendProtocol)
    mock_store = MagicMock()
    mock_git = MagicMock()

    service = CheckCleanupService(
        store=mock_store,
        git_client=mock_git,
        backend=mock_backend,
    )

    with patch(
        "vibe3.environment.session_registry.SessionRegistryService"
    ) as mock_registry_class:
        mock_registry = MagicMock()
        mock_registry_class.return_value = mock_registry
        mock_registry.get_all_branches_with_live_sessions.return_value = set()

        service._get_branches_with_live_sessions()

        mock_registry_class.assert_called_once_with(
            store=mock_store, backend=mock_backend
        )


def test_backend_passed_to_expired_resource_service():
    """Backend should be passed to ExpiredResourceCleanupService."""
    from unittest.mock import MagicMock, patch

    from vibe3.clients.protocols.backend import BackendProtocol

    mock_backend = MagicMock(spec=BackendProtocol)
    service = CheckCleanupService(
        store=MagicMock(),
        git_client=MagicMock(),
        backend=mock_backend,
    )

    with patch(
        "vibe3.services.expired_resource_cleanup_service.ExpiredResourceCleanupService"
    ) as mock_class:
        mock_instance = MagicMock()
        mock_class.return_value = mock_instance
        mock_instance.clean_expired_agent_worktrees.return_value = {"cleaned": []}
        mock_instance.clean_expired_remote_branches.return_value = {"cleaned": []}
        mock_instance.clean_expired_local_branches.return_value = {"cleaned": []}

        # Trigger creation via clean_residual_branches
        with patch.object(
            service, "_clean_terminal_flows", return_value={"summary": ""}
        ):
            with patch("vibe3.config.settings.VibeConfig.get_defaults"):
                service.clean_residual_branches()

                # Verify backend was passed to constructor
                mock_class.assert_called_once()
                call_kwargs = mock_class.call_args.kwargs
                assert call_kwargs.get("backend") is mock_backend


def test_cleanup_detached_worktrees_removes_non_flow_managed() -> None:
    """Detached worktrees not in flow records should also be cleaned (repo-internal)."""
    store = MagicMock()
    git_client = MagicMock()
    service = CheckCleanupService(store=store, git_client=git_client)

    repo_root = "/repo/main"
    # wt-orphan is detached and NOT in any flow record
    porcelain_output = f"""worktree {repo_root}
branch refs/heads/main

worktree {repo_root}/.worktrees/wt-orphan
HEAD abc123def456
detached

"""
    git_client._run.return_value = porcelain_output
    git_client.get_worktree_root.return_value = repo_root
    # No flow records at all
    store.get_all_flows.return_value = []

    result = service._cleanup_detached_worktrees()

    # non-flow-managed detached worktree within repo → should be cleaned
    assert f"{repo_root}/.worktrees/wt-orphan" in result["cleaned"]


def test_cleanup_detached_worktrees_skips_protected_names() -> None:
    """Protected worktree names (wt-claude, codex, etc.) must never be deleted."""
    store = MagicMock()
    git_client = MagicMock()
    service = CheckCleanupService(store=store, git_client=git_client)

    repo_root = "/repo/main"
    porcelain_output = f"""worktree {repo_root}
branch refs/heads/main

worktree {repo_root}/.worktrees/wt-claude
HEAD aaa111bbb222
detached

worktree {repo_root}/.worktrees/wt-codex
HEAD bbb222ccc333
detached

worktree {repo_root}/.worktrees/wt-orphan
HEAD ccc333ddd444
detached

"""
    git_client._run.return_value = porcelain_output
    git_client.get_worktree_root.return_value = repo_root
    store.get_all_flows.return_value = []

    result = service._cleanup_detached_worktrees()

    # Protected names must be skipped
    protected_paths = [
        f"{repo_root}/.worktrees/wt-claude",
        f"{repo_root}/.worktrees/wt-codex",
    ]
    for p in protected_paths:
        assert p not in result["cleaned"], f"{p} should be protected"
    assert "skipped_protected" in result
    assert any("wt-claude" in s for s in result["skipped_protected"])
    assert any("wt-codex" in s for s in result["skipped_protected"])

    # wt-orphan is not protected → cleaned
    assert f"{repo_root}/.worktrees/wt-orphan" in result["cleaned"]
