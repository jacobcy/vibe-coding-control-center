"""Tests for RemoteLabelCheckService."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from vibe3.services.remote_label_check_service import (
    RemoteLabelCheckService,
)


class TestRemoteLabelCheckService:
    """Test suite for RemoteLabelCheckService."""

    @pytest.fixture
    def mock_github_client(self):
        """Mock GitHubClient."""
        return MagicMock()

    @pytest.fixture
    def mock_store(self):
        """Mock SQLiteClient."""
        return MagicMock()

    @pytest.fixture
    def mock_label_port(self):
        """Mock GhIssueLabelPort."""
        return MagicMock()

    @pytest.fixture
    def service(self, mock_github_client, mock_store, mock_label_port):
        """Create service instance with mocks."""
        return RemoteLabelCheckService(
            github_client=mock_github_client,
            store=mock_store,
            label_port=mock_label_port,
            manager_usernames=("vibe-manager-agent",),
        )

    def test_rule1_roadmap_rfc_conflict(self, service, mock_github_client, mock_store):
        """Rule 1: issue with roadmap/rfc + state/claimed → removes state/claimed."""
        # Setup: Issue with roadmap/rfc and state/claimed
        mock_github_client.list_issues.return_value = [
            {
                "number": 1,
                "title": "Test issue",
                "labels": [
                    {"name": "roadmap/rfc"},
                    {"name": "state/claimed"},
                ],
                "assignees": [],
            }
        ]
        mock_store.get_all_flows.return_value = []

        # Execute
        result = service.check(dry_run=True)

        # Verify
        assert result.total_issues == 1
        assert result.issues_found == 1
        assert len(result.results) == 1
        assert result.results[0].issue_number == 1
        assert result.results[0].labels_removed == ["state/claimed"]
        assert result.results[0].labels_added == []
        assert "规则 1" in result.results[0].rule

    def test_rule1_roadmap_epic_conflict(self, service, mock_github_client, mock_store):
        """Rule 1: issue with roadmap/epic + state/in-progress → removes state."""
        mock_github_client.list_issues.return_value = [
            {
                "number": 2,
                "title": "Epic issue",
                "labels": [
                    {"name": "roadmap/epic"},
                    {"name": "state/in-progress"},
                ],
                "assignees": [],
            }
        ]
        mock_store.get_all_flows.return_value = []

        result = service.check(dry_run=True)

        assert result.issues_found == 1
        assert result.results[0].issue_number == 2
        assert result.results[0].labels_removed == ["state/in-progress"]
        assert "规则 1" in result.results[0].rule

    def test_rule2_multiple_state_labels_blocked_and_review(
        self, service, mock_github_client, mock_store
    ):
        """Rule 2: issue with state/blocked and state/review → keeps blocked."""
        mock_github_client.list_issues.return_value = [
            {
                "number": 3,
                "title": "Blocked issue",
                "labels": [
                    {"name": "state/blocked"},
                    {"name": "state/review"},
                ],
                "assignees": [],
            }
        ]
        mock_store.get_all_flows.return_value = []

        result = service.check(dry_run=True)

        assert result.issues_found == 1
        assert result.results[0].issue_number == 3
        assert result.results[0].labels_removed == ["state/review"]
        assert "规则 2" in result.results[0].rule

    def test_rule2_multiple_state_labels_merge_ready_and_in_progress(
        self, service, mock_github_client, mock_store
    ):
        """Rule 2: merge-ready has higher priority than in-progress."""
        mock_github_client.list_issues.return_value = [
            {
                "number": 4,
                "title": "Merge ready issue",
                "labels": [
                    {"name": "state/merge-ready"},
                    {"name": "state/in-progress"},
                ],
                "assignees": [],
            }
        ]
        mock_store.get_all_flows.return_value = []

        result = service.check(dry_run=True)

        assert result.issues_found == 1
        assert result.results[0].labels_removed == ["state/in-progress"]
        assert "规则 2" in result.results[0].rule

    def test_rule3_orphan_execution_state_manager_assigned(
        self, service, mock_github_client, mock_store
    ):
        """Rule 3: manager-assigned issue with state/in-progress but no local flow."""
        mock_github_client.list_issues.return_value = [
            {
                "number": 5,
                "title": "Orphan issue",
                "labels": [{"name": "state/in-progress"}],
                "assignees": [{"login": "vibe-manager-agent"}],
            }
        ]
        # No local flow for issue-5
        mock_store.get_all_flows.return_value = []

        result = service.check(dry_run=True)

        assert result.issues_found == 1
        assert result.results[0].labels_removed == ["state/in-progress"]
        assert result.results[0].labels_added == ["state/ready"]
        assert "规则 3" in result.results[0].rule

    def test_rule3_non_manager_assigned_no_action(
        self, service, mock_github_client, mock_store
    ):
        """Rule 3: non-manager-assigned issue with state/in-progress and
        no local flow → no action."""
        mock_github_client.list_issues.return_value = [
            {
                "number": 6,
                "title": "Non-manager issue",
                "labels": [{"name": "state/in-progress"}],
                "assignees": [{"login": "human-user"}],  # Not a manager
            }
        ]
        mock_store.get_all_flows.return_value = []

        result = service.check(dry_run=True)

        # Should not trigger any rule
        assert result.issues_found == 0

    def test_rule4_orphan_orchestra_governed(
        self, service, mock_github_client, mock_store
    ):
        """Rule 4: manager-assigned issue with orchestra-governed, no state/*,
        no roadmap labels."""
        mock_github_client.list_issues.return_value = [
            {
                "number": 7,
                "title": "Orchestra issue",
                "labels": [{"name": "orchestra-governed"}],
                "assignees": [{"login": "vibe-manager-agent"}],
            }
        ]
        mock_store.get_all_flows.return_value = []

        result = service.check(dry_run=True)

        assert result.issues_found == 1
        assert result.results[0].labels_removed == ["orchestra-governed"]
        assert "规则 4" in result.results[0].rule

    def test_dry_run_mode_no_mutations(
        self, service, mock_github_client, mock_store, mock_label_port
    ):
        """Dry run mode should not call label_port mutations."""
        mock_github_client.list_issues.return_value = [
            {
                "number": 8,
                "title": "Test issue",
                "labels": [
                    {"name": "roadmap/rfc"},
                    {"name": "state/claimed"},
                ],
                "assignees": [],
            }
        ]
        mock_store.get_all_flows.return_value = []

        result = service.check(dry_run=True)

        # Should detect the issue but not apply changes
        assert result.issues_found == 1
        mock_label_port.remove_issue_label.assert_not_called()
        mock_label_port.add_issue_label.assert_not_called()

    def test_real_mode_applies_mutations(
        self, service, mock_github_client, mock_store, mock_label_port
    ):
        """Real mode should call label_port mutations."""
        mock_github_client.list_issues.return_value = [
            {
                "number": 9,
                "title": "Test issue",
                "labels": [
                    {"name": "roadmap/rfc"},
                    {"name": "state/claimed"},
                ],
                "assignees": [],
            }
        ]
        mock_store.get_all_flows.return_value = []

        result = service.check(dry_run=False)

        # Should detect and apply changes
        assert result.issues_found == 1
        mock_label_port.remove_issue_label.assert_called_once_with(9, "state/claimed")

    def test_rule_ordering_roadmap_takes_precedence(
        self, service, mock_github_client, mock_store
    ):
        """Rule 1 runs before rule 2: roadmap conflict takes precedence."""
        # Issue with both roadmap/rfc and multiple state labels
        mock_github_client.list_issues.return_value = [
            {
                "number": 10,
                "title": "Complex issue",
                "labels": [
                    {"name": "roadmap/rfc"},
                    {"name": "state/blocked"},
                    {"name": "state/review"},
                ],
                "assignees": [],
            }
        ]
        mock_store.get_all_flows.return_value = []

        result = service.check(dry_run=True)

        # Should trigger rule 1, not rule 2
        assert result.issues_found == 1
        assert "规则 1" in result.results[0].rule
        # Both state labels should be removed
        assert set(result.results[0].labels_removed) == {
            "state/blocked",
            "state/review",
        }

    def test_no_manager_usernames_skips_rules_3_4(
        self, mock_github_client, mock_store, mock_label_port
    ):
        """If no manager usernames configured, rules 3 and 4 should be skipped."""
        service = RemoteLabelCheckService(
            github_client=mock_github_client,
            store=mock_store,
            label_port=mock_label_port,
            manager_usernames=(),  # Empty tuple
        )

        mock_github_client.list_issues.return_value = [
            {
                "number": 11,
                "title": "Manager issue",
                "labels": [{"name": "state/in-progress"}],
                "assignees": [{"login": "vibe-manager-agent"}],
            }
        ]
        mock_store.get_all_flows.return_value = []

        result = service.check(dry_run=True)

        # Should not trigger rule 3 because no managers configured
        assert result.issues_found == 0

    def test_rule3_issue_has_local_flow_no_action(
        self, service, mock_github_client, mock_store
    ):
        """Rule 3: manager-assigned issue with state/in-progress and HAS local
        flow → no action."""
        mock_github_client.list_issues.return_value = [
            {
                "number": 12,
                "title": "Active issue",
                "labels": [{"name": "state/in-progress"}],
                "assignees": [{"login": "vibe-manager-agent"}],
            }
        ]
        # Issue 12 HAS a local flow record
        mock_store.get_all_flows.return_value = [{"branch": "task/issue-12"}]

        result = service.check(dry_run=True)

        # Should not trigger rule 3
        assert result.issues_found == 0

    def test_rule4_issue_has_state_label_no_action(
        self, service, mock_github_client, mock_store
    ):
        """Rule 4: issue with orchestra-governed BUT has state/* label → no action."""
        mock_github_client.list_issues.return_value = [
            {
                "number": 13,
                "title": "State issue",
                "labels": [
                    {"name": "orchestra-governed"},
                    {"name": "state/ready"},
                ],
                "assignees": [{"login": "vibe-manager-agent"}],
            }
        ]
        mock_store.get_all_flows.return_value = []

        result = service.check(dry_run=True)

        # Should not trigger rule 4
        assert result.issues_found == 0

    def test_rule4_issue_has_roadmap_label_no_action(
        self, service, mock_github_client, mock_store
    ):
        """Rule 4: issue with orchestra-governed BUT has roadmap label → no action."""
        mock_github_client.list_issues.return_value = [
            {
                "number": 14,
                "title": "Roadmap issue",
                "labels": [
                    {"name": "orchestra-governed"},
                    {"name": "roadmap/rfc"},
                ],
                "assignees": [{"login": "vibe-manager-agent"}],
            }
        ]
        mock_store.get_all_flows.return_value = []

        result = service.check(dry_run=True)

        # Should not trigger any rule because:
        # - Rule 1 needs state/* labels (orchestra-governed is not state/*)
        # - Rule 4 needs NO roadmap labels (but this issue has roadmap/rfc)
        assert result.issues_found == 0

    def test_multiple_issues_with_different_rules(
        self, service, mock_github_client, mock_store
    ):
        """Test processing multiple issues with different rules."""
        mock_github_client.list_issues.return_value = [
            {
                "number": 15,
                "title": "Issue 1",
                "labels": [{"name": "roadmap/rfc"}, {"name": "state/ready"}],
                "assignees": [],
            },
            {
                "number": 16,
                "title": "Issue 2",
                "labels": [
                    {"name": "state/blocked"},
                    {"name": "state/in-progress"},
                ],
                "assignees": [],
            },
            {
                "number": 17,
                "title": "Issue 3",
                "labels": [{"name": "state/review"}],
                "assignees": [{"login": "vibe-manager-agent"}],
            },
        ]
        mock_store.get_all_flows.return_value = []

        result = service.check(dry_run=True)

        assert result.total_issues == 3
        assert result.issues_found == 3
        # Issue 15: removes state/ready (1)
        # Issue 16: removes state/in-progress (1)
        # Issue 17: removes state/review (1), adds state/ready
        assert result.total_removed == 3
        assert result.total_added == 1  # state/ready for issue 17

    def test_rule1_plus_rule3_interaction_roadmap_issue(
        self, service, mock_github_client, mock_store
    ):
        """Rule 1+3: roadmap issue should NOT get state/ready via Rule 3."""
        # Issue with roadmap/rfc + state/in-progress, manager-assigned, no flow
        mock_github_client.list_issues.return_value = [
            {
                "number": 18,
                "title": "Roadmap issue with execution state",
                "labels": [
                    {"name": "roadmap/rfc"},
                    {"name": "state/in-progress"},
                ],
                "assignees": [{"login": "vibe-manager-agent"}],
            }
        ]
        mock_store.get_all_flows.return_value = []

        result = service.check(dry_run=True)

        # Should only trigger Rule 1 (remove state/in-progress)
        # Should NOT trigger Rule 3 (add state/ready)
        assert result.issues_found == 1
        assert result.results[0].labels_removed == ["state/in-progress"]
        assert result.results[0].labels_added == []
        assert "规则 1" in result.results[0].rule
        assert "规则 3" not in result.results[0].rule

    def test_rule2_plus_rule3_interaction_blocked_state(
        self, service, mock_github_client, mock_store
    ):
        """Rule 2+3: blocked state should prevent Rule 3 from adding state/ready."""
        # Issue with state/blocked + state/in-progress, manager-assigned, no flow
        mock_github_client.list_issues.return_value = [
            {
                "number": 19,
                "title": "Blocked issue with execution state",
                "labels": [
                    {"name": "state/blocked"},
                    {"name": "state/in-progress"},
                ],
                "assignees": [{"login": "vibe-manager-agent"}],
            }
        ]
        mock_store.get_all_flows.return_value = []

        result = service.check(dry_run=True)

        # Should trigger Rule 2 (keep blocked, remove in-progress)
        # Should NOT trigger Rule 3 (add state/ready)
        assert result.issues_found == 1
        assert result.results[0].labels_removed == ["state/in-progress"]
        assert result.results[0].labels_added == []
        assert "规则 2" in result.results[0].rule
        assert "规则 3" not in result.results[0].rule

    def test_rule2_plus_rule3_interaction_done_state(
        self, service, mock_github_client, mock_store
    ):
        """Rule 2+3: done state should prevent Rule 3 from adding state/ready."""
        mock_github_client.list_issues.return_value = [
            {
                "number": 20,
                "title": "Done issue with execution state",
                "labels": [
                    {"name": "state/done"},
                    {"name": "state/review"},
                ],
                "assignees": [{"login": "vibe-manager-agent"}],
            }
        ]
        mock_store.get_all_flows.return_value = []

        result = service.check(dry_run=True)

        # Should trigger Rule 2 (keep done, remove review)
        # Should NOT trigger Rule 3
        assert result.issues_found == 1
        assert result.results[0].labels_removed == ["state/review"]
        assert result.results[0].labels_added == []
        assert "规则 2" in result.results[0].rule

    def test_rule2_plus_rule3_interaction_execution_state_allowed(
        self, service, mock_github_client, mock_store
    ):
        """Rule 2+3: if Rule 2 kept execution state, Rule 3 should fire."""
        # Issue with state/review + state/in-progress, manager-assigned, no flow
        mock_github_client.list_issues.return_value = [
            {
                "number": 21,
                "title": "Review issue with execution state",
                "labels": [
                    {"name": "state/review"},
                    {"name": "state/in-progress"},
                ],
                "assignees": [{"login": "vibe-manager-agent"}],
            }
        ]
        mock_store.get_all_flows.return_value = []

        result = service.check(dry_run=True)

        # Should trigger Rule 2 (keep review, remove in-progress)
        # AND Rule 3 (remove review, add state/ready)
        assert result.issues_found == 1
        assert "state/in-progress" in result.results[0].labels_removed
        assert "state/review" in result.results[0].labels_removed
        assert result.results[0].labels_added == ["state/ready"]
        assert "规则 2" in result.results[0].rule
        assert "规则 3" in result.results[0].rule
