"""Tests for manager role dispatching and state transition behavior.

钉死 manager 的关键行为：
1. blocked issue 不应该被派发
2. blocked → handoff 转换应该被阻止
3. blocked_reason 字段正确写入

Note: Dispatch queue filtering tests moved to
test_dispatch_queue_operations.py after StateLabelDispatchService
deletion in issue-462 refactoring.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.models.orchestra_config import AssigneeDispatchConfig, OrchestraConfig
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.roles.manager import build_manager_sync_request


class TestManagerPromptAssembly:
    """Manager prompt output is controlled by prompt-recipes.yaml sections."""

    def test_bootstrap_recipe_renders_supervisor_from_recipe_source(
        self, tmp_path, monkeypatch
    ):
        """Supervisor content comes from recipe source declaration."""
        from vibe3.prompts import manifest

        # Create supervisor file
        supervisor_file = tmp_path / "manager.md"
        supervisor_file.write_text("MANAGER SUPERVISOR BODY", encoding="utf-8")

        # Create recipe with source declaration
        recipes_path = tmp_path / "prompt-recipes.yaml"
        recipes_path.write_text(
            f"""
recipes:
  manager.default:
    kind: section_recipe
    variants:
      first.bootstrap:
        sections:
          - key: manager.supervisor_content
            source:
              kind: file
              path: {supervisor_file}
          - key: manager.target
          - key: manager.quick_commands
      retry.resume:
        sections:
          - manager.retry_task
""",
            encoding="utf-8",
        )

        # Create prompts.yaml with minimal sections
        prompts_path = tmp_path / "prompts.yaml"
        prompts_path.write_text(
            """
manager:
  target: "target section"
  quick_commands: "quick commands"
  retry_task: "retry task"
""",
            encoding="utf-8",
        )

        # Patch paths
        monkeypatch.setattr(manifest, "DEFAULT_PROMPT_RECIPES_PATH", recipes_path)
        monkeypatch.setattr(
            "vibe3.roles.manager.resolve_prompts_path", lambda: prompts_path
        )

        config = OrchestraConfig(assignee_dispatch=AssigneeDispatchConfig())

        request = build_manager_sync_request(
            config=config,
            issue=IssueInfo(number=661, title="Config cleanup"),
            branch="task/issue-661",
            flow_state=None,
            session_id=None,
            options=object(),
            actor="test",
            dry_run=False,
            show_prompt=False,
        )

        assert "MANAGER SUPERVISOR BODY" in (request.prompt or "")

    def test_retry_resume_recipe_does_not_render_supervisor_section(
        self, tmp_path, monkeypatch
    ):
        """retry.resume variant does not include supervisor_content section."""
        from vibe3.prompts import manifest

        # Create recipe without supervisor_content in retry.resume
        recipes_path = tmp_path / "prompt-recipes.yaml"
        recipes_path.write_text(
            """
recipes:
  manager.default:
    kind: section_recipe
    variants:
      first.bootstrap:
        sections:
          - key: manager.supervisor_content
            source:
              kind: literal
              value: "SUPERVISOR CONTENT"
          - key: manager.target
      retry.resume:
        sections:
          - manager.retry_task
""",
            encoding="utf-8",
        )

        prompts_path = tmp_path / "prompts.yaml"
        prompts_path.write_text(
            """
manager:
  target: "target section"
  retry_task: "retry task"
""",
            encoding="utf-8",
        )

        monkeypatch.setattr(manifest, "DEFAULT_PROMPT_RECIPES_PATH", recipes_path)
        monkeypatch.setattr(
            "vibe3.roles.manager.resolve_prompts_path", lambda: prompts_path
        )

        config = OrchestraConfig(assignee_dispatch=AssigneeDispatchConfig())

        request = build_manager_sync_request(
            config=config,
            issue=IssueInfo(number=661, title="Config cleanup"),
            branch="task/issue-661",
            flow_state=None,
            session_id="session-1",
            options=object(),
            actor="test",
            dry_run=False,
            show_prompt=False,
        )

        assert "SUPERVISOR CONTENT" not in (request.prompt or "")

    def test_retry_resume_uses_main_repo_root_not_current_cwd(
        self, tmp_path, monkeypatch
    ) -> None:
        """Retry manager requests should keep orchestration anchored to main repo."""
        from vibe3.prompts import manifest

        recipes_path = tmp_path / "prompt-recipes.yaml"
        recipes_path.write_text(
            """
