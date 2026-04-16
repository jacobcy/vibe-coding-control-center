"""Tests for orchestration models."""

from vibe3.models.orchestration import (
    ALLOWED_TRANSITIONS,
    FORBIDDEN_TRANSITIONS,
    IssueState,
    StateTransition,
)


class TestIssueState:
    """Tests for IssueState enum."""

    def test_all_states_defined(self):
        """Test that all expected states are defined."""
        assert IssueState.READY == "ready"
        assert IssueState.CLAIMED == "claimed"
        assert IssueState.IN_PROGRESS == "in-progress"
        assert IssueState.BLOCKED == "blocked"
        assert IssueState.FAILED == "failed"
        assert IssueState.HANDOFF == "handoff"
        assert IssueState.REVIEW == "review"
        assert IssueState.MERGE_READY == "merge-ready"
        assert IssueState.DONE == "done"

    def test_to_label(self):
        """Test conversion to GitHub label."""
        assert IssueState.READY.to_label() == "state/ready"
        assert IssueState.IN_PROGRESS.to_label() == "state/in-progress"
        assert IssueState.DONE.to_label() == "state/done"

    def test_from_label_valid(self):
        """Test parsing from valid GitHub label."""
        assert IssueState.from_label("state/ready") == IssueState.READY
        assert IssueState.from_label("state/in-progress") == IssueState.IN_PROGRESS
        assert IssueState.from_label("state/done") == IssueState.DONE

    def test_from_label_invalid(self):
        """Test parsing from invalid label returns None."""
        assert IssueState.from_label("type/feature") is None
        assert IssueState.from_label("state/invalid") is None
        assert IssueState.from_label("ready") is None


class TestStateTransition:
    """Tests for StateTransition model."""

    def test_create_transition(self):
        """Test creating a state transition."""
        transition = StateTransition(
            issue_number=123,
            from_state=IssueState.READY,
            to_state=IssueState.CLAIMED,
            actor="agent:plan",
        )
        assert transition.issue_number == 123
        assert transition.from_state == IssueState.READY
        assert transition.to_state == IssueState.CLAIMED
        assert transition.actor == "agent:plan"
        assert transition.forced is False

    def test_transition_with_none_from_state(self):
        """Test transition with None from_state (initial state)."""
        transition = StateTransition(
            issue_number=123,
            from_state=None,
            to_state=IssueState.READY,
            actor="flow:new",
        )
        assert transition.from_state is None
        assert transition.to_state == IssueState.READY

    def test_forced_transition(self):
        """Test forced transition flag."""
        transition = StateTransition(
            issue_number=123,
            from_state=IssueState.READY,
            to_state=IssueState.DONE,
            actor="admin",
            forced=True,
        )
        assert transition.forced is True


