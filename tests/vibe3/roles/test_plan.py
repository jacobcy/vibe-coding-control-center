"""Tests for planner role completion scenarios.

钉死 planner 的关键行为：
1. blocked issue 不应该被派发
2. blocked → handoff 转换应该被阻止

Note: 执行报错/无行动等场景的 fail/block 调用已在 test_issue_failure_service.py 中测试。
"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from vibe3.roles.plan import resolve_spec_plan_input


class TestPlannerNoOpGate:
    """Planner no-op gate: state 未变 → blocked"""

    def test_planner_blocked_when_state_unchanged(
        self,
    ) -> None:
        """Planner state/claimed 未变 → blocked"""
        from unittest.mock import MagicMock, patch

        from vibe3.execution.noop_gate import apply_unified_noop_gate

        mock_store = MagicMock()

        with (
            patch("vibe3.clients.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.role_policy_helpers.block_planner_noop_issue"
            ) as mock_block,
        ):
            mock_gh.return_value.view_issue.return_value = {
                "labels": [{"name": "state/claimed"}],
                "state": "open",
            }
            apply_unified_noop_gate(
                store=mock_store,
                issue_number=100,
                branch="task/issue-100",
                actor="agent:plan",
                role="planner",
                before_state_label="state/claimed",
            )

        mock_block.assert_called_once()

    def test_planner_pass_when_state_changed(
        self,
    ) -> None:
        """Planner state/claimed → state/handoff → pass"""
        from unittest.mock import MagicMock, patch

        from vibe3.execution.noop_gate import apply_unified_noop_gate

        mock_store = MagicMock()

        with (
            patch("vibe3.clients.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.role_policy_helpers.block_planner_noop_issue"
            ) as mock_block,
        ):
            mock_gh.return_value.view_issue.return_value = {
                "labels": [{"name": "state/handoff"}],
                "state": "open",
            }
            apply_unified_noop_gate(
                store=mock_store,
                issue_number=100,
                branch="task/issue-100",
                actor="agent:plan",
                role="planner",
                before_state_label="state/claimed",
            )

        mock_block.assert_not_called()


def test_build_plan_prompt_retry_resume_provides_bootstrap_fallback() -> None:
    from vibe3.models.orchestration import IssueInfo
    from vibe3.roles.plan import build_plan_prompt

    config = SimpleNamespace(repo="owner/repo")
    issue = IssueInfo(number=123, title="Retry planning", labels=[])
    flow_state = {"plan_ref": "docs/plans/issue-123-plan.md"}

    with patch("vibe3.roles.plan._build_plan_task_guidance", return_value=None):
        prompt, refs, summary, include_notice, fallback_prompt = build_plan_prompt(
            config,
            issue,
            "task/issue-123",
            flow_state,
            session_id="ses_123",
        )

    assert refs == {"plan_ref": "docs/plans/issue-123-plan.md"}
    assert summary["prompt_mode"] == "retry"
    assert summary["context_mode"] == "resume"
    assert summary["fallback_context_mode"] == "bootstrap"
    assert include_notice is False
    assert fallback_prompt is not None
    assert "policy" not in prompt.lower()
    assert "handoff plan" in prompt
    assert "## Output format requirements" in fallback_prompt


class TestResolveSpecPlanInputDefaultSpecRef:
    """Tests for resolve_spec_plan_input using flow's spec_ref as default."""

    def test_explicit_file_works(self, tmp_path: Path) -> None:
        """Explicit --file should work normally."""
        spec_file = tmp_path / "explicit-spec.md"
        spec_file.write_text("Explicit spec content", encoding="utf-8")

        # Explicit file input never queries flow
        result = resolve_spec_plan_input("test-branch", file=spec_file)

        assert result.description == "Explicit spec content"
        assert result.spec_path == str(spec_file.resolve())

    def test_no_explicit_input_uses_flow_spec_ref_file(self, tmp_path: Path) -> None:
        """When no --file or --msg, use flow.spec_ref (file type)."""
        spec_file = tmp_path / "flow-spec.md"
        spec_file.write_text("Flow spec content", encoding="utf-8")

        # Mock flow with file spec_ref
        mock_flow = MagicMock()
        mock_flow.spec_ref = str(spec_file)

        # Mock spec service
        mock_spec_info = MagicMock()
        mock_spec_info.kind = "file"
        mock_spec_info.file_path = str(spec_file)

        # Patch at the source module, not where it's imported
        with (
            patch("vibe3.services.flow_service.FlowService") as mock_fs,
            patch("vibe3.services.spec_ref_service.SpecRefService") as mock_ss,
        ):
            mock_fs.return_value.get_flow_status.return_value = mock_flow
            mock_ss.return_value.parse_spec_ref.return_value = mock_spec_info
            mock_ss.return_value.validate_spec_ref.return_value = (True, "")
            mock_ss.return_value.get_spec_content_for_prompt.return_value = (
                "Flow spec content"
            )

            result = resolve_spec_plan_input("test-branch")

        assert result.description == "Flow spec content"
        assert result.spec_path == str(spec_file)

    def test_no_explicit_input_uses_flow_spec_ref_issue(self) -> None:
        """When no --file or --msg, use flow.spec_ref (issue type)."""
        # Mock flow with issue spec_ref
        mock_flow = MagicMock()
        mock_flow.spec_ref = "#789"

        # Mock spec service
        mock_spec_info = MagicMock()
        mock_spec_info.kind = "issue"
        mock_spec_info.issue_number = 789
        mock_spec_info.file_path = None

        # Patch at the source module
        with (
            patch("vibe3.services.flow_service.FlowService") as mock_fs,
            patch("vibe3.services.spec_ref_service.SpecRefService") as mock_ss,
        ):
            mock_fs.return_value.get_flow_status.return_value = mock_flow
            mock_ss.return_value.parse_spec_ref.return_value = mock_spec_info
            mock_ss.return_value.validate_spec_ref.return_value = (True, "")
            content = "Issue #789: Add feature\nBody content"
            mock_ss.return_value.get_spec_content_for_prompt.return_value = content

            result = resolve_spec_plan_input("test-branch")

        assert "Issue #789" in result.description
        assert result.spec_path is None

    def test_no_explicit_input_raises_when_no_flow_spec_ref(self) -> None:
        """Raise ValueError when no explicit input and flow has no spec_ref."""
        mock_flow = MagicMock()
        mock_flow.spec_ref = None

        # Patch at the source module
        with patch("vibe3.services.flow_service.FlowService") as mock_fs:
            mock_fs.return_value.get_flow_status.return_value = mock_flow

            with pytest.raises(ValueError) as exc_info:
                resolve_spec_plan_input("test-branch")

        assert "No spec provided" in str(exc_info.value)

    def test_no_explicit_input_raises_when_no_flow(self) -> None:
        """Raise ValueError when flow does not exist."""
        # Patch at the source module
        with patch("vibe3.services.flow_service.FlowService") as mock_fs:
            mock_fs.return_value.get_flow_status.return_value = None

            with pytest.raises(ValueError) as exc_info:
                resolve_spec_plan_input("test-branch")

        assert "No spec provided" in str(exc_info.value)

    def test_no_explicit_input_raises_when_flow_spec_ref_invalid(self) -> None:
        """Raise ValueError when flow.spec_ref is invalid."""
        mock_flow = MagicMock()
        mock_flow.spec_ref = "nonexistent.md"

        # Patch at the source module
        with (
            patch("vibe3.services.flow_service.FlowService") as mock_fs,
            patch("vibe3.services.spec_ref_service.SpecRefService") as mock_ss,
        ):
            mock_fs.return_value.get_flow_status.return_value = mock_flow
            mock_ss.return_value.validate_spec_ref.return_value = (
                False,
                "File not found",
            )

            with pytest.raises(ValueError) as exc_info:
                resolve_spec_plan_input("test-branch")

        assert "Flow spec_ref invalid" in str(exc_info.value)

    def test_no_explicit_input_raises_when_flow_spec_content_unreadable(self) -> None:
        """Raise ValueError when flow.spec_ref content cannot be read."""
        mock_flow = MagicMock()
        mock_flow.spec_ref = "#999"

        # Patch at the source module
        with (
            patch("vibe3.services.flow_service.FlowService") as mock_fs,
            patch("vibe3.services.spec_ref_service.SpecRefService") as mock_ss,
        ):
            mock_fs.return_value.get_flow_status.return_value = mock_flow
            mock_ss.return_value.validate_spec_ref.return_value = (True, "")
            mock_ss.return_value.get_spec_content_for_prompt.return_value = None

            with pytest.raises(ValueError) as exc_info:
                resolve_spec_plan_input("test-branch")

        assert "Failed to read spec content" in str(exc_info.value)


