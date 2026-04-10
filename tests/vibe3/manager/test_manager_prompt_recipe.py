"""Tests for manager recipe-driven prompt assembly without executor shell."""

import yaml

from vibe3.manager.prompts import (
    build_manager_command,
    build_manager_recipe,
    render_manager_prompt,
)
from vibe3.models.orchestra_config import AssigneeDispatchConfig, OrchestraConfig
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.prompts.models import PromptRecipe, VariableSourceKind


def make_issue(number: int = 42, title: str = "Test issue") -> IssueInfo:
    return IssueInfo(
        number=number,
        title=title,
        state=IssueState.CLAIMED,
        labels=["state/claimed"],
    )


class TestManagerRecipeDrivenPrompt:
    def test_build_manager_recipe_returns_prompt_recipe(self):
        recipe = build_manager_recipe(OrchestraConfig())
        assert isinstance(recipe, PromptRecipe)

    def test_build_manager_recipe_uses_configured_template_key(self):
        config = OrchestraConfig(
            assignee_dispatch=AssigneeDispatchConfig(
                prompt_template="orchestra.assignee_dispatch.manager"
            )
        )
        recipe = build_manager_recipe(config)
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
        issue = make_issue(number=88, title="Improve parser")
        rendered = render_manager_prompt(config, issue, prompts_path=prompts_path)
        cmd = build_manager_command(config, rendered.rendered_text)
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
            assignee_dispatch=AssigneeDispatchConfig(
                prompt_template="orchestra.assignee_dispatch.manager"
            ),
        )
        issue = make_issue(number=42, title="Dry run test")
        rendered = render_manager_prompt(config, issue, prompts_path=prompts_path)
        build_manager_command(config, rendered.rendered_text)
        assert rendered is not None
        assert "Implement issue #42: Dry run test" in (rendered.rendered_text)

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

        recipe = build_manager_recipe(config)

        supervisor_src = recipe.variables.get("supervisor_content")
        assert supervisor_src is not None
        assert supervisor_src.kind == VariableSourceKind.FILE
        assert supervisor_src.path == "supervisor/manager.md"
