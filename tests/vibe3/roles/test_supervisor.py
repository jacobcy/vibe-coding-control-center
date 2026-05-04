"""Tests for supervisor role module functions."""

from unittest.mock import MagicMock, patch

from vibe3.domain.events.supervisor_apply import SupervisorIssueIdentified
from vibe3.execution.role_contracts import WorktreeRequirement
from vibe3.models.orchestra_config import OrchestraConfig, SupervisorHandoffConfig
from vibe3.roles.supervisor import (
    SUPERVISOR_APPLY_ROLE,
    SUPERVISOR_IDENTIFY_ROLE,
    build_supervisor_apply_request,
    build_supervisor_handoff_payload,
    build_supervisor_task_string,
    iter_supervisor_identified_events,
)


def _make_config(**overrides) -> OrchestraConfig:
    handoff_defaults = dict(
        prompt_template="orchestra.supervisor.apply",
    )
    handoff_overrides = overrides.pop("supervisor_handoff", {})
    return OrchestraConfig(
        supervisor_handoff=SupervisorHandoffConfig(
            **{**handoff_defaults, **handoff_overrides}
        ),
        **overrides,
    )


class TestSupervisorRoleDefinitions:
    """Tests for supervisor role constants."""

    def test_identify_role(self):
        assert SUPERVISOR_IDENTIFY_ROLE.name == "supervisor-identify"
        assert SUPERVISOR_IDENTIFY_ROLE.registry_role == "supervisor"
        assert SUPERVISOR_IDENTIFY_ROLE.worktree == WorktreeRequirement.NONE

    def test_apply_role(self):
        assert SUPERVISOR_APPLY_ROLE.name == "supervisor-apply"
        assert SUPERVISOR_APPLY_ROLE.registry_role == "supervisor"
        assert SUPERVISOR_APPLY_ROLE.worktree == WorktreeRequirement.TEMPORARY


class TestBuildSupervisorTaskString:
    """Tests for build_supervisor_task_string."""

    def test_basic_task(self):
        config = _make_config()
        task = build_supervisor_task_string(config, 42)
        assert "#42" in task
        # supervisor_file no longer in task string after migration
        assert "supervisor material" in task

    def test_with_title(self):
        config = _make_config()
        task = build_supervisor_task_string(config, 42, "Fix docs")
        assert "Fix docs" in task
        assert "#42" in task

    def test_repo_hint(self):
        config = _make_config(repo="org/repo")
        task = build_supervisor_task_string(config, 42)
        assert "org/repo" in task


class TestBuildSupervisorHandoffPayload:
    """Tests for build_supervisor_handoff_payload."""

    def test_returns_tuple(self):
        """After migration, supervisor handoff returns rendered prompt."""
        config = _make_config()
        prompt, options, task = build_supervisor_handoff_payload(
            config, 42, "Test issue"
        )
        # Prompt is now rendered from recipe, not mocked
        assert prompt is not None
        assert len(prompt) > 0
        assert options is not None
        assert "#42" in task
        assert "Test issue" in task

    def test_uses_supervisor_recipe(self, tmp_path, monkeypatch):
        """After migration, supervisor handoff uses direct recipe."""
        from vibe3.prompts import manifest

        # Create recipe for supervisor handoff
        recipes_path = tmp_path / "prompt-recipes.yaml"
        recipes_path.write_text(
            """
recipes:
  supervisor.handoff:
    kind: template_recipe
    template_key: orchestra.supervisor.apply
    variables:
      supervisor_name:
        kind: literal
        value: supervisor/apply.md
      supervisor_content:
        kind: literal
        value: "APPLY BODY"
      server_status:
        kind: literal
        value: running
      active_count:
        kind: literal
        value: "0"
      active_flows:
        kind: literal
        value: "0"
      active_worktrees:
        kind: literal
        value: "0"
      running_issue_count:
        kind: literal
        value: "0"
      queued_issue_count:
        kind: literal
        value: "0"
      suggested_issue_count:
        kind: literal
        value: "0"
      circuit_breaker_state:
        kind: literal
        value: closed
      circuit_breaker_failures:
        kind: literal
        value: "0"
      issue_list:
        kind: literal
        value: ""
      running_issue_details:
        kind: literal
        value: ""
      suggested_issue_details:
        kind: literal
        value: ""
      truncated_note:
        kind: literal
        value: ""
""",
            encoding="utf-8",
        )

        prompts_path = tmp_path / "prompts.yaml"
        prompts_path.write_text(
            """
orchestra:
  supervisor:
    apply: |
      Supervisor: {supervisor_name}
      Content: {supervisor_content}
      Status: {server_status}
""",
            encoding="utf-8",
        )

        monkeypatch.setattr(manifest, "DEFAULT_PROMPT_RECIPES_PATH", recipes_path)

        config = _make_config(
            supervisor_handoff={"prompt_template": "orchestra.supervisor.apply"}
        )
        prompt, _options, _task = build_supervisor_handoff_payload(
            config, 42, "Test issue", prompts_path=prompts_path
        )

        assert "APPLY BODY" in prompt


class TestBuildSupervisorApplyRequest:
    """Tests for build_supervisor_apply_request."""

    @patch("vibe3.roles.supervisor.resolve_supervisor_agent_options")
    def test_request_structure(self, mock_opts):
        mock_opts.return_value = MagicMock()
        config = _make_config()
        req = build_supervisor_apply_request(config, 42, "Fix docs")
        assert req.role == "supervisor"
        assert req.target_branch == "issue-42"
        assert req.target_id == 42
        # cwd is not set — coordinator resolves it via worktree_requirement=TEMPORARY
        assert req.cwd is None
        assert req.mode == "async"
        assert req.worktree_requirement == WorktreeRequirement.TEMPORARY

    @patch("vibe3.roles.supervisor.resolve_supervisor_agent_options")
    def test_env_has_async_child(self, mock_opts):
        mock_opts.return_value = MagicMock()
        config = _make_config()
        req = build_supervisor_apply_request(config, 42)
        assert req.env is not None
        assert req.env.get("VIBE3_ASYNC_CHILD") == "1"


class TestSupervisorIdentifiedEvents:
    """Supervisor observation filtering should stay in role layer."""

    def test_iter_supervisor_identified_events_filters_matching_labels(self):
        config = _make_config(
            repo="owner/repo",
            supervisor_handoff={
                "issue_label": "supervisor",
                "handoff_state_label": "state/handoff",
                "supervisor_file": "supervisor/apply.md",
            },
        )

        events = iter_supervisor_identified_events(
            config,
            [
                {
                    "number": 1,
                    "title": "match",
                    "labels": [{"name": "supervisor"}, {"name": "state/handoff"}],
                },
                {
                    "number": 2,
                    "title": "skip",
                    "labels": [{"name": "supervisor"}],
                },
            ],
        )

        assert len(events) == 1
        assert isinstance(events[0], SupervisorIssueIdentified)
        assert events[0].issue_number == 1
        assert events[0].issue_title == "match"
