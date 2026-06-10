"""Tests for domain state-machine rules."""

import pytest

from vibe3.exceptions import InvalidTransitionError
from vibe3.models.orchestration import IssueState
from vibe3.models.state_machine import can_transition, validate_transition


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


def test_validate_transition_blocked_to_handoff_forbidden() -> None:
    """blocked → handoff should be forbidden without force (Issue #303)."""
    with pytest.raises(InvalidTransitionError):
        validate_transition(IssueState.BLOCKED, IssueState.HANDOFF, force=False)


def test_validate_transition_blocked_to_handoff_allowed_with_force() -> None:
    """Manual resume commands can bypass blocked state with force=True."""
    validate_transition(IssueState.BLOCKED, IssueState.HANDOFF, force=True)
