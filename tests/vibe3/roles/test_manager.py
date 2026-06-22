"""Tests for manager prompt assembly behavior.

Note: Dispatch queue filtering tests moved to
test_dispatch_queue_operations.py after StateLabelDispatchService
deletion in issue-462 refactoring.
"""

from pathlib import Path

from vibe3.models.orchestra_config import AssigneeDispatchConfig, OrchestraConfig
from vibe3.models.orchestration import IssueInfo
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

        # Patch paths
        monkeypatch.setattr(manifest, "DEFAULT_PROMPT_RECIPES_PATH", recipes_path)
        monkeypatch.setattr(
            "vibe3.roles.manager.load_prompt_templates",
            lambda prompts_path=None: {
                "manager": {
                    "target": "target section",
                    "quick_commands": "quick commands",
                    "retry_task": "retry task",
                }
            },
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

        monkeypatch.setattr(manifest, "DEFAULT_PROMPT_RECIPES_PATH", recipes_path)
        monkeypatch.setattr(
            "vibe3.roles.manager.load_prompt_templates",
            lambda prompts_path=None: {
                "manager": {
                    "target": "target section",
                    "retry_task": "retry task",
                }
            },
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

        monkeypatch.setattr(manifest, "DEFAULT_PROMPT_RECIPES_PATH", recipes_path)
        monkeypatch.setattr(
            "vibe3.roles.manager.load_prompt_templates",
            lambda prompts_path=None: {
                "manager": {
                    "target": "target section",
                    "retry_task": "retry task",
                }
            },
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

    def test_first_bootstrap_generates_dry_run_summary(self, tmp_path, monkeypatch):
        """first.bootstrap variant produces a dry_run_summary with correct fields."""
        from vibe3.prompts import manifest

        recipes_path = tmp_path / "prompt-recipes.yaml"
        recipes_path.write_text("""
recipes:
  manager.default:
    kind: section_recipe
    variants:
      first.bootstrap:
        sections:
          - key: manager.target
          - key: manager.quick_commands
      retry.resume:
        sections:
          - manager.retry_task
""")

        monkeypatch.setattr(manifest, "DEFAULT_PROMPT_RECIPES_PATH", recipes_path)
        monkeypatch.setattr(
            "vibe3.roles.manager.load_prompt_templates",
            lambda prompts_path=None: {
                "manager": {
                    "target": "target section",
                    "quick_commands": "quick commands",
                    "retry_task": "retry task",
                }
            },
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
            dry_run=True,
            show_prompt=False,
        )

        assert request.dry_run_summary["prompt_mode"] == "first"
        assert request.dry_run_summary["context_mode"] == "bootstrap"
        assert request.dry_run_summary["session_reused"] is False
        assert request.dry_run_summary["session_id"] == ""
        assert "manager.target" in request.dry_run_summary["sections"]
        assert "manager.quick_commands" in request.dry_run_summary["sections"]

    def test_retry_resume_generates_dry_run_summary(self, tmp_path, monkeypatch):
        """retry.resume variant produces a dry_run_summary with retry fields."""
        from vibe3.prompts import manifest

        recipes_path = tmp_path / "prompt-recipes.yaml"
        recipes_path.write_text("""
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
""")

        monkeypatch.setattr(manifest, "DEFAULT_PROMPT_RECIPES_PATH", recipes_path)
        monkeypatch.setattr(
            "vibe3.roles.manager.load_prompt_templates",
            lambda prompts_path=None: {
                "manager": {
                    "target": "target section",
                    "retry_task": "retry task",
                }
            },
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
            dry_run=True,
            show_prompt=False,
        )

        assert request.dry_run_summary["prompt_mode"] == "retry"
        assert request.dry_run_summary["context_mode"] == "resume"
        assert request.dry_run_summary["session_reused"] is True
        assert request.dry_run_summary["session_id"] == "session-1"
        assert request.dry_run_summary["sections"] == ["manager.retry_task"]

    def test_dry_run_passes_annotate_sections_to_render_sections(
        self, tmp_path, monkeypatch
    ):
        """dry_run=True passes annotate_sections=True to render_sections."""
        from unittest.mock import patch

        from vibe3.prompts import manifest

        recipes_path = tmp_path / "prompt-recipes.yaml"
        recipes_path.write_text("""
recipes:
  manager.default:
    kind: section_recipe
    variants:
      first.bootstrap:
        sections:
          - key: manager.target
""")

        monkeypatch.setattr(manifest, "DEFAULT_PROMPT_RECIPES_PATH", recipes_path)
        monkeypatch.setattr(
            "vibe3.roles.manager.load_prompt_templates",
            lambda prompts_path=None: {
                "manager": {
                    "target": "target section",
                }
            },
        )

        config = OrchestraConfig(assignee_dispatch=AssigneeDispatchConfig())

        # Patch render_sections to capture annotate_sections parameter
        with patch.object(
            manifest.PromptManifest,
            "render_sections",
            wraps=manifest.PromptManifest.load_default().render_sections,
        ) as mock_render:
            # Need to return a valid prompt result
            mock_render.return_value = "test prompt"

            build_manager_sync_request(
                config=config,
                issue=IssueInfo(number=661, title="Test"),
                branch="task/issue-661",
                flow_state=None,
                session_id=None,
                options=object(),
                actor="test",
                dry_run=True,
                show_prompt=False,
            )

            # Verify annotate_sections=True was passed
            assert mock_render.called
            call_kwargs = mock_render.call_args[1]
            assert call_kwargs.get("annotate_sections") is True