recipes:
  manager.default:
    kind: section_recipe
    variants:
      first.bootstrap:
        sections:
          - key: manager.target
      retry.resume:
        sections:
          - manager.retry_task
""",
            encoding="utf-8",
        )

        prompts_path = tmp_path / "prompts.yaml"
        prompts_path.write_text(
            """
manager:
  target: "target section"
  retry_task: "retry task"
""",
            encoding="utf-8",
        )

        monkeypatch.setattr(manifest, "DEFAULT_PROMPT_RECIPES_PATH", recipes_path)
        monkeypatch.setattr(
            "vibe3.roles.manager.resolve_prompts_path", lambda: prompts_path
        )
        monkeypatch.setattr(
            "vibe3.roles.manager.resolve_orchestra_repo_root",
            lambda: Path("/test/repos/vibe-center/main"),
        )

        config = OrchestraConfig(assignee_dispatch=AssigneeDispatchConfig())

        request = build_manager_sync_request(
            config=config,
            issue=IssueInfo(number=661, title="Config cleanup"),
            branch="task/issue-661",
            flow_state=None,
            session_id="session-1",
            options=object(),
            actor="test",
            dry_run=False,
            show_prompt=False,
        )

        assert request.repo_path == "/test/repos/vibe-center/main"


class TestManagerBlockedToHandoffTransitionBlocked:
    """blocked → handoff 转换应该被阻止"""

    def test_blocked_to_handoff_forbidden_without_force(
        self,
    ) -> None:
        """ALLOWED_TRANSITIONS 应该拒绝 blocked → handoff"""
        from vibe3.domain.state_machine import validate_transition
        from vibe3.exceptions import InvalidTransitionError

        # Try blocked → handoff
        with pytest.raises(InvalidTransitionError):
            validate_transition(
                from_state=IssueState.BLOCKED,
                to_state=IssueState.HANDOFF,
                force=False,  # ← 不强制
            )

    def test_blocked_to_handoff_allowed_with_force(
        self,
    ) -> None:
        """手动 resume 命令可以用 force=True 绕过"""
        from vibe3.domain.state_machine import validate_transition

        # Try blocked → handoff with force=True
        validate_transition(
            from_state=IssueState.BLOCKED,
            to_state=IssueState.HANDOFF,
            force=True,  # ← 强制绕过（用于手动命令）
        )


class TestManagerBlockedReasonWriting:
    """blocked_reason 字段写入"""

    def test_manager_blocked_calls_ensure_flow_state(
        self,
    ) -> None:
        """Manager blocked 应该通过 block_flow 设置 blocked_reason"""
        mock_issue_number = 305

        with patch(
            "vibe3.services.issue_failure_service._get_issue_flow_service"
        ) as mock_get_service:
            mock_service = MagicMock()
            mock_store = MagicMock()
            mock_service.store = mock_store
            mock_get_service.return_value = mock_service

            # Mock flow data
            mock_store.get_flows_by_issue.return_value = [
                {"branch": "task/issue-305", "task_issue_number": 305}
            ]

            with patch("vibe3.services.flow_service.FlowService") as mock_flow_service:
                mock_flow_instance = mock_flow_service.return_value

                from vibe3.services import (
                    block_manager_noop_issue,
                )

                block_manager_noop_issue(
                    issue_number=mock_issue_number,
                    repo="jacobcy/vibe-coding-control-center",
                    reason="manager 本轮未产生状态迁移",
                    actor="test-backend/test-model",
                )

                # Verify: block_flow called with correct parameters
                mock_flow_instance.block_flow.assert_called_once_with(
                    "task/issue-305",
                    reason="manager 本轮未产生状态迁移",
                    actor="test-backend/test-model",
                )
