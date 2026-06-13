"""Tests for label utility functions."""

from vibe3.clients import collect_label_anomalies
from vibe3.services.shared.labels import (
    classify_dispatch_eligibility,
    get_conflicting_states,
    get_highest_priority_state,
    get_state_labels,
    has_execution_state,
    has_manager_assignee,
    has_orchestra_governed,
    has_roadmap_conflict,
    has_roadmap_label,
    normalize_assignees,
    normalize_labels,
)


class TestHasManagerAssignee:
    """Tests for has_manager_assignee function."""

    def test_empty_manager_usernames_returns_true(self) -> None:
        """Empty manager list should allow all issues (no restriction)."""
        assert has_manager_assignee(["alice", "bob"], []) is True
        assert has_manager_assignee(["alice"], ()) is True
        assert has_manager_assignee([], []) is True

    def test_assignee_in_manager_list(self) -> None:
        """Issue with manager assignee should return True."""
        assert has_manager_assignee(["alice", "bob"], ["alice", "charlie"]) is True
        assert has_manager_assignee(["bob"], ["alice", "bob", "charlie"]) is True

    def test_assignee_not_in_manager_list(self) -> None:
        """Issue without manager assignee should return False."""
        assert has_manager_assignee(["dave", "eve"], ["alice", "bob"]) is False
        assert has_manager_assignee(["dave"], ["alice"]) is False

    def test_empty_assignees_with_managers_configured(self) -> None:
        """Unassigned issue with managers configured should return False."""
        assert has_manager_assignee([], ["alice", "bob"]) is False

    def test_tuple_manager_usernames(self) -> None:
        """Function should accept both list and tuple for manager_usernames."""
        assert has_manager_assignee(["alice"], ("alice", "bob")) is True
        assert has_manager_assignee(["charlie"], ("alice", "bob")) is False


class TestNormalizeLabels:
    """Tests for normalize_labels function."""

    def test_empty_list(self) -> None:
        """Empty list should return empty list."""
        assert normalize_labels([]) == []

    def test_dict_items(self) -> None:
        """Should extract 'name' field from dict items."""
        labels = [{"name": "bug"}, {"name": "enhancement"}, {"name": "wontfix"}]
        assert normalize_labels(labels) == ["bug", "enhancement", "wontfix"]

    def test_missing_name_field(self) -> None:
        """Should skip items without 'name' field."""
        labels = [{"name": "bug"}, {"id": 123}, {"name": "feature"}]
        assert normalize_labels(labels) == ["bug", "feature"]

    def test_non_dict_items(self) -> None:
        """Should preserve plain string items, skip non-string non-dict."""
        labels = [{"name": "bug"}, "not-a-dict", 123]
        assert normalize_labels(labels) == ["bug", "not-a-dict"]

    def test_non_list_input(self) -> None:
        """Non-list input should return empty list."""
        assert normalize_labels("not-a-list") == []
        assert normalize_labels(None) == []
        assert normalize_labels(123) == []


class TestNormalizeAssignees:
    """Tests for normalize_assignees function."""

    def test_empty_list(self) -> None:
        """Empty list should return empty list."""
        assert normalize_assignees([]) == []

    def test_dict_items(self) -> None:
        """Should extract 'login' field from dict items."""
        assignees = [{"login": "alice"}, {"login": "bob"}, {"login": "charlie"}]
        assert normalize_assignees(assignees) == ["alice", "bob", "charlie"]

    def test_missing_login_field(self) -> None:
        """Should skip items without 'login' field."""
        assignees = [{"login": "alice"}, {"id": 123}, {"login": "bob"}]
        assert normalize_assignees(assignees) == ["alice", "bob"]

    def test_empty_login(self) -> None:
        """Should skip items with empty login."""
        assignees = [{"login": "alice"}, {"login": ""}, {"login": "bob"}]
        assert normalize_assignees(assignees) == ["alice", "bob"]

    def test_non_dict_items(self) -> None:
        """Should skip non-dict items."""
        assignees = [{"login": "alice"}, "not-a-dict", 123]
        assert normalize_assignees(assignees) == ["alice"]

    def test_non_list_input(self) -> None:
        """Non-list input should return empty list."""
        assert normalize_assignees("not-a-list") == []
        assert normalize_assignees(None) == []
        assert normalize_assignees(123) == []