class TestTransitionRules:
    """Tests for state transition rules."""

    def test_allowed_transitions_count(self):
        """Test that we have expected number of allowed transitions.

        Fixed Issue #303: Removed BLOCKED→CLAIMED and BLOCKED→HANDOFF (2 transitions)
        Added: MERGE_READY→IN_PROGRESS (commit+PR), HANDOFF→DONE (manager concludes)
        Replaced: MERGE_READY→DONE (now goes through commit+PR flow)
        """
        assert len(ALLOWED_TRANSITIONS) == 22

    def test_main_chain_transitions_allowed(self):
        """Test that main chain transitions are allowed."""
        assert (IssueState.READY, IssueState.CLAIMED) in ALLOWED_TRANSITIONS
        assert (IssueState.CLAIMED, IssueState.HANDOFF) in ALLOWED_TRANSITIONS
        assert (IssueState.HANDOFF, IssueState.IN_PROGRESS) in ALLOWED_TRANSITIONS
        assert (IssueState.IN_PROGRESS, IssueState.HANDOFF) in ALLOWED_TRANSITIONS
        assert (IssueState.HANDOFF, IssueState.REVIEW) in ALLOWED_TRANSITIONS
        assert (IssueState.REVIEW, IssueState.HANDOFF) in ALLOWED_TRANSITIONS
        assert (IssueState.HANDOFF, IssueState.MERGE_READY) in ALLOWED_TRANSITIONS
        assert (IssueState.MERGE_READY, IssueState.IN_PROGRESS) in ALLOWED_TRANSITIONS
        assert (IssueState.HANDOFF, IssueState.DONE) in ALLOWED_TRANSITIONS

    def test_side_path_transitions_allowed(self):
        """Test that side path transitions are allowed.

        Fixed Issue #303: Removed BLOCKED→CLAIMED and BLOCKED→HANDOFF
        Blocked state requires manual intervention (force=True for resume)
        """
        # → blocked transitions (allowed)
        assert (IssueState.READY, IssueState.BLOCKED) in ALLOWED_TRANSITIONS
        assert (IssueState.CLAIMED, IssueState.BLOCKED) in ALLOWED_TRANSITIONS
        assert (IssueState.HANDOFF, IssueState.BLOCKED) in ALLOWED_TRANSITIONS
        assert (IssueState.IN_PROGRESS, IssueState.BLOCKED) in ALLOWED_TRANSITIONS
        assert (IssueState.REVIEW, IssueState.BLOCKED) in ALLOWED_TRANSITIONS
        assert (IssueState.MERGE_READY, IssueState.BLOCKED) in ALLOWED_TRANSITIONS

        # blocked → other transitions (NOT allowed, removed)
        assert (IssueState.BLOCKED, IssueState.CLAIMED) not in ALLOWED_TRANSITIONS
        assert (IssueState.BLOCKED, IssueState.HANDOFF) not in ALLOWED_TRANSITIONS

        # failed transitions (allowed)
        assert (IssueState.CLAIMED, IssueState.FAILED) in ALLOWED_TRANSITIONS
        assert (IssueState.IN_PROGRESS, IssueState.FAILED) in ALLOWED_TRANSITIONS
        assert (IssueState.REVIEW, IssueState.FAILED) in ALLOWED_TRANSITIONS
        assert (IssueState.FAILED, IssueState.CLAIMED) in ALLOWED_TRANSITIONS
        assert (IssueState.FAILED, IssueState.HANDOFF) in ALLOWED_TRANSITIONS
        assert (IssueState.FAILED, IssueState.IN_PROGRESS) in ALLOWED_TRANSITIONS
        assert (IssueState.FAILED, IssueState.REVIEW) in ALLOWED_TRANSITIONS

    def test_closure_path_transitions_allowed(self):
        """Test that closure path transitions are allowed."""
        # MERGE_READY -> IN_PROGRESS (commit+PR), HANDOFF -> DONE (manager concludes)
        assert (IssueState.MERGE_READY, IssueState.IN_PROGRESS) in ALLOWED_TRANSITIONS
        assert (IssueState.HANDOFF, IssueState.DONE) in ALLOWED_TRANSITIONS
        # Direct MERGE_READY -> DONE no longer allowed (goes through commit+PR flow)
        assert (IssueState.MERGE_READY, IssueState.DONE) not in ALLOWED_TRANSITIONS
        assert (IssueState.READY, IssueState.DONE) not in ALLOWED_TRANSITIONS

    def test_forbidden_transitions_count(self):
        """Test that we have expected number of forbidden transitions."""
        assert len(FORBIDDEN_TRANSITIONS) == 5

    def test_skip_to_done_forbidden(self):
        """Test that skipping to done is forbidden."""
        # All states except HANDOFF cannot jump directly to DONE
        assert (IssueState.READY, IssueState.DONE) in FORBIDDEN_TRANSITIONS
        assert (IssueState.CLAIMED, IssueState.DONE) in FORBIDDEN_TRANSITIONS
        assert (IssueState.BLOCKED, IssueState.DONE) in FORBIDDEN_TRANSITIONS
        assert (IssueState.FAILED, IssueState.DONE) in FORBIDDEN_TRANSITIONS
        assert (IssueState.MERGE_READY, IssueState.DONE) in FORBIDDEN_TRANSITIONS

    def test_allowed_not_in_forbidden(self):
        """Test that allowed transitions are not in forbidden set."""
        for transition in ALLOWED_TRANSITIONS:
            assert transition not in FORBIDDEN_TRANSITIONS
