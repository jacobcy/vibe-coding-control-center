"""Tests for Orchestra ManagerExecutor - review dispatch and manager commands."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import yaml

from tests.vibe3.conftest import CompletedProcess
from vibe3.manager.manager_executor import ManagerExecutor
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.orchestra.config import OrchestraConfig


def make_issue(number: int = 42, title: str = "Test issue") -> IssueInfo:
    return IssueInfo(
        number=number,
        title=title,
        state=IssueState.CLAIMED,
        labels=["state/claimed"],
    )


class TestManagerReviewWorktreeResolution:
    def test_prepare_pr_review_dispatch_returns_command_and_cwd(self):
        config = OrchestraConfig()
        manager = ManagerExecutor(config, repo_path=Path("/tmp/repo"))

        with patch.object(
            manager, "_resolve_review_cwd", return_value=Path("/tmp/wt-feature")
        ):
            # prepare_pr_review_dispatch was a test proxy, now we call components
            cmd = manager.command_builder.build_pr_review_command(42)
            cwd = manager._resolve_review_cwd_for_dispatch(42)

        assert cmd == ["uv", "run", "python", "-m", "vibe3", "review", "pr", "42"]
        assert cwd == Path("/tmp/wt-feature")

    def test_dispatch_pr_review_uses_resolved_worktree(self):
        config = OrchestraConfig()
        manager = ManagerExecutor(config, repo_path=Path("/tmp/repo"))

        with patch.object(
            manager, "_resolve_review_cwd", return_value=Path("/tmp/wt-feature")
        ):
            with patch.object(manager, "can_dispatch", return_value=True):
                with patch(
                    "subprocess.run",
                    return_value=CompletedProcess(returncode=0),
                ) as mock_run:
                    result = manager.dispatch_pr_review(42)

        assert result is True
        # ManagerExecutor calls run_command which calls subprocess.run
        cwd_calls = [c for c in mock_run.call_args_list if c[1].get("cwd") is not None]
        assert any(c[1]["cwd"] == Path("/tmp/wt-feature") for c in cwd_calls)

    def test_dispatch_pr_review_appends_async_flag_when_enabled(self):
        config = OrchestraConfig()
        config.pr_review_dispatch.async_mode = True
        manager = ManagerExecutor(config, repo_path=Path("/tmp/repo"))

        with patch.object(
            manager, "_resolve_review_cwd", return_value=Path("/tmp/wt-feature")
        ):
            with patch.object(manager, "can_dispatch", return_value=True):
                with patch(
                    "subprocess.run",
                    return_value=CompletedProcess(returncode=0),
                ) as mock_run:
                    result = manager.dispatch_pr_review(42)

        assert result is True
        async_calls = [c for c in mock_run.call_args_list if "--async" in c[0][0]]
        assert len(async_calls) > 0

    def test_build_manager_command_formats_issue_prompt(self):
        config = OrchestraConfig()
        manager = ManagerExecutor(config, repo_path=Path("/tmp/repo"))
        issue = make_issue(number=88, title="Improve parser")

        cmd = manager.command_builder.build_manager_command(issue)

        assert cmd[:6] == ["uv", "run", "python", "-m", "vibe3", "run"]
        assert "--async" in cmd
        assert "--worktree" in cmd
        assert "Manage issue #88: Improve parser" in cmd[-1]
        assert "## Role" in cmd[-1]
        assert "状态控制器" in cmd[-1]
        assert "不是实现 agent" in cmd[-1]

    def test_build_manager_command_can_disable_worktree_mode(self):
        config = OrchestraConfig()
        config.assignee_dispatch.use_worktree = False
        manager = ManagerExecutor(config, repo_path=Path("/tmp/repo"))
        issue = make_issue(number=89, title="Run in current flow")

        cmd = manager.command_builder.build_manager_command(issue)

        assert "--async" in cmd
        assert "--worktree" not in cmd
        assert "Manage issue #89: Run in current flow" in cmd[-1]
        assert "comment、写 handoff、修改 labels" in cmd[-1]

    def test_dispatch_manager_dry_run_skips_flow_creation_and_execution(self):
        config = OrchestraConfig(dry_run=True)
        manager = ManagerExecutor(config, dry_run=True, repo_path=Path("/tmp/repo"))
        issue = make_issue(number=101, title="Dry run manager dispatch")

        with patch.object(
            manager.flow_manager,
            "create_flow_for_issue",
        ) as mock_create_flow:
            with patch.object(manager, "can_dispatch", return_value=True):
                with patch("subprocess.run") as mock_run:
                    result = manager.dispatch_manager(issue)

        assert result is True
        mock_create_flow.assert_not_called()
        # subprocess.run might be called by other components (e.g. SQLiteClient)
        # but NOT for actual execution if dry_run works.
        # However, ManagerExecutor doesn't call run_command in dry_run mode.
        exec_calls = [c for c in mock_run.call_args_list if "vibe3" in str(c[0][0])]
        assert len(exec_calls) == 0

    def test_dispatch_manager_starts_internal_manager_run_in_target_worktree(self):
        config = OrchestraConfig()
        manager = ManagerExecutor(config, repo_path=Path("/tmp/repo"))
        issue = make_issue(number=102, title="Manager session test")

        with patch.object(
            manager.flow_manager,
            "create_flow_for_issue",
            return_value={"branch": "task/issue-102"},
        ):
            with patch.object(
                manager.status_service, "get_active_flow_count", return_value=0
            ):
                with patch.object(
                    manager,
                    "_resolve_manager_cwd",
                    return_value=(Path("/tmp/repo/.worktrees/issue-102"), False),
                ):
                    with patch.object(manager.result_handler, "update_state_label"):
                        with patch.object(
                            manager.flow_manager.store,
                            "add_event",
                        ) as mock_add_event:
                            with patch.object(
                                manager._backend,
                                "start_async_command",
                                return_value=SimpleNamespace(
                                    tmux_session="vibe3-manager-102",
                                    log_path=Path(
                                        "/tmp/repo/temp/logs/vibe3-manager-102.async.log"
                                    ),
                                ),
                            ) as mock_start:
                                result = manager.dispatch_manager(issue)

        assert result is True
        mock_start.assert_called_once()
        call = mock_start.call_args
        cmd = call.args[0]
        assert cmd[:5] == ["uv", "run", "python", "src/vibe3/cli.py", "run"]
        assert "--manager-issue" in cmd
        assert "--sync" in cmd
        assert call.kwargs["cwd"] == Path("/tmp/repo/.worktrees/issue-102")
        # Async dispatch records "dispatched" event, not success
        mock_add_event.assert_called_once()
        assert mock_add_event.call_args.args[1] == "manager_dispatched"

    def test_dispatch_manager_marks_issue_claimed_before_launch(self):
        config = OrchestraConfig()
        manager = ManagerExecutor(config, repo_path=Path("/tmp/repo"))
        issue = make_issue(number=103, title="Claim before manager run")

        with patch.object(
            manager.flow_manager,
            "create_flow_for_issue",
            return_value={"branch": "task/issue-103"},
        ):
            with patch.object(
                manager.status_service, "get_active_flow_count", return_value=0
            ):
                with patch.object(
                    manager,
                    "_resolve_manager_cwd",
                    return_value=(Path("/tmp/repo/.worktrees/issue-103"), False),
                ):
                    with patch.object(
                        manager.result_handler, "update_state_label"
                    ) as mock_update:
                        with patch.object(
                            manager.result_handler, "on_dispatch_success"
                        ):
                            with patch.object(
                                manager._backend,
                                "start_async_command",
                                return_value=SimpleNamespace(
                                    tmux_session="vibe3-manager-103",
                                    log_path=Path(
                                        "/tmp/repo/temp/logs/vibe3-manager-103.async.log"
                                    ),
                                ),
                            ):
                                result = manager.dispatch_manager(issue)

        assert result is True
        mock_update.assert_called_once_with(issue.number, IssueState.CLAIMED)

    def test_find_worktree_for_branch_parses_porcelain_output(self):
        config = OrchestraConfig()
        manager = ManagerExecutor(config, repo_path=Path("/tmp/repo"))
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
            wt = manager.worktree_manager._find_worktree_for_branch(
                "task/issue250-orchestra-manager"
            )

        assert wt == Path("/tmp/wt-feature")

    def test_resolve_review_cwd_falls_back_to_repo_path(self):
        config = OrchestraConfig()
        manager = ManagerExecutor(config, repo_path=Path("/tmp/repo"))

        class _PR:
            head_branch = "task/missing"

        with patch(
            "vibe3.clients.github_client.GitHubClient.get_pr",
            return_value=_PR(),
        ):
            with patch.object(
                manager.worktree_manager,
                "_find_worktree_for_branch",
                return_value=None,
            ):
                cwd = manager._resolve_review_cwd(99)

        assert cwd == Path("/tmp/repo")

    def test_prepare_pr_review_dispatch_can_force_wrapper_worktree(self):
        config = OrchestraConfig()
        config.pr_review_dispatch.use_worktree = True
        manager = ManagerExecutor(config, repo_path=Path("/tmp/repo"))

        with patch.object(manager, "_resolve_review_cwd") as mock_resolve:
            cmd = manager.command_builder.build_pr_review_command(42)
            cwd = manager._resolve_review_cwd_for_dispatch(42)

        mock_resolve.assert_not_called()
        assert "--worktree" in cmd
        assert cwd == Path("/tmp/repo")


class TestManagerRecipeDrivenPrompt:
    """Assert manager dispatch uses recipe-driven prompt assembly."""

    def test_build_manager_recipe_returns_prompt_recipe(self):
        """ManagerExecutor should expose recipe building via CommandBuilder."""
        from vibe3.prompts.models import PromptRecipe

        config = OrchestraConfig()
        manager = ManagerExecutor(config, repo_path=Path("/tmp/repo"))
        recipe = manager.command_builder.build_manager_recipe()
        assert isinstance(recipe, PromptRecipe)

    def test_build_manager_recipe_uses_configured_template_key(self):
        """Recipe template_key should come from config."""
        from vibe3.orchestra.config import AssigneeDispatchConfig

        config = OrchestraConfig(
            assignee_dispatch=AssigneeDispatchConfig(
                prompt_template="orchestra.assignee_dispatch.manager"
            )
        )
        manager = ManagerExecutor(config, repo_path=Path("/tmp/repo"))
        recipe = manager.command_builder.build_manager_recipe()
        assert recipe.template_key == "orchestra.assignee_dispatch.manager"

    def test_build_manager_command_still_produces_correct_last_arg(self, tmp_path):
        """Default template should produce same text as the old hardcoded format."""
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
            assignee_dispatch=AssigneeDispatchConfig(
                prompt_template="orchestra.assignee_dispatch.manager"
            )
        )
        manager = ManagerExecutor(
            config, repo_path=Path("/tmp/repo"), prompts_path=prompts_path
        )
        issue = make_issue(number=88, title="Improve parser")
        cmd = manager.command_builder.build_manager_command(issue)
        assert cmd[-1] == "Implement issue #88: Improve parser"

    def test_dispatch_manager_dry_run_logs_rendered_prompt(self, tmp_path):
        """Dry run should be able to show rendered prompt."""
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
        manager = ManagerExecutor(
            config, dry_run=True, repo_path=Path("/tmp/repo"), prompts_path=prompts_path
        )
        issue = make_issue(number=42, title="Dry run test")
        manager.command_builder.build_manager_command(issue)
        assert manager.last_manager_render_result is not None
        assert "Implement issue #42: Dry run test" in (
            manager.last_manager_render_result.rendered_text
        )

    def test_manager_recipe_uses_file_source_for_supervisor_content(self, tmp_path):
        """include_supervisor_content=True: FILE source for supervisor/manager.md."""
        from vibe3.orchestra.config import AssigneeDispatchConfig
        from vibe3.prompts.models import VariableSourceKind

        templates = {
            "orchestra": {
                "assignee_dispatch": {
                    "manager": (
                        "Implement issue #{issue_number}: {issue_title}"
                        "\nSupervisor: {supervisor_content}"
                    ),
                }
            }
        }
        prompts_path = tmp_path / "prompts.yaml"
        prompts_path.write_text(yaml.dump(templates), encoding="utf-8")

        config = OrchestraConfig(
            assignee_dispatch=AssigneeDispatchConfig(
                prompt_template="orchestra.assignee_dispatch.manager",
                supervisor_file="supervisor/manager.md",
                include_supervisor_content=True,
            ),
        )

        manager = ManagerExecutor(
            config, repo_path=Path("/tmp/repo"), prompts_path=prompts_path
        )
        recipe = manager.command_builder.build_manager_recipe()

        # Verify supervisor_content uses FILE source
        supervisor_src = recipe.variables.get("supervisor_content")
        assert supervisor_src is not None
        assert supervisor_src.kind == VariableSourceKind.FILE
        assert supervisor_src.path == "supervisor/manager.md"
