"""Tests for Orchestra dispatcher - review dispatch and manager commands."""

from pathlib import Path
from unittest.mock import patch

from tests.vibe3.orchestra.conftest import CompletedProcess
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.dispatcher import Dispatcher


def make_issue(number: int = 42, title: str = "Test issue") -> IssueInfo:
    return IssueInfo(
        number=number,
        title=title,
        state=IssueState.CLAIMED,
        labels=["state/claimed"],
    )


class TestDispatcherReviewWorktreeResolution:
    def test_prepare_pr_review_dispatch_returns_command_and_cwd(self):
        config = OrchestraConfig()
        dispatcher = Dispatcher(config, repo_path=Path("/tmp/repo"))

        with patch.object(
            dispatcher, "_resolve_review_cwd", return_value=Path("/tmp/wt-feature")
        ):
            cmd, cwd = dispatcher.prepare_pr_review_dispatch(42)

        assert cmd == ["uv", "run", "python", "-m", "vibe3", "review", "pr", "42"]
        assert cwd == Path("/tmp/wt-feature")

    def test_dispatch_pr_review_uses_resolved_worktree(self):
        config = OrchestraConfig()
        dispatcher = Dispatcher(config, repo_path=Path("/tmp/repo"))

        with patch.object(
            dispatcher, "_resolve_review_cwd", return_value=Path("/tmp/wt-feature")
        ):
            with patch(
                "subprocess.run",
                return_value=CompletedProcess(returncode=0),
            ) as mock_run:
                result = dispatcher.dispatch_pr_review(42)

        assert result is True
        mock_run.assert_called_once()
        assert mock_run.call_args.kwargs["cwd"] == Path("/tmp/wt-feature")
        assert "--async" not in mock_run.call_args.args[0]

    def test_dispatch_pr_review_appends_async_flag_when_enabled(self):
        config = OrchestraConfig()
        config.pr_review_dispatch.async_mode = True
        dispatcher = Dispatcher(config, repo_path=Path("/tmp/repo"))

        with patch.object(
            dispatcher, "_resolve_review_cwd", return_value=Path("/tmp/wt-feature")
        ):
            with patch(
                "subprocess.run",
                return_value=CompletedProcess(returncode=0),
            ) as mock_run:
                result = dispatcher.dispatch_pr_review(42)

        assert result is True
        mock_run.assert_called_once()
        assert "--async" in mock_run.call_args.args[0]

    def test_build_manager_command_formats_issue_prompt(self):
        config = OrchestraConfig()
        dispatcher = Dispatcher(config, repo_path=Path("/tmp/repo"))
        issue = make_issue(number=88, title="Improve parser")

        cmd = dispatcher.build_manager_command(issue)

        assert cmd[:6] == ["uv", "run", "python", "-m", "vibe3", "run"]
        assert "--worktree" in cmd
        assert cmd[-1] == "Implement issue #88: Improve parser"

    def test_build_manager_command_can_disable_worktree_mode(self):
        config = OrchestraConfig()
        config.assignee_dispatch.use_worktree = False
        dispatcher = Dispatcher(config, repo_path=Path("/tmp/repo"))
        issue = make_issue(number=89, title="Run in current flow")

        cmd = dispatcher.build_manager_command(issue)

        assert "--worktree" not in cmd
        assert cmd[-1] == "Implement issue #89: Run in current flow"

    def test_dispatch_manager_dry_run_skips_flow_creation_and_execution(self):
        config = OrchestraConfig(dry_run=True)
        dispatcher = Dispatcher(config, dry_run=True, repo_path=Path("/tmp/repo"))
        issue = make_issue(number=101, title="Dry run manager dispatch")

        with patch.object(
            dispatcher.orchestrator,
            "create_flow_for_issue",
        ) as mock_create_flow:
            with patch("subprocess.run") as mock_run:
                result = dispatcher.dispatch_manager(issue)

        assert result is True
        mock_create_flow.assert_not_called()
        mock_run.assert_not_called()

    def test_find_worktree_for_branch_parses_porcelain_output(self):
        config = OrchestraConfig()
        dispatcher = Dispatcher(config, repo_path=Path("/tmp/repo"))
        output = (
            "worktree /tmp/repo\n"
            "HEAD abcdef0\n"
            "branch refs/heads/main\n"
            "\n"
            "worktree /tmp/wt-feature\n"
            "HEAD 1234567\n"
            "branch refs/heads/task/issue250-orchestra-manager\n"
            "\n"
        )

        with patch(
            "subprocess.run",
            return_value=CompletedProcess(returncode=0, stdout=output),
        ):
            wt = dispatcher._find_worktree_for_branch("task/issue250-orchestra-manager")

        assert wt == Path("/tmp/wt-feature")

    def test_resolve_review_cwd_falls_back_to_repo_path(self):
        config = OrchestraConfig()
        dispatcher = Dispatcher(config, repo_path=Path("/tmp/repo"))

        class _PR:
            head_branch = "task/missing"

        with patch(
            "vibe3.clients.github_client.GitHubClient.get_pr",
            return_value=_PR(),
        ):
            with patch.object(
                dispatcher,
                "_find_worktree_for_branch",
                return_value=None,
            ):
                cwd = dispatcher._resolve_review_cwd(99)

        assert cwd == Path("/tmp/repo")

    def test_prepare_pr_review_dispatch_can_force_wrapper_worktree(self):
        config = OrchestraConfig()
        config.pr_review_dispatch.use_worktree = True
        dispatcher = Dispatcher(config, repo_path=Path("/tmp/repo"))

        with patch.object(dispatcher, "_resolve_review_cwd") as mock_resolve:
            cmd, cwd = dispatcher.prepare_pr_review_dispatch(42)

        mock_resolve.assert_not_called()
        assert "--worktree" in cmd
        assert cwd == Path("/tmp/repo")


