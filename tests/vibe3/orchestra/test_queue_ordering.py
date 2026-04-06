"""Tests for queue ordering utilities."""

from __future__ import annotations

from vibe3.models.orchestration import IssueInfo
from vibe3.orchestra.queue_ordering import (
    resolve_milestone_rank,
    resolve_priority,
    resolve_roadmap_rank,
    sort_ready_issues,
)


class TestResolvePriority:
    """Tests for priority label resolution."""

    def test_numeric_priority_9(self):
        """Test priority/9 resolves to 9."""
        labels = ["priority/9", "state/ready"]
        assert resolve_priority(labels) == 9

    def test_numeric_priority_7(self):
        """Test priority/7 resolves to 7."""
        labels = ["priority/7", "state/ready"]
        assert resolve_priority(labels) == 7

    def test_numeric_priority_0(self):
        """Test priority/0 resolves to 0."""
        labels = ["priority/0", "state/ready"]
        assert resolve_priority(labels) == 0

    def test_priority_9_sorts_before_priority_7(self):
        """Test that priority/9 sorts before priority/7."""
        labels_high = ["priority/9", "state/ready"]
        labels_low = ["priority/7", "state/ready"]
        assert resolve_priority(labels_high) > resolve_priority(labels_low)

    def test_legacy_priority_critical(self):
        """Test legacy label priority/critical maps to numeric."""
        labels = ["priority/critical", "state/ready"]
        # Legacy critical should map to highest priority
        assert resolve_priority(labels) == 9

    def test_legacy_priority_high(self):
        """Test legacy label priority/high maps to numeric."""
        labels = ["priority/high", "state/ready"]
        # Legacy high should map to high priority
        assert resolve_priority(labels) == 7

    def test_legacy_priority_medium(self):
        """Test legacy label priority/medium maps to numeric."""
        labels = ["priority/medium", "state/ready"]
        # Legacy medium should map to medium priority
        assert resolve_priority(labels) == 5

    def test_legacy_priority_low(self):
        """Test legacy label priority/low maps to numeric."""
        labels = ["priority/low", "state/ready"]
        # Legacy low should map to low priority
        assert resolve_priority(labels) == 3

    def test_missing_priority_fallback_to_zero(self):
        """Test missing priority label falls back to 0."""
        labels = ["state/ready", "type/feature"]
        assert resolve_priority(labels) == 0

    def test_multiple_priority_labels_highest_wins(self):
        """Test when multiple priority labels exist, highest wins."""
        labels = ["priority/3", "priority/9", "state/ready"]
        # Should use highest priority
        assert resolve_priority(labels) == 9


class TestResolveRoadmapRank:
    """Tests for roadmap label resolution."""

    def test_roadmap_p0(self):
        """Test roadmap/p0 resolves to rank 0."""
        labels = ["roadmap/p0", "state/ready"]
        rank, name = resolve_roadmap_rank(labels)
        assert rank == 0
        assert name == "p0"

    def test_roadmap_p1(self):
        """Test roadmap/p1 resolves to rank 1."""
        labels = ["roadmap/p1", "state/ready"]
        rank, name = resolve_roadmap_rank(labels)
        assert rank == 1
        assert name == "p1"

    def test_roadmap_p2(self):
        """Test roadmap/p2 resolves to rank 2."""
        labels = ["roadmap/p2", "state/ready"]
        rank, name = resolve_roadmap_rank(labels)
        assert rank == 2
        assert name == "p2"

    def test_roadmap_p0_sorts_before_p1(self):
        """Test roadmap/p0 sorts before roadmap/p1."""
        labels_p0 = ["roadmap/p0", "state/ready"]
        labels_p1 = ["roadmap/p1", "state/ready"]
        rank_p0, _ = resolve_roadmap_rank(labels_p0)
        rank_p1, _ = resolve_roadmap_rank(labels_p1)
        assert rank_p0 < rank_p1

    def test_missing_roadmap_returns_none(self):
        """Test missing roadmap label returns None name."""
        labels = ["state/ready", "priority/7"]
        rank, name = resolve_roadmap_rank(labels)
        # Missing roadmap should get a high fallback rank
        assert name is None
        # Rank should be higher than any roadmap-labeled issue
        assert rank > 10

    def test_roadmap_overrides_priority_in_sorting(self):
        """Test that roadmap rank is primary sort key within same milestone."""
        # This test will be used in sort_ready_issues tests
        pass


class TestResolveMilestoneRank:
    """Tests for milestone rank resolution."""

    def test_milestone_v0_1(self):
        """Test milestone v0.1 resolves to rank."""
        milestone = {"title": "v0.1", "number": 1}
        rank, title = resolve_milestone_rank(milestone)
        assert title == "v0.1"
        assert isinstance(rank, int)

    def test_milestone_v0_3(self):
        """Test milestone v0.3 resolves to rank."""
        milestone = {"title": "v0.3", "number": 3}
        rank, title = resolve_milestone_rank(milestone)
        assert title == "v0.3"

    def test_milestone_v0_1_sorts_before_v0_3(self):
        """Test milestone v0.1 sorts before v0.3."""
        milestone_01 = {"title": "v0.1", "number": 1}
        milestone_03 = {"title": "v0.3", "number": 3}
        rank_01, _ = resolve_milestone_rank(milestone_01)
        rank_03, _ = resolve_milestone_rank(milestone_03)
        assert rank_01 < rank_03

    def test_missing_milestone_returns_high_rank(self):
        """Test missing milestone gets high fallback rank."""
        rank, title = resolve_milestone_rank(None)
        assert title == ""
        # Should sort after milestone-labeled issues
        assert rank > 1000


