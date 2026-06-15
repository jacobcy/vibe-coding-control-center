"""Tests for check-service label constraint enforcement side effects."""

from __future__ import annotations

import subprocess
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from vibe3.services.check.rule_checks import (
    CheckContext,
    rule_label_constraint_enforcement,
)
from vibe3.services.check.service import CheckService


def _enabled_sync_rules() -> SimpleNamespace:
    return SimpleNamespace(
        local=SimpleNamespace(
            label_constraint_enforcement=SimpleNamespace(enabled=True)
        )
    )


def _removed_labels(mock_run: MagicMock) -> list[str]:
    labels: list[str] = []
    for call in mock_run.call_args_list:
        cmd = call.args[0]
        if "--remove-label" not in cmd:
            continue
        labels.append(cmd[cmd.index("--remove-label") + 1])
    return labels


def test_rule_scanned_state_with_assignee_removes_only_scanned() -> None:
    """state/* wins over orchestra-scanned when an assignee exists."""
    ctx = CheckContext(
        branch="task/issue-123",
        flow_data={},
        flow_status="active",
        is_active_flow=True,
        task_issue=123,
        task_issue_closed=False,
        orchestration_state=None,
        issue_payload={"assignees": [{"login": "agent"}]},
        issue_labels=["state/ready", "orchestra-scanned"],
        issue_labels_loaded=True,
        branch_missing=False,
    )
    svc = SimpleNamespace(_sync_rules=_enabled_sync_rules())

    with patch("subprocess.run") as mock_run, patch("time.sleep"):
        mock_run.return_value = subprocess.CompletedProcess([], 0, "", "")
        result = rule_label_constraint_enforcement(ctx, svc)

    assert result is not None
    assert _removed_labels(mock_run) == ["orchestra-scanned"]


def test_rule_label_fix_failure_is_reported_as_error() -> None:
    """A failed GitHub label mutation should be visible in error logs."""
    ctx = CheckContext(
        branch="task/issue-123",
        flow_data={},
        flow_status="active",
        is_active_flow=True,
        task_issue=123,
        task_issue_closed=False,
        orchestration_state=None,
        issue_payload={"assignees": [{"login": "agent"}]},
        issue_labels=["state/ready", "orchestra-scanned"],
        issue_labels_loaded=True,
        branch_missing=False,
    )
    svc = SimpleNamespace(_sync_rules=_enabled_sync_rules())

    with (
        patch("subprocess.run") as mock_run,
        patch("vibe3.services.check.rule_checks.logger") as mock_logger,
    ):
        mock_run.side_effect = subprocess.CalledProcessError(
            1, ["gh"], stderr="api unavailable"
        )
        result = rule_label_constraint_enforcement(ctx, svc)

    assert result is None
    mock_logger.bind.return_value.error.assert_called_once()


def test_remote_scan_covers_state_labels_without_assignee() -> None:
    """Remote enforcement catches no-assignee state/* issues."""
    github = MagicMock()

    def list_issues(*, label: str, **kwargs):
        if label == "state/ready":
            return [
                {
                    "number": 123,
                    "labels": [{"name": "state/ready"}],
                    "assignees": [],
                }
            ]
        return []

    github.list_issues.side_effect = list_issues
    service = CheckService(github_client=github)

    with patch("subprocess.run") as mock_run, patch("time.sleep"):
        mock_run.return_value = subprocess.CompletedProcess([], 0, "", "")
        fixed = service.enforce_label_constraints_remote()

    assert fixed == 1
    assert _removed_labels(mock_run) == ["state/ready"]
    queried_labels = {
        call.kwargs["label"] for call in github.list_issues.call_args_list
    }
    assert "orchestra-scanned" in queried_labels
    assert "state/ready" in queried_labels


def test_remote_scanned_state_with_assignee_removes_only_scanned() -> None:
    """Remote enforcement keeps valid state/* labels on scanned conflicts."""
    github = MagicMock()

    def list_issues(*, label: str, **kwargs):
        if label == "orchestra-scanned":
            return [
                {
                    "number": 123,
                    "labels": [
                        {"name": "state/ready"},
                        {"name": "orchestra-scanned"},
                    ],
                    "assignees": [{"login": "agent"}],
                }
            ]
        return []

    github.list_issues.side_effect = list_issues
    service = CheckService(github_client=github)

    with patch("subprocess.run") as mock_run, patch("time.sleep"):
        mock_run.return_value = subprocess.CompletedProcess([], 0, "", "")
        fixed = service.enforce_label_constraints_remote()

    assert fixed == 1
    assert _removed_labels(mock_run) == ["orchestra-scanned"]