class TestExecuteSpecPlanAsyncWorktreeRequirement:
    """execute_spec_plan_async must set worktree_requirement=PERMANENT."""

    def test_sets_worktree_requirement_permanent(self) -> None:
        """ExecutionRequest must include worktree_requirement=PERMANENT."""
        from unittest.mock import MagicMock, patch

        from vibe3.execution.role_contracts import WorktreeRequirement

        mock_launch = MagicMock()
        mock_launch.launched = True
        mock_launch.tmux_session = "test-session"
        mock_launch.log_path = "/tmp/test.log"
        mock_launch.reason = ""

        with (
            patch(
                "vibe3.execution.issue_role_support.resolve_orchestra_repo_root",
                return_value=Path("/fake/repo"),
            ),
            patch("vibe3.roles.plan.load_orchestra_config"),
            patch("vibe3.clients.SQLiteClient"),
            patch("vibe3.roles.plan.ExecutionCoordinator") as mock_coord_cls,
        ):
            mock_coord = MagicMock()
            mock_coord.dispatch_execution.return_value = mock_launch
            mock_coord_cls.return_value = mock_coord

            from vibe3.roles.plan import execute_spec_plan_async

            execute_spec_plan_async(
                request=MagicMock(),
                issue_number=42,
                branch="dev/issue-42",
                cli_args=["plan"],
            )

            call_args = mock_coord.dispatch_execution.call_args
            exec_request = call_args[0][0]
            assert exec_request.worktree_requirement == WorktreeRequirement.PERMANENT
            assert exec_request.cwd is None
            assert exec_request.repo_path == "/fake/repo"

    def test_sets_worktree_requirement_permanent_no_issue(self) -> None:
        """Even without issue_number, worktree_requirement must be PERMANENT."""
        from unittest.mock import MagicMock, patch

        from vibe3.execution.role_contracts import WorktreeRequirement

        mock_launch = MagicMock()
        mock_launch.launched = True

        with (
            patch(
                "vibe3.execution.issue_role_support.resolve_orchestra_repo_root",
                return_value=Path("/fake/repo"),
            ),
            patch("vibe3.roles.plan.load_orchestra_config"),
            patch("vibe3.clients.SQLiteClient"),
            patch("vibe3.roles.plan.ExecutionCoordinator") as mock_coord_cls,
        ):
            mock_coord = MagicMock()
            mock_coord.dispatch_execution.return_value = mock_launch
            mock_coord_cls.return_value = mock_coord

            from vibe3.roles.plan import execute_spec_plan_async

            execute_spec_plan_async(
                request=MagicMock(),
                issue_number=None,
                branch="dev/issue-99",
                cli_args=["plan"],
            )

            exec_request = mock_coord.dispatch_execution.call_args[0][0]
            assert exec_request.worktree_requirement == WorktreeRequirement.PERMANENT
            assert exec_request.target_id == 0


class TestExecuteSpecPlanSyncCwdNone:
    """execute_spec_plan_sync must pass cwd=None to ExecutionRequest."""

    def test_sync_passes_cwd_none(self) -> None:
        """Sync execution passes cwd=None for coordinator to resolve."""
        from unittest.mock import MagicMock, patch

        with patch("vibe3.roles.plan.CodeagentExecutionService") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc.execute_sync.return_value = MagicMock(success=True, stderr="")
            mock_svc_cls.return_value = mock_svc

            from vibe3.roles.plan import execute_spec_plan_sync

            execute_spec_plan_sync(
                request=MagicMock(),
                issue_number=42,
                branch="task/issue-42",
            )

            call_args = mock_svc.execute_sync.call_args
            command = call_args[0][0]
            assert command.cwd is None
