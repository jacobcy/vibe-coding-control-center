"""Tests for supervisor handoff payload construction."""

from vibe3.roles.supervisor import build_supervisor_handoff_payload


class TestBuildSupervisorHandoffPayload:
    """Tests for build_supervisor_handoff_payload."""

    def _make_config(self, **overrides):
        from vibe3.models.orchestra_config import (
            OrchestraConfig,
            SupervisorHandoffConfig,
        )

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

    def test_returns_tuple(self):
        """After migration, supervisor handoff returns rendered prompt."""
        config = self._make_config()
        prompt, options, task = build_supervisor_handoff_payload(
            config, 42, "Test issue"
        )
        # Prompt is now rendered from recipe, not mocked
        assert prompt is not None
        assert len(prompt) > 0
        assert options is not None
        assert "#42" in task
        assert "Test issue" in task

    def test_default_recipe_renders_runtime_summary(self):
        """Default provider-backed recipe should render snapshot values."""
        config = self._make_config()
        prompt, _options, _task = build_supervisor_handoff_payload(
            config, 42, "Test issue"
        )

        assert "- Server: running" in prompt
        assert "- Running issues: 0" in prompt
        assert "- Suggested issues: 0" in prompt
        assert "- Active flows: 0" in prompt
        assert "- Circuit breaker: closed (failures=0)" in prompt

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

        config = self._make_config(
            supervisor_handoff={"prompt_template": "orchestra.supervisor.apply"}
        )
        prompt, _options, _task = build_supervisor_handoff_payload(
            config, 42, "Test issue", prompts_path=prompts_path
        )

        assert "APPLY BODY" in prompt

    def test_annotate_sections_wraps_prompt_with_markers(self, tmp_path, monkeypatch):
        """annotate_sections=True wraps prompt with section markers."""
        from vibe3.prompts import manifest

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
""",
            encoding="utf-8",
        )

        monkeypatch.setattr(manifest, "DEFAULT_PROMPT_RECIPES_PATH", recipes_path)

        config = self._make_config(
            supervisor_handoff={"prompt_template": "orchestra.supervisor.apply"}
        )

        # Test with annotate_sections=True
        prompt, _options, _task = build_supervisor_handoff_payload(
            config,
            42,
            "Test issue",
            prompts_path=prompts_path,
            annotate_sections=True,
        )

        # Verify section markers wrap the prompt
        assert "<!-- section:supervisor.handoff -->" in prompt
        assert "<!-- /section:supervisor.handoff -->" in prompt
        assert prompt.startswith("<!-- section:supervisor.handoff -->")
        assert prompt.endswith("<!-- /section:supervisor.handoff -->")

    def test_annotate_sections_false_no_markers(self, tmp_path, monkeypatch):
        """annotate_sections=False does not add section markers."""
        from vibe3.prompts import manifest

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
""",
            encoding="utf-8",
        )

        monkeypatch.setattr(manifest, "DEFAULT_PROMPT_RECIPES_PATH", recipes_path)

        config = self._make_config(
            supervisor_handoff={"prompt_template": "orchestra.supervisor.apply"}
        )

        # Test with annotate_sections=False (default)
        prompt, _options, _task = build_supervisor_handoff_payload(
            config,
            42,
            "Test issue",
            prompts_path=prompts_path,
            annotate_sections=False,
        )

        # Verify no section markers
        assert "<!-- section:supervisor.handoff -->" not in prompt
        assert "<!-- /section:supervisor.handoff -->" not in prompt
