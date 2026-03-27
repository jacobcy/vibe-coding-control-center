"""Tests for LabelService."""

from vibe3.models.orchestration import IssueState
from vibe3.services.label_service import VIBE_TASK_LABEL, LabelService


class FakeIssuePort:
    """In-memory issue label port for unit tests."""

    def __init__(self, labels: dict[int, list[str]] | None = None) -> None:
        self.labels: dict[int, list[str]] = labels or {}
        self.fail_add = False
        self.fail_remove = False
        self.fail_get = False

    def get_issue_labels(self, issue_number: int) -> list[str] | None:
        if self.fail_get:
            return None
        return list(self.labels.get(issue_number, []))

    def add_issue_label(self, issue_number: int, label: str) -> bool:
        if self.fail_add:
            return False
        labels = self.labels.setdefault(issue_number, [])
        if label not in labels:
            labels.append(label)
        return True

    def remove_issue_label(self, issue_number: int, label: str) -> bool:
        if self.fail_remove:
            return False
        labels = self.labels.setdefault(issue_number, [])
        if label in labels:
            labels.remove(label)
        return True


def test_confirm_issue_state_returns_confirmed_when_already_target() -> None:
    port = FakeIssuePort({123: ["state/in-progress"]})
    service = LabelService(issue_port=port)

    result = service.confirm_issue_state(123, IssueState.IN_PROGRESS, actor="agent:run")

    assert result == "confirmed"
    assert port.labels[123] == ["state/in-progress"]


def test_confirm_issue_state_returns_advanced_when_transition_applied() -> None:
    port = FakeIssuePort({123: ["state/ready"]})
    service = LabelService(issue_port=port)

    result = service.confirm_issue_state(123, IssueState.CLAIMED, actor="agent:plan")

    assert result == "advanced"
    assert port.labels[123] == ["state/claimed"]


def test_confirm_issue_state_returns_blocked_on_forbidden_transition() -> None:
    port = FakeIssuePort({123: ["state/ready"]})
    service = LabelService(issue_port=port)

    result = service.confirm_issue_state(123, IssueState.DONE, actor="agent:done")

    assert result == "blocked"
    assert port.labels[123] == ["state/ready"]


def test_confirm_vibe_task_add_confirmed_advanced_and_blocked() -> None:
    port = FakeIssuePort({123: []})
    service = LabelService(issue_port=port)

    result1 = service.confirm_vibe_task(123, should_exist=True)
    result2 = service.confirm_vibe_task(123, should_exist=True)
    port.fail_add = True
    port.labels[123].remove(VIBE_TASK_LABEL)
    result3 = service.confirm_vibe_task(123, should_exist=True)

    assert result1 == "advanced"
    assert result2 == "confirmed"
    assert result3 == "blocked"
