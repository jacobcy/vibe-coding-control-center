"""Fail-closed resume normalization regressions."""

from pathlib import Path

import pytest

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.exceptions import SystemError
from vibe3.models import IssueState
from vibe3.services.flow.blocked_state_service import BlockedStateService


class StubGitHubClient:
    def __init__(self, issue_body: str) -> None:
        self.issue_body = issue_body

    def get_issue_body(self, issue_number: int) -> str | None:
        return self.issue_body

    def update_issue_body(self, issue_number: int, body: str) -> bool:
        self.issue_body = body
        return True


class FailingNormalizeLabelService:
    def get_state(self, issue_number: int) -> IssueState:
        return IssueState.BLOCKED

    def replace_issue_state(
        self,
        issue_number: int,
        state: IssueState,
        *,
        actor: str,
    ) -> str:
        raise SystemError("normalize failed")


def test_resume_normalization_failure_keeps_body_and_cache_blocked(
    tmp_path: Path,
) -> None:
    store = SQLiteClient(db_path=str(tmp_path / "test.db"))
    branch = "task/issue-123"
    store.update_flow_state(branch, flow_slug="test", flow_status="blocked")
    blocked_body = (
        "<!-- vibe3-flow-state-start -->\n\n"
        "**Vibe3 Flow State**\n\n"
        "- **State**: blocked\n\n"
        "<!-- vibe3-flow-state-end -->"
    )
    github = StubGitHubClient(issue_body=blocked_body)
    service = BlockedStateService(
        store=store,
        github_client=github,  # type: ignore[arg-type]
        label_service=FailingNormalizeLabelService(),  # type: ignore[arg-type]
    )

    with pytest.raises(SystemError, match="normalize failed"):
        service.reconcile_blocked(123, branch)

    assert "- **State**: blocked" in (github.get_issue_body(123) or "")
    flow_state = store.get_flow_state(branch)
    assert flow_state is not None
    assert flow_state["flow_status"] == "blocked"
