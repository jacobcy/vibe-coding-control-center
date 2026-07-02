"""Fail-closed resume normalization regressions."""

from pathlib import Path

import pytest

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.exceptions import SystemError
from vibe3.models import IssueState
from vibe3.services.flow.blocked_state_service import BlockedStateService


class StubGitHubClient:
    def __init__(self, issue_body: str, updated_at: str = "ts-1") -> None:
        self.issue_body = issue_body
        self._updated_at = updated_at

    def get_issue_body(self, issue_number: int) -> str | None:
        return self.issue_body

    def get_issue_snapshot(
        self, issue_number: int, repo: str | None = None
    ) -> tuple[str | None, str | None] | None:
        return (self.issue_body, self._updated_at)

    def update_issue_body(self, issue_number: int, body: str) -> bool:
        self.issue_body = body
        return True


class FailingNormalizeLabelService:
    def get_state(self, issue_number: int) -> IssueState:
        return IssueState.BLOCKED

    def confirm_issue_state(self, *args, **kwargs) -> str:
        return "confirmed"

    def replace_issue_state(
        self,
        issue_number: int,
        state: IssueState,
        *,
        actor: str,
    ) -> str:
        raise SystemError("normalize failed")


def test_apply_auto_resume_normalization_failure_keeps_body_blocked(
    tmp_path: Path,
) -> None:
    """When label normalization fails during apply_auto_resume, body stays blocked.

    The auto resume path uses force=True + normalize=True for label writes.
    If that fails (SystemError), the body projection must NOT be cleared —
    the flow stays authoritatively blocked.
    """
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

    decision = service.evaluate_auto_eligibility(123, branch)
    # No reason + no deps -> ELIGIBLE
    from vibe3.services.flow.blocked_state_types import AutoResumeVerdict

    assert decision.verdict == AutoResumeVerdict.ELIGIBLE

    with pytest.raises(SystemError, match="normalize failed"):
        service.apply_auto_resume(decision)

    # Body projection must remain blocked
    assert "- **State**: blocked" in (github.get_issue_body(123) or "")
    flow_state = store.get_flow_state(branch)
    assert flow_state is not None
    assert flow_state["flow_status"] == "blocked"
