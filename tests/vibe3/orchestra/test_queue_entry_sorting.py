"""Tests for queue entry sorting utilities."""

from __future__ import annotations

from vibe3.models import QueueEntry
from vibe3.models.orchestration import IssueInfo
from vibe3.utils.queue_ordering import sort_queue_entries


class TestSortQueueEntries:
    """Tests for sorting queue entries with preserved waiting_state."""

    def test_sort_queue_entries_basic_order(self):
        """Test that queue entries sort by priority correctly."""
        entries = [
            QueueEntry(issue_number=1, collected_state="ready"),
            QueueEntry(issue_number=2, collected_state="ready"),
        ]
        issue_infos = {
            1: IssueInfo(
                number=1,
                title="Low priority",
                state=None,
                labels=["priority/3", "state/ready"],
                milestone="v0.3",
            ),
            2: IssueInfo(
                number=2,
                title="High priority",
                state=None,
                labels=["priority/9", "state/ready"],
                milestone="v0.3",
            ),
        }
        sorted_entries = sort_queue_entries(entries, issue_infos)
        assert sorted_entries[0].issue_number == 2  # priority/9 first
        assert sorted_entries[1].issue_number == 1  # priority/3 second

    def test_sort_queue_entries_preserves_waiting_state(self):
        """Test that waiting_state is preserved across re-sort."""
        entries = [
            QueueEntry(
                issue_number=1, collected_state="ready", waiting_state="in-progress"
            ),
            QueueEntry(issue_number=2, collected_state="ready", waiting_state=None),
        ]
        issue_infos = {
            1: IssueInfo(
                number=1,
                title="Low priority",
                state=None,
                labels=["priority/3", "state/ready"],
                milestone="v0.3",
            ),
            2: IssueInfo(
                number=2,
                title="High priority",
                state=None,
                labels=["priority/9", "state/ready"],
                milestone="v0.3",
            ),
        }
        sorted_entries = sort_queue_entries(entries, issue_infos)
        # Order should change, but waiting_state preserved
        assert sorted_entries[0].issue_number == 2
        assert sorted_entries[0].waiting_state is None
        assert sorted_entries[1].issue_number == 1
        assert sorted_entries[1].waiting_state == "in-progress"

    def test_sort_queue_entries_missing_issue_info(self):
        """Test that entries without IssueInfo go to end unchanged."""
        entries = [
            QueueEntry(issue_number=1, collected_state="ready"),
            QueueEntry(issue_number=2, collected_state="ready"),
            QueueEntry(issue_number=3, collected_state="ready"),
        ]
        issue_infos = {
            # Issue 2 missing from dict
            1: IssueInfo(
                number=1,
                title="Low priority",
                state=None,
                labels=["priority/3", "state/ready"],
                milestone="v0.3",
            ),
            3: IssueInfo(
                number=3,
                title="High priority",
                state=None,
                labels=["priority/9", "state/ready"],
                milestone="v0.3",
            ),
        }
        sorted_entries = sort_queue_entries(entries, issue_infos)
        # Issue 2 should be at end (missing IssueInfo)
        assert sorted_entries[-1].issue_number == 2
        # First two should be sorted by priority
        assert sorted_entries[0].issue_number == 3  # priority/9
        assert sorted_entries[1].issue_number == 1  # priority/3