class TestDispatcherManagerRecipeDrivenPrompt:
    """Assert manager dispatch uses recipe-driven prompt assembly."""

    def test_build_manager_recipe_returns_prompt_recipe(self):
        """Dispatcher should expose _build_manager_recipe() returning a PromptRecipe."""
        from vibe3.prompts.models import PromptRecipe

        config = OrchestraConfig()
        dispatcher = Dispatcher(config, repo_path=Path("/tmp/repo"))
        recipe = dispatcher._build_manager_recipe()
        assert isinstance(recipe, PromptRecipe)

    def test_build_manager_recipe_uses_configured_template_key(self):
        """Recipe template_key should come from config, not be hardcoded."""
        from vibe3.orchestra.config import AssigneeDispatchConfig

        config = OrchestraConfig(
            assignee_dispatch=AssigneeDispatchConfig(
                prompt_template="orchestra.assignee_dispatch.manager"
            )
        )
        dispatcher = Dispatcher(config, repo_path=Path("/tmp/repo"))
        recipe = dispatcher._build_manager_recipe()
        assert recipe.template_key == "orchestra.assignee_dispatch.manager"

    def test_build_manager_command_still_produces_correct_last_arg(self, tmp_path):
        """Default template should produce same text as the old hardcoded format."""
        import yaml

        from vibe3.orchestra.config import AssigneeDispatchConfig

        # Write the default template to a tmp prompts.yaml
        templates = {
            "orchestra": {
                "assignee_dispatch": {
                    "manager": "Implement issue #{issue_number}: {issue_title}"
                }
            }
        }
        prompts_path = tmp_path / "prompts.yaml"
        prompts_path.write_text(yaml.dump(templates), encoding="utf-8")

        config = OrchestraConfig(
            assignee_dispatch=AssigneeDispatchConfig(
                prompt_template="orchestra.assignee_dispatch.manager"
            )
        )
        dispatcher = Dispatcher(
            config, repo_path=Path("/tmp/repo"), prompts_path=prompts_path
        )
        issue = make_issue(number=88, title="Improve parser")
        cmd = dispatcher.build_manager_command(issue)
        assert cmd[-1] == "Implement issue #88: Improve parser"

    def test_dispatch_manager_dry_run_logs_rendered_prompt(self, tmp_path, capsys):
        """Dry run should be able to show rendered prompt (not hardcoded string)."""
        import yaml

        from vibe3.orchestra.config import AssigneeDispatchConfig

        templates = {
            "orchestra": {
                "assignee_dispatch": {
                    "manager": "Implement issue #{issue_number}: {issue_title}"
                }
            }
        }
        prompts_path = tmp_path / "prompts.yaml"
        prompts_path.write_text(yaml.dump(templates), encoding="utf-8")

        config = OrchestraConfig(
            dry_run=True,
            assignee_dispatch=AssigneeDispatchConfig(
                prompt_template="orchestra.assignee_dispatch.manager"
            ),
        )
        dispatcher = Dispatcher(
            config, dry_run=True, repo_path=Path("/tmp/repo"), prompts_path=prompts_path
        )
        issue = make_issue(number=42, title="Dry run test")
        dispatcher.build_manager_command(issue)
        assert dispatcher.last_manager_render_result is not None
        assert "Implement issue #42: Dry run test" in (
            dispatcher.last_manager_render_result.rendered_text
        )
