"""Tests for domain state-machine rules."""

import pytest

from vibe3.domain.state_machine import can_transition, validate_transition
from vibe3.exceptions import InvalidTransitionError
from vibe3.models.orchestration import IssueState


def test_can_transition_accepts_mainline_edge() -> None:
    assert can_transition(IssueState.READY, IssueState.CLAIMED) is True


def test_can_transition_rejects_forbidden_edge() -> None:
    assert can_transition(IssueState.READY, IssueState.DONE) is False


def test_validate_transition_raises_for_invalid_edge() -> None:
    with pytest.raises(InvalidTransitionError):
        validate_transition(IssueState.READY, IssueState.DONE)


def test_validate_transition_allows_missing_from_state() -> None:
    validate_transition(None, IssueState.READY)


def test_validate_transition_honors_force() -> None:
    validate_transition(IssueState.READY, IssueState.DONE, force=True)
