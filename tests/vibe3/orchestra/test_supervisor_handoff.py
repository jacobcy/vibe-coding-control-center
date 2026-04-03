"""Tests for SupervisorHandoffService."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from vibe3.agents.backends.codeagent import AsyncExecutionHandle
from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.services.supervisor_handoff import (
    SupervisorHandoffIssue,
    SupervisorHandoffService,
)


@pytest.fixture
def service() -> tuple[SupervisorHandoffService, MagicMock, MagicMock]:
    github = MagicMock()
    backend = MagicMock()
    backend.start_async.return_value = AsyncExecutionHandle(
        tmux_session="vibe3-supervisor-issue-101",
        log_path=Path("temp/logs/vibe3-supervisor-issue-101.async.log"),
        prompt_file_path=Path("/tmp/prompt.md"),
    )
    executor = ThreadPoolExecutor(max_workers=2)
    svc = SupervisorHandoffService(
        OrchestraConfig(dry_run=False, max_concurrent_flows=2),
        github=github,
        backend=backend,
        executor=executor,
    )
    try:
        yield svc, github, backend
    finally:
        executor.shutdown(wait=True)


def test_list_handoff_issues_filters_by_labels_only(
    service: tuple[SupervisorHandoffService, MagicMock, MagicMock],
) -> None:
    svc, github, _backend = service
    github.list_issues.return_value = [
        {
            "number": 101,
            "title": "cleanup: stale flows",
            "labels": [{"name": "supervisor"}, {"name": "state/handoff"}],
        },
        {
            "number": 102,
            "title": "cleanup: missing handoff state",
            "labels": [{"name": "supervisor"}],
        },
        {
            "number": 103,
            "title": "roadmap: reorder milestones",
            "labels": [{"name": "supervisor"}, {"name": "state/handoff"}],
        },
    ]

    issues = svc._list_handoff_issues()

    assert issues == [
        SupervisorHandoffIssue(
            number=101,
            title="cleanup: stale flows",
        ),
        SupervisorHandoffIssue(
            number=103,
            title="roadmap: reorder milestones",
        ),
    ]


def test_process_issue_dispatches_apply_supervisor_async(
    service: tuple[SupervisorHandoffService, MagicMock, MagicMock],
) -> None:
    svc, github, backend = service
    svc._render_supervisor_prompt = MagicMock(return_value="# plan")  # type: ignore[method-assign]

    svc._process_issue(
        SupervisorHandoffIssue(
            number=101,
            title="cleanup: stale flows",
        )
    )

    backend.start_async.assert_called_once()
    kwargs = backend.start_async.call_args.kwargs
    assert kwargs["execution_name"] == "vibe3-supervisor-issue-101"
    assert kwargs["task"].startswith("Process governance issue #101")
    assert "same issue" in kwargs["task"]
    github.add_comment.assert_not_called()
    github.close_issue.assert_not_called()


def test_process_issue_uses_configured_apply_supervisor(
    service: tuple[SupervisorHandoffService, MagicMock, MagicMock],
) -> None:
    svc, _github, _backend = service
    svc._render_supervisor_prompt = MagicMock(return_value="# plan")  # type: ignore[method-assign]
    svc._process_issue(
        SupervisorHandoffIssue(
            number=101,
            title="cleanup: stale flows",
        )
    )

    svc._render_supervisor_prompt.assert_called_once_with("supervisor/apply.md")
