"""Tests for issue-scoped role sync/async runner behavior."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from vibe3.execution.issue_role_sync_runner import (
    run_issue_role_async,
    run_issue_role_sync,
)
from vibe3.models import (
    AgentOptions,
    ExecutionLaunchResult,
    ExecutionRequest,
    IssueInfo,
)
from vibe3.roles.definitions import IssueRoleSyncSpec


class _FakeCapacity:
    def can_dispatch(self, _role: str) -> bool:
        return True


class _FakeCoordinator:
    requests: list[ExecutionRequest] = []

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        self.capacity = _FakeCapacity()

    def dispatch_execution(self, request: ExecutionRequest) -> ExecutionLaunchResult:
        self.requests.append(request)
        return ExecutionLaunchResult(launched=True)


class _FakeStore:
    def get_flow_state(self, branch: str) -> dict[str, object]:
        return {"branch": branch}

    def add_event(self, *_args: Any, **_kwargs: Any) -> None:
        return None


def _patch_runner_boundaries(monkeypatch) -> None:
    _FakeCoordinator.requests = []
    monkeypatch.setattr(
        "vibe3.execution.issue_role_sync_runner.resolve_orchestra_repo_root",
        lambda: "/repo",
    )
    monkeypatch.setattr(
        "vibe3.execution.issue_role_sync_runner.load_orchestra_config",
        lambda **_kwargs: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "vibe3.execution.issue_role_sync_runner.load_issue_info",
        lambda issue_number, config: IssueInfo(number=issue_number, title="Issue"),
    )
    monkeypatch.setattr(
        "vibe3.execution.issue_role_sync_runner.SQLiteClient",
        lambda: _FakeStore(),
    )
    monkeypatch.setattr(
        "vibe3.execution.issue_role_sync_runner.CodeagentBackend",
        lambda: object(),
    )
    monkeypatch.setattr(
        "vibe3.execution.issue_role_sync_runner.ExecutionCoordinator",
        _FakeCoordinator,
    )
    monkeypatch.setattr(
        "vibe3.execution.issue_role_sync_runner.resolve_branch_arg",
        lambda value: f"resolved/{value}",
    )
    monkeypatch.setattr(
        "vibe3.execution.issue_role_sync_runner.record_dispatch_failure_if_unexpected",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        "vibe3.execution.issue_role_sync_runner.format_agent_actor",
        lambda _options: "agent:test",
    )


def test_async_runner_passes_resolved_branch_to_async_request(monkeypatch) -> None:
    _patch_runner_boundaries(monkeypatch)
    seen: dict[str, str] = {}

    def build_async_request(
        _config: object,
        issue: IssueInfo,
        _actor: str,
        branch: str,
    ) -> ExecutionRequest:
        seen["branch"] = branch
        return ExecutionRequest(
            role="reviewer",
            target_branch=branch,
            target_id=issue.number,
            execution_name="reviewer",
            cmd=["vibe3", "review", "--branch", branch, "--no-async"],
        )

    spec = IssueRoleSyncSpec(
        role_name="reviewer",
        resolve_options=lambda _config, _cli_overrides=None: AgentOptions(),
        resolve_branch=lambda _store, _issue, _current: "unused",
        build_async_request=build_async_request,
        build_sync_request=lambda *_args: None,  # type: ignore[arg-type]
    )

    run_issue_role_async(
        issue_number=2058,
        dry_run=False,
        spec=spec,
        branch="2058",
        agent="reviewer-fast",
        backend="codex",
        model="gpt-5.4",
        fresh_session=True,
    )

    assert seen["branch"] == "resolved/2058"
    assert _FakeCoordinator.requests[0].target_branch == "resolved/2058"
    assert _FakeCoordinator.requests[0].cmd == [
        "vibe3",
        "review",
        "--branch",
        "resolved/2058",
        "--no-async",
        "--agent",
        "reviewer-fast",
        "--backend",
        "codex",
        "--model",
        "gpt-5.4",
        "--fresh-session",
    ]


def test_sync_runner_applies_cli_overrides_to_resolved_options(monkeypatch) -> None:
    _patch_runner_boundaries(monkeypatch)
    monkeypatch.setattr(
        "vibe3.execution.issue_role_sync_runner.load_session_id",
        lambda _role, branch=None: "session-1",
    )

    def resolve_options(_config: object, cli_overrides: dict[str, str] | None = None):
        assert cli_overrides == {
            "review.agent_config.backend": "codex",
            "review.agent_config.model": "gpt-5.4",
            "review.agent_config.agent": "reviewer-fast",
        }
        return AgentOptions(agent="reviewer-fast", backend=None, model=None)

    def build_sync_request(
        _config: object,
        issue: IssueInfo,
        branch: str,
        _flow_state: dict[str, object] | None,
        _session_id: str | None,
        options: AgentOptions,
        _actor: str,
        _dry_run: bool,
        _show_prompt: bool,
    ) -> ExecutionRequest:
        return ExecutionRequest(
            role="reviewer",
            target_branch=branch,
            target_id=issue.number,
            execution_name="reviewer",
            options=options,
            mode="sync",
        )

    spec = IssueRoleSyncSpec(
        role_name="reviewer",
        resolve_options=resolve_options,
        resolve_branch=lambda _store, _issue, _current: "unused",
        build_async_request=lambda *_args: None,
        build_sync_request=build_sync_request,
    )

    run_issue_role_sync(
        issue_number=2023,
        dry_run=True,
        fresh_session=False,
        show_prompt=False,
        spec=spec,
        branch="2023",
        agent="reviewer-fast",
        backend="codex",
        model="gpt-5.4",
    )

    assert _FakeCoordinator.requests[0].options == AgentOptions(
        agent="reviewer-fast",
        backend=None,
        model=None,
    )