class TestSortReadyIssues:
    """Tests for sorting ready queue issues."""

    def test_priority_9_sorts_before_priority_7_same_milestone(self):
        """Test priority/9 issue sorts before priority/7 in same milestone."""
        issues = [
            IssueInfo(
                number=1,
                title="Issue with priority/7",
                state=None,
                labels=["priority/7", "state/ready"],
                milestone="v0.3",
            ),
            IssueInfo(
                number=2,
                title="Issue with priority/9",
                state=None,
                labels=["priority/9", "state/ready"],
                milestone="v0.3",
            ),
        ]
        sorted_issues = sort_ready_issues(issues)
        assert sorted_issues[0].number == 2  # priority/9 first
        assert sorted_issues[1].number == 1  # priority/7 second

    def test_roadmap_p0_sorts_before_p1_same_milestone(self):
        """Test roadmap/p0 sorts before roadmap/p1 in same milestone."""
        issues = [
            IssueInfo(
                number=1,
                title="Issue with roadmap/p1",
                state=None,
                labels=["roadmap/p1", "state/ready"],
                milestone="v0.3",
            ),
            IssueInfo(
                number=2,
                title="Issue with roadmap/p0",
                state=None,
                labels=["roadmap/p0", "state/ready"],
                milestone="v0.3",
            ),
        ]
        sorted_issues = sort_ready_issues(issues)
        assert sorted_issues[0].number == 2  # roadmap/p0 first
        assert sorted_issues[1].number == 1  # roadmap/p1 second

    def test_milestone_v0_1_sorts_before_v0_3(self):
        """Test milestone v0.1 sorts before v0.3."""
        issues = [
            IssueInfo(
                number=1,
                title="Issue in v0.3",
                state=None,
                labels=["state/ready"],
                milestone="v0.3",
            ),
            IssueInfo(
                number=2,
                title="Issue in v0.1",
                state=None,
                labels=["state/ready"],
                milestone="v0.1",
            ),
        ]
        sorted_issues = sort_ready_issues(issues)
        assert sorted_issues[0].number == 2  # v0.1 first
        assert sorted_issues[1].number == 1  # v0.3 second

    def test_missing_priority_fallback_to_zero(self):
        """Test issue without priority label defaults to 0."""
        labels_no_priority = ["state/ready"]
        assert resolve_priority(labels_no_priority) == 0

    def test_missing_roadmap_sorts_after_labeled_roadmap(self):
        """Test issue without roadmap sorts after roadmap-labeled in same milestone."""
        issues = [
            IssueInfo(
                number=1,
                title="Issue without roadmap",
                state=None,
                labels=["state/ready", "priority/7"],
                milestone="v0.3",
            ),
            IssueInfo(
                number=2,
                title="Issue with roadmap/p1",
                state=None,
                labels=["roadmap/p1", "state/ready", "priority/7"],
                milestone="v0.3",
            ),
        ]
        sorted_issues = sort_ready_issues(issues)
        assert sorted_issues[0].number == 2  # roadmap/p1 first
        assert sorted_issues[1].number == 1  # no roadmap second

    def test_combined_sort_order(self):
        """Test full sort: milestone -> roadmap -> priority."""
        issues = [
            # v0.3, roadmap/p1, priority/7 (should be 4th)
            IssueInfo(
                number=100,
                title="A",
                state=None,
                labels=["roadmap/p1", "priority/7", "state/ready"],
                milestone="v0.3",
            ),
            # v0.3, roadmap/p0, priority/7 (should be 3rd)
            IssueInfo(
                number=200,
                title="B",
                state=None,
                labels=["roadmap/p0", "priority/7", "state/ready"],
                milestone="v0.3",
            ),
            # v0.1, roadmap/p1, priority/5 (should be 2nd)
            IssueInfo(
                number=300,
                title="C",
                state=None,
                labels=["roadmap/p1", "priority/5", "state/ready"],
                milestone="v0.1",
            ),
            # v0.1, roadmap/p0, priority/9 (should be 1st)
            IssueInfo(
                number=400,
                title="D",
                state=None,
                labels=["roadmap/p0", "priority/9", "state/ready"],
                milestone="v0.1",
            ),
        ]
        sorted_issues = sort_ready_issues(issues)
        # Expected order: 400, 300, 200, 100
        assert sorted_issues[0].number == 400  # v0.1, p0, priority/9
        assert sorted_issues[1].number == 300  # v0.1, p1, priority/5
        assert sorted_issues[2].number == 200  # v0.3, p0, priority/7
        assert sorted_issues[3].number == 100  # v0.3, p1, priority/7

    def test_issue_number_is_stable_tie_break(self) -> None:
        """When two issues have identical milestone/roadmap/priority, sort by number."""
        issues = [
            # Same milestone, roadmap, priority — should sort by number ascending
            IssueInfo(
                number=300,
                title="Issue 300",
                state=None,
                labels=["roadmap/p1", "priority/7", "state/ready"],
                milestone="v0.3",
            ),
            IssueInfo(
                number=100,
                title="Issue 100",
                state=None,
                labels=["roadmap/p1", "priority/7", "state/ready"],
                milestone="v0.3",
            ),
            IssueInfo(
                number=200,
                title="Issue 200",
                state=None,
                labels=["roadmap/p1", "priority/7", "state/ready"],
                milestone="v0.3",
            ),
        ]
        sorted_issues = sort_ready_issues(issues)
        # All three have same milestone/roadmap/priority
        # Should sort by issue number ascending: 100, 200, 300
        assert sorted_issues[0].number == 100
        assert sorted_issues[1].number == 200
        assert sorted_issues[2].number == 300