class TestHasRoadmapLabel:
    def test_rfc(self) -> None:
        assert has_roadmap_label(["roadmap/rfc"]) is True

    def test_epic(self) -> None:
        assert has_roadmap_label(["roadmap/epic"]) is True

    def test_both(self) -> None:
        assert has_roadmap_label(["roadmap/rfc", "roadmap/epic"]) is True

    def test_no_roadmap(self) -> None:
        assert has_roadmap_label(["bug", "state/ready"]) is False

    def test_empty(self) -> None:
        assert has_roadmap_label([]) is False


class TestHasRoadmapConflict:
    def test_rfc_with_state(self) -> None:
        assert has_roadmap_conflict(["roadmap/rfc", "state/claimed"]) is True

    def test_epic_with_multiple_states(self) -> None:
        assert (
            has_roadmap_conflict(["roadmap/epic", "state/blocked", "state/review"])
            is True
        )

    def test_rfc_without_state(self) -> None:
        assert has_roadmap_conflict(["roadmap/rfc"]) is False

    def test_state_without_roadmap(self) -> None:
        assert has_roadmap_conflict(["state/ready", "bug"]) is False

    def test_empty(self) -> None:
        assert has_roadmap_conflict([]) is False


class TestHasExecutionState:
    def test_in_progress(self) -> None:
        assert has_execution_state(["state/in-progress"]) is True

    def test_claimed(self) -> None:
        assert has_execution_state(["state/claimed"]) is True

    def test_merge_ready(self) -> None:
        assert has_execution_state(["state/merge-ready"]) is True

    def test_ready_is_not_execution(self) -> None:
        assert has_execution_state(["state/ready"]) is False

    def test_blocked_is_not_execution(self) -> None:
        assert has_execution_state(["state/blocked"]) is False

    def test_no_states(self) -> None:
        assert has_execution_state(["bug"]) is False


class TestHasOrchestraGoverned:
    def test_present(self) -> None:
        assert has_orchestra_governed(["orchestra-governed"]) is True

    def test_absent(self) -> None:
        assert has_orchestra_governed(["state/ready"]) is False

    def test_empty(self) -> None:
        assert has_orchestra_governed([]) is False


class TestGetStateLabels:
    def test_multiple(self) -> None:
        result = get_state_labels(["bug", "state/ready", "state/blocked"])
        assert result == ["state/ready", "state/blocked"]

    def test_none(self) -> None:
        assert get_state_labels(["bug", "enhancement"]) == []

    def test_empty(self) -> None:
        assert get_state_labels([]) == []


class TestGetHighestPriorityState:
    def test_blocked_wins(self) -> None:
        assert (
            get_highest_priority_state(["state/review", "state/blocked"])
            == "state/blocked"
        )

    def test_single_state(self) -> None:
        assert get_highest_priority_state(["state/ready"]) == "state/ready"

    def test_done_beats_in_progress(self) -> None:
        assert (
            get_highest_priority_state(["state/in-progress", "state/done"])
            == "state/done"
        )

    def test_no_states(self) -> None:
        assert get_highest_priority_state([]) is None

    def test_unknown_only(self) -> None:
        assert get_highest_priority_state(["state/new-future"]) is None


class TestGetConflictingStates:
    def test_keeps_blocked_removes_others(self) -> None:
        result = get_conflicting_states(["state/blocked", "state/review"])
        assert result == ["state/review"]

    def test_single_state_no_conflict(self) -> None:
        assert get_conflicting_states(["state/ready"]) == []

    def test_no_states(self) -> None:
        assert get_conflicting_states([]) == []

    def test_keeps_done(self) -> None:
        result = get_conflicting_states(
            ["state/done", "state/ready", "state/in-progress"]
        )
        assert set(result) == {"state/ready", "state/in-progress"}


