"""Tests for manager recipe-driven prompt assembly."""

from pathlib import Path

import yaml

from vibe3.manager.manager_executor import ManagerExecutor
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.orchestra.config import AssigneeDispatchConfig, OrchestraConfig
from vibe3.prompts.models import PromptRecipe, VariableSourceKind


def make_issue(number: int = 42, title: str = "Test issue") -> IssueInfo:
    return IssueInfo(
        number=number,
        title=title,
        state=IssueState.CLAIMED,
        labels=["state/claimed"],
    )


class TestManagerRecipeDrivenPrompt:
    """Assert manager dispatch uses recipe-driven prompt assembly."""

    def test_build_manager_recipe_returns_prompt_recipe(self):
        config = OrchestraConfig()
        manager = ManagerExecutor(config, repo_path=Path("/tmp/repo"))
        recipe = manager.command_builder.build_manager_recipe()
        assert isinstance(recipe, PromptRecipe)

    def test_build_manager_recipe_uses_configured_template_key(self):
        config = OrchestraConfig(
            assignee_dispatch=AssigneeDispatchConfig(
                prompt_template="orchestra.assignee_dispatch.manager"
            )
        )
        manager = ManagerExecutor(config, repo_path=Path("/tmp/repo"))
        recipe = manager.command_builder.build_manager_recipe()
        assert recipe.template_key == "orchestra.assignee_dispatch.manager"

    def test_build_manager_command_still_produces_correct_last_arg(self, tmp_path):
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

        supervisor_src = recipe.variables.get("supervisor_content")
        assert supervisor_src is not None
        assert supervisor_src.kind == VariableSourceKind.FILE
        assert supervisor_src.path == "supervisor/manager.md"
