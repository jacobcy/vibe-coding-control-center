"""Tests for LabelService."""

import pytest

from vibe3.exceptions import SystemError
from vibe3.models.orchestration import IssueState
from vibe3.models.state_machine import VIBE_TASK_LABEL
from vibe3.services.shared.label_service import LabelService


class FakeIssuePort:
    """In-memory issue label port for unit tests."""

    def __init__(self, labels: dict[int, list[str]] | None = None) -> None:
        self.labels: dict[int, list[str]] = labels or {}
        self.fail_add = False
        self.fail_remove = False
        self.fail_get = False
        self.fail_ensure = False
        self.repo_labels: set[str] = set()
        self.operations: list[tuple[str, str]] = []

    def get_issue_labels(self, issue_number: int) -> list[str] | None:
        if self.fail_get:
            return None
        return list(self.labels.get(issue_number, []))

    def add_issue_label(self, issue_number: int, label: str) -> bool:
        self.operations.append(("add", label))
        if self.fail_add:
            return False
        labels = self.labels.setdefault(issue_number, [])
        if label not in labels:
            labels.append(label)
        return True

    def remove_issue_label(self, issue_number: int, label: str) -> bool:
        self.operations.append(("remove", label))
        if self.fail_remove:
            return False
        labels = self.labels.setdefault(issue_number, [])
        if label in labels:
            labels.remove(label)
        return True

    def ensure_label_exists(
        self,
        label: str,
        *,
        color: str,
        description: str,
    ) -> bool:
        del color, description
        if self.fail_ensure:
            return False
        self.repo_labels.add(label)
        return True


def test_get_state_returns_highest_priority_label_when_multiple_exist() -> None:
    """Regression: stale lower-priority label must not be picked as 'current'.

    GitHub label list order is not guaranteed to reflect application order,
    so get_state() must resolve ties by STATE_PRIORITY_ORDER, not by
    iteration order. Otherwise confirm_issue_state() can short-circuit on a
    stale label and leave it stuck forever (see issue #3182: state/in-progress
    persisted while state/handoff toggled around it).
    """
    # handoff listed first, but in-progress outranks it in STATE_PRIORITY_ORDER
    port = FakeIssuePort({123: ["state/handoff", "state/in-progress"]})
    service = LabelService(issue_port=port)

    assert service.get_state(123) == IssueState.IN_PROGRESS


def test_confirm_issue_state_cleans_up_stale_label_when_multiple_exist() -> None:
    """confirm_issue_state must not short-circuit on a stale non-priority label."""
    port = FakeIssuePort({123: ["state/handoff", "state/in-progress"]})
    service = LabelService(issue_port=port)

    result = service.confirm_issue_state(123, IssueState.HANDOFF, actor="agent:run")

    assert result == "advanced"
    assert port.labels[123] == ["state/handoff"]


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
    assert "state/claimed" in port.repo_labels


def test_confirm_issue_state_returns_blocked_on_forbidden_transition() -> None:
    port = FakeIssuePort({123: ["state/ready"]})
    service = LabelService(issue_port=port)

    result = service.confirm_issue_state(123, IssueState.DONE, actor="agent:done")

    assert result == "blocked"
    assert port.labels[123] == ["state/ready"]


def test_confirm_issue_state_creates_missing_target_label() -> None:
    port = FakeIssuePort({123: ["state/claimed"]})
    service = LabelService(issue_port=port)

    result = service.confirm_issue_state(123, IssueState.BLOCKED, actor="agent:manager")

    assert result == "advanced"
    assert port.labels[123] == ["state/blocked"]
    assert "state/blocked" in port.repo_labels


def test_confirm_issue_state_blocked_to_handoff_requires_force() -> None:
    """BLOCKED -> HANDOFF is forbidden (requires force=True via resume)."""
    port = FakeIssuePort({123: ["state/blocked"]})
    service = LabelService(issue_port=port)

    result = service.confirm_issue_state(123, IssueState.HANDOFF, actor="agent:manager")

    assert result == "blocked"
    assert port.labels[123] == ["state/blocked"]


def test_confirm_issue_state_keeps_old_label_when_add_fails() -> None:
    port = FakeIssuePort({123: ["state/claimed"]})
    port.fail_add = True
    service = LabelService(issue_port=port)

    result = service.confirm_issue_state(123, IssueState.BLOCKED, actor="agent:manager")

    assert result == "blocked"
    assert port.labels[123] == ["state/claimed"]


def test_confirm_issue_state_returns_blocked_when_ensure_fails() -> None:
    port = FakeIssuePort({123: ["state/claimed"]})
    port.fail_ensure = True
    service = LabelService(issue_port=port)

    result = service.confirm_issue_state(123, IssueState.BLOCKED, actor="agent:manager")

    assert result == "blocked"
    assert port.labels[123] == ["state/claimed"]


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


def test_replace_issue_state_normalizes_duplicate_labels() -> None:
    port = FakeIssuePort({123: ["state/in-progress", "state/handoff", "type/feature"]})
    service = LabelService(issue_port=port)

    result = service.replace_issue_state(
        123,
        IssueState.IN_PROGRESS,
        actor="recovery:resume",
    )

    assert result == "normalized"
    assert port.labels[123] == ["state/in-progress", "type/feature"]
    assert port.operations.index(("add", "state/in-progress")) < port.operations.index(
        ("remove", "state/handoff")
    )


def test_replace_issue_state_confirms_single_target_without_writes() -> None:
    port = FakeIssuePort({123: ["state/in-progress", "type/feature"]})
    service = LabelService(issue_port=port)

    result = service.replace_issue_state(
        123,
        IssueState.IN_PROGRESS,
        actor="recovery:resume",
    )

    assert result == "confirmed"
    assert port.operations == []


def test_replace_issue_state_fails_closed_when_labels_unreadable() -> None:
    port = FakeIssuePort({123: ["state/blocked"]})
    port.fail_get = True
    service = LabelService(issue_port=port)

    with pytest.raises(SystemError, match="read state labels"):
        service.replace_issue_state(
            123,
            IssueState.IN_PROGRESS,
            actor="recovery:resume",
        )

    assert port.operations == []