class TestClassifyDispatchEligibility:
    def _call(self, labels, assignees, **kwargs):
        defaults = dict(supervisor_label="supervisor", manager_usernames=("mgr",))
        defaults.update(kwargs)
        return classify_dispatch_eligibility(labels, assignees, **defaults)

    def test_ready_manager_is_dispatchable(self) -> None:
        assert self._call(["state/ready"], ["mgr"]) == []

    def test_missing_state_label(self) -> None:
        reasons = self._call([], ["mgr"])
        codes = [r.code for r in reasons]
        assert "missing_state_label" in codes

    def test_blocked_state(self) -> None:
        reasons = self._call(["state/blocked"], ["mgr"])
        codes = [r.code for r in reasons]
        assert "blocked_state" in codes

    def test_roadmap_rfc(self) -> None:
        reasons = self._call(["state/ready", "roadmap/rfc"], ["mgr"])
        codes = [r.code for r in reasons]
        assert "roadmap_rfc" in codes

    def test_roadmap_epic(self) -> None:
        reasons = self._call(["roadmap/epic", "state/ready"], ["mgr"])
        codes = [r.code for r in reasons]
        assert "roadmap_epic" in codes

    def test_supervisor_issue(self) -> None:
        reasons = self._call(["state/ready", "supervisor"], ["mgr"])
        codes = [r.code for r in reasons]
        assert "supervisor_issue" in codes

    def test_missing_manager_assignee(self) -> None:
        reasons = self._call(["state/ready"], [])
        codes = [r.code for r in reasons]
        assert "missing_manager_assignee" in codes

    def test_non_manager_assignee(self) -> None:
        reasons = self._call(["state/ready"], ["stranger"])
        codes = [r.code for r in reasons]
        assert "non_manager_assignee" in codes

    def test_empty_manager_list_allows_all(self) -> None:
        reasons = self._call(["state/ready"], ["anyone"], manager_usernames=())
        codes = [r.code for r in reasons]
        assert "non_manager_assignee" not in codes
        assert "missing_manager_assignee" not in codes

    def test_all_exclusion_reasons(self) -> None:
        reasons = self._call(
            labels=["roadmap/epic", "supervisor"],
            assignees=["jacobcy"],
        )
        codes = [r.code for r in reasons]
        assert "missing_state_label" in codes
        assert "roadmap_epic" in codes
        assert "supervisor_issue" in codes
        assert "non_manager_assignee" in codes


class TestCollectLabelAnomalies:
    def test_no_anomalies(self) -> None:
        result = collect_label_anomalies(
            ["state/ready"], issue_number=1, has_local_flow=True, is_manager_issue=False
        )
        assert result == []

    def test_roadmap_conflict(self) -> None:
        result = collect_label_anomalies(
            ["roadmap/rfc", "state/claimed"],
            issue_number=1,
            has_local_flow=True,
            is_manager_issue=True,
        )
        assert len(result) == 1
        assert "roadmap_conflict" in result[0].rule
        assert "state/claimed" in result[0].removed

    def test_multi_state_no_roadmap(self) -> None:
        result = collect_label_anomalies(
            ["state/review", "state/blocked"],
            issue_number=1,
            has_local_flow=True,
            is_manager_issue=False,
        )
        assert len(result) == 1
        assert "multi_state" in result[0].rule
        assert result[0].removed == ["state/review"]

    def test_orphan_execution_state(self) -> None:
        result = collect_label_anomalies(
            ["state/in-progress"],
            issue_number=1,
            has_local_flow=False,
            is_manager_issue=True,
        )
        assert len(result) == 1
        assert "orphan_execution" in result[0].rule
        assert "state/in-progress" in result[0].removed
        assert "state/ready" in result[0].added

    def test_orphan_execution_skipped_when_has_flow(self) -> None:
        result = collect_label_anomalies(
            ["state/in-progress"],
            issue_number=1,
            has_local_flow=True,
            is_manager_issue=True,
        )
        assert result == []

    def test_governed_without_terminal_label_backfills_ready(self) -> None:
        result = collect_label_anomalies(
            ["orchestra-governed"],
            issue_number=1,
            has_local_flow=True,
            is_manager_issue=True,
        )
        assert len(result) == 1
        assert "governed_missing_state" in result[0].rule
        assert result[0].removed == []
        assert result[0].added == ["state/ready"]

    def test_governed_missing_state_skipped_when_has_state(self) -> None:
        result = collect_label_anomalies(
            ["orchestra-governed", "state/ready"],
            issue_number=1,
            has_local_flow=True,
            is_manager_issue=True,
        )
        assert result == []

    def test_governed_missing_state_skipped_when_rfc_or_epic(self) -> None:
        for roadmap_label in ("roadmap/rfc", "roadmap/epic"):
            result = collect_label_anomalies(
                ["orchestra-governed", roadmap_label],
                issue_number=1,
                has_local_flow=True,
                is_manager_issue=True,
            )
            assert result == []

    def test_roadmap_skips_multi_state_rule(self) -> None:
        result = collect_label_anomalies(
            ["roadmap/epic", "state/blocked", "state/review"],
            issue_number=1,
            has_local_flow=True,
            is_manager_issue=True,
        )
        rules = [a.rule for a in result]
        assert "multi_state" not in rules
