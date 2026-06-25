"""Tests for supervisor role module functions."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from vibe3.config.convention_resolver import ConventionResolver
from vibe3.domain.events.supervisor_apply import SupervisorIssueIdentified
from vibe3.execution.role_contracts import WorktreeRequirement
from vibe3.models.adapter_manifest import AdapterManifest, AdapterResource
from vibe3.models.orchestra_config import OrchestraConfig, SupervisorHandoffConfig
from vibe3.roles.supervisor import (
    SUPERVISOR_APPLY_ROLE,
    SUPERVISOR_IDENTIFY_ROLE,
    build_supervisor_apply_request,
    build_supervisor_cli_request,
    build_supervisor_cli_sync_request,
    build_supervisor_task_string,
    get_supervisor_prompt_path,
    iter_supervisor_identified_events,
)


@pytest.fixture(autouse=True)
def clear_resolver_cache():
    """Clear resolver cache before each test to ensure fresh resolver."""
    from vibe3.config.convention_resolver import get_convention, get_resolver

    get_convention.cache_clear()
    get_resolver.cache_clear()
    yield
    # Clear after test as well
    get_convention.cache_clear()
    get_resolver.cache_clear()


def _get_adapter_for_profile(profile_config):
    """Return a focused adapter stub for supervisor profile lookup tests."""
    if profile_config.profile != "vibe-center":
        return None
    return AdapterManifest(
        name="vibe-center",
        version="3.0.0",
        description="Focused adapter stub for supervisor tests",
        resources=[
            AdapterResource(type="supervisor", name="apply", path="supervisor/apply.md")
        ],
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


class TestBuildSupervisorApplyRequest:
    """Tests for build_supervisor_apply_request."""

    @patch(
        "vibe3.execution.execution_role_policy.ExecutionRolePolicyService.resolve_effective_agent_options"
    )
    def test_request_structure(self, mock_opts):
        mock_opts.return_value = MagicMock()
        config = _make_config()
        req = build_supervisor_apply_request(config, 42, "Fix docs")
        assert req.role == "supervisor"
        assert req.target_branch == "task/issue-42"
        assert req.target_id == 42
        # cwd is not set — coordinator resolves it via worktree_requirement=TEMPORARY
        assert req.cwd is None
        assert req.mode == "async"
        assert req.worktree_requirement == WorktreeRequirement.TEMPORARY

    @patch(
        "vibe3.execution.execution_role_policy.ExecutionRolePolicyService.resolve_effective_agent_options"
    )
    def test_env_has_async_child(self, mock_opts):
        mock_opts.return_value = MagicMock()
        config = _make_config()
        req = build_supervisor_apply_request(config, 42)
        assert req.env is not None
        assert req.env.get("VIBE3_ASYNC_CHILD") == "1"


class TestBuildSupervisorCliRequest:
    """Tests for build_supervisor_cli_request (async CLI invocation)."""

    @patch(
        "vibe3.execution.execution_role_policy.ExecutionRolePolicyService.resolve_effective_agent_options"
    )
    def test_cli_request_uses_temporary_worktree(self, mock_opts):
        """Async CLI invocation must use TEMPORARY worktree for isolation."""
        mock_opts.return_value = MagicMock()
        config = _make_config()
        req = build_supervisor_cli_request(config, 42, "Fix docs")
        assert req.worktree_requirement == WorktreeRequirement.TEMPORARY
        assert req.target_id == 42


class TestBuildSupervisorCliSyncRequest:
    """Tests for build_supervisor_cli_sync_request (sync CLI invocation)."""

    @patch(
        "vibe3.execution.execution_role_policy.ExecutionRolePolicyService.resolve_effective_agent_options"
    )
    def test_sync_request_uses_temporary_worktree_when_not_dry_run(self, mock_opts):
        """Sync execution path must use TEMPORARY worktree for isolation."""
        from vibe3.models import IssueInfo

        mock_opts.return_value = MagicMock()
        config = _make_config()
        issue = IssueInfo(number=42, title="Fix docs", labels=[])
        req = build_supervisor_cli_sync_request(
            config,
            issue,
            "task/issue-42",
            None,
            None,
            None,
            "cli",
            dry_run=False,
            show_prompt=False,
        )
        assert req.worktree_requirement == WorktreeRequirement.TEMPORARY

    @patch(
        "vibe3.execution.execution_role_policy.ExecutionRolePolicyService.resolve_effective_agent_options"
    )
    def test_sync_request_skips_worktree_when_dry_run(self, mock_opts):
        """Dry-run mode must not create a real worktree."""
        from vibe3.models import IssueInfo

        mock_opts.return_value = MagicMock()
        config = _make_config()
        issue = IssueInfo(number=42, title="Fix docs", labels=[])
        req = build_supervisor_cli_sync_request(
            config,
            issue,
            "task/issue-42",
            None,
            None,
            None,
            "cli",
            dry_run=True,
            show_prompt=False,
        )
        assert req.worktree_requirement == WorktreeRequirement.NONE


class TestSupervisorIdentifiedEvents:
    """Supervisor observation filtering should stay in role layer."""

    def test_iter_supervisor_identified_events_filters_matching_labels(self):
        config = _make_config(
            repo="owner/repo",
            supervisor_handoff={
                "issue_label": "supervisor",
                "handoff_state_label": "state/handoff",
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


def test_supervisor_uses_profile_resolution() -> None:
    """Test supervisor prompt path uses profile resolution."""
    # With vibe-center profile
    with patch(
        "vibe3.config.profile_config.ProfileConfig._get_adapter",
        _get_adapter_for_profile,
    ):
        resolver = ConventionResolver(profile="vibe-center")
        path = get_supervisor_prompt_path(resolver)
        resolver_minimal = ConventionResolver(profile="minimal")
        path_minimal = get_supervisor_prompt_path(resolver_minimal)

    assert path == "supervisor/apply.md"
    assert path_minimal is None
