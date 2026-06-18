"""Tests for AuditEvidenceCollector service."""

from unittest.mock import MagicMock

import pytest

from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.services.audit.collector import AuditEvidenceCollector
from vibe3.services.audit.formatter import format_bundle_json, format_bundle_summary


@pytest.fixture
def mock_sqlite_client() -> MagicMock:
    """Create mock SQLite client."""
    return MagicMock(spec=SQLiteClient)


@pytest.fixture
def mock_github_client() -> MagicMock:
    """Create mock GitHub client."""
    return MagicMock(spec=GitHubClient)


@pytest.fixture
def mock_git_client() -> MagicMock:
    """Create mock Git client."""
    return MagicMock(spec=GitClient)


@pytest.fixture
def collector(
    mock_sqlite_client: MagicMock,
    mock_github_client: MagicMock,
    mock_git_client: MagicMock,
) -> AuditEvidenceCollector:
    """Create collector instance with mocked clients."""
    return AuditEvidenceCollector(
        sqlite_client=mock_sqlite_client,
        github_client=mock_github_client,
        git_client=mock_git_client,
    )


class TestCollectFlowEvidence:
    """Tests for collect_flow_evidence method."""

    def test_collect_flow_evidence_returns_flow_refs(
        self, collector: AuditEvidenceCollector, mock_sqlite_client: MagicMock
    ) -> None:
        """Should return FlowRef list when flow state exists."""
        # Setup mocks
        mock_sqlite_client.get_flow_state.return_value = {
            "branch": "task/issue-123",
            "flow_slug": "issue-123",
            "flow_status": "active",
            "updated_at": "2026-06-18T10:00:00",
            "latest_actor": "claude/sonnet",
        }
        mock_sqlite_client.get_events.return_value = [
            {
                "id": 1,
                "event_type": "flow_created",
                "actor": "claude/opus",
                "created_at": "2026-06-18T09:00:00",
            },
            {
                "id": 2,
                "event_type": "state_transitioned",
                "actor": "claude/sonnet",
                "created_at": "2026-06-18T09:30:00",
            },
        ]
        mock_sqlite_client.get_issue_links.return_value = []

        # Execute
        refs = collector.collect_flow_evidence("task/issue-123")

        # Verify
        assert len(refs) == 3  # 1 state snapshot + 2 events
        assert refs[0].event_type == "flow_state_snapshot"
        assert refs[1].event_type == "flow_created"
        assert refs[2].event_type == "state_transitioned"
        # All refs should have the same watermark
        assert refs[0].watermark == refs[1].watermark == refs[2].watermark

    def test_collect_flow_evidence_empty_branch_returns_empty(
        self, collector: AuditEvidenceCollector, mock_sqlite_client: MagicMock
    ) -> None:
        """Should return empty list when flow state does not exist."""
        mock_sqlite_client.get_flow_state.return_value = None

        refs = collector.collect_flow_evidence("nonexistent-branch")

        assert refs == []


class TestCollectGithubIssueEvidence:
    """Tests for collect_github_issue_evidence method."""

    def test_collect_github_issue_evidence_with_comments(
        self, collector: AuditEvidenceCollector, mock_github_client: MagicMock
    ) -> None:
        """Should extract markers from comments."""
        # Setup mocks - use nested author objects like real GitHub API
        mock_github_client.view_issue.return_value = {
            "number": 123,
            "title": "Test Issue",
            "body": "Test body",
            "state": "open",
            "author": {"login": "user"},
            "createdAt": "2026-06-18T08:00:00",
        }
        mock_github_client.list_issue_comments.return_value = [
            {
                "id": 456,
                "body": "[manager] Moving to in-progress",
                "author": {"login": "manager-bot"},
                "createdAt": "2026-06-18T09:00:00",
                "url": "https://github.com/owner/repo/issues/123#issuecomment-456",
            },
            {
                "id": 789,
                "body": "[plan] Implementation plan submitted",
                "author": {"login": "planner-bot"},
                "createdAt": "2026-06-18T10:00:00",
                "url": "https://github.com/owner/repo/issues/123#issuecomment-789",
            },
        ]

        # Execute
        refs = collector.collect_github_issue_evidence(123, repo="owner/repo")

        # Verify
        assert len(refs) == 3  # 1 issue + 2 comments
        assert refs[0].kind == "issue"
        assert refs[0].author == "user"
        assert refs[1].kind == "issue_comment"
        assert refs[1].author == "manager-bot"
        assert refs[1].marker == "[manager]"
        assert refs[2].marker == "[plan]"

    def test_collect_github_issue_evidence_issue_not_found(
        self, collector: AuditEvidenceCollector, mock_github_client: MagicMock
    ) -> None:
        """Should return empty list when issue not found."""
        mock_github_client.view_issue.return_value = None

        refs = collector.collect_github_issue_evidence(999)

        assert refs == []


class TestCollectGithubPrEvidence:
    """Tests for collect_github_pr_evidence method."""

    def test_collect_github_pr_evidence_with_reviews(
        self, collector: AuditEvidenceCollector, mock_github_client: MagicMock
    ) -> None:
        """Should collect PR state, comments, and reviews."""
        # Setup mocks - PRResponse objects use attribute access
        from vibe3.models import PRResponse

        mock_pr = MagicMock(spec=PRResponse)
        mock_pr.number = 456
        mock_pr.url = "https://github.com/owner/repo/pull/456"
        mock_pr.author = {"login": "developer"}
        mock_pr.created_at = "2026-06-18T10:00:00"

        mock_github_client.list_prs_for_branch.return_value = [mock_pr]
        mock_github_client.list_pr_comments.return_value = [
            {
                "id": 111,
                "author": {"login": "reviewer"},
                "createdAt": "2026-06-18T11:00:00",
                "url": "https://github.com/owner/repo/pull/456#issuecomment-111",
            }
        ]
        mock_github_client.list_pr_reviews.return_value = [
            {
                "id": 222,
                "user": {"login": "reviewer"},
                "submittedAt": "2026-06-18T11:30:00",
                "url": "https://github.com/owner/repo/pull/456#pullrequestreview-222",
            }
        ]

        # Execute
        refs = collector.collect_github_pr_evidence(
            branch="task/issue-123", repo="owner/repo"
        )

        # Verify
        assert len(refs) == 3  # 1 PR + 1 comment + 1 review
        assert refs[0].kind == "pr"
        assert refs[0].author == "developer"
        assert refs[1].kind == "pr_comment"
        assert refs[1].author == "reviewer"
        assert refs[2].kind == "review"
        assert refs[2].author == "reviewer"

    def test_collect_github_pr_evidence_no_prs(
        self, collector: AuditEvidenceCollector, mock_github_client: MagicMock
    ) -> None:
        """Should return empty list when no PRs found."""
        mock_github_client.list_prs_for_branch.return_value = []

        refs = collector.collect_github_pr_evidence(branch="task/issue-123")

        assert refs == []


class TestCollectGitEvidence:
    """Tests for collect_git_evidence method."""

    def test_collect_git_evidence_identifies_commits(
        self, collector: AuditEvidenceCollector, mock_git_client: MagicMock
    ) -> None:
        """Should collect commit subjects and create GitRef objects."""
        # Mock git log output with SHA and subject
        mock_git_client._run.return_value = (
            "abc123 feat(core): add new feature\n"
            "def456 fix(bug): resolve issue\n"
            "789xyz test: add unit tests"
        )

        refs = collector.collect_git_evidence("task/issue-123", base_ref="origin/main")

        assert len(refs) == 4  # 1 diff_range + 3 commits
        assert refs[0].kind == "diff_range"
        assert refs[0].base_ref == "origin/main"
        assert refs[0].head_ref == "task/issue-123"
        assert refs[1].kind == "commit"
        assert refs[1].ref == "abc123"  # SHA, not subject

    def test_collect_git_evidence_empty_branch(
        self, collector: AuditEvidenceCollector, mock_git_client: MagicMock
    ) -> None:
        """Should handle empty commit history gracefully."""
        mock_git_client._run.return_value = ""

        refs = collector.collect_git_evidence("task/issue-123")

        assert len(refs) == 0


class TestAssembleBundle:
    """Tests for assemble_bundle method."""

    def test_assemble_bundle_full(
        self,
        collector: AuditEvidenceCollector,
        mock_sqlite_client: MagicMock,
        mock_github_client: MagicMock,
        mock_git_client: MagicMock,
    ) -> None:
        """Should assemble complete EvidenceBundle with all fields."""
        # Setup all mocks
        mock_sqlite_client.get_flow_state.return_value = {
            "branch": "task/issue-123",
            "flow_slug": "issue-123",
            "flow_status": "active",
            "updated_at": "2026-06-18T10:00:00",
            "latest_actor": "claude/sonnet",
        }
        mock_sqlite_client.get_events.return_value = []
        mock_sqlite_client.get_issue_links.return_value = []
        mock_sqlite_client.db_path = "/tmp/test.db"

        mock_github_client.view_issue.return_value = {
            "number": 123,
            "title": "Test",
            "body": "Body",
            "state": "open",
            "author": {"login": "user"},
            "createdAt": "2026-06-18T08:00:00",
        }
        mock_github_client.list_issue_comments.return_value = []
        mock_github_client.list_prs_for_branch.return_value = []

        mock_git_client.get_current_commit.return_value = "abc123"
        # Mock the _run method for git log
        mock_git_client._run.return_value = ""

        # Execute
        bundle = collector.assemble_bundle(
            mode="issue",
            issue_number=123,
            branch="task/issue-123",
            repo="owner/repo",
        )

        # Verify
        assert bundle.schema_version == 1
        assert bundle.collection_context.mode == "issue"
        assert bundle.primary_subject.issue_number == 123
        assert bundle.primary_subject.branch == "task/issue-123"
        assert bundle.trust.source_class in ["authoritative", "derived", "auxiliary"]
        assert bundle.summary.symptom != ""

    def test_assemble_bundle_metadata(
        self,
        collector: AuditEvidenceCollector,
        mock_sqlite_client: MagicMock,
        mock_github_client: MagicMock,
        mock_git_client: MagicMock,
    ) -> None:
        """Should include source metadata in bundle."""
        mock_sqlite_client.get_flow_state.return_value = None
        mock_sqlite_client.db_path = "/tmp/test.db"
        mock_github_client.view_issue.return_value = {
            "number": 123,
            "title": "Test",
            "body": "Body",
            "state": "open",
            "author": {"login": "user"},
            "createdAt": "2026-06-18T08:00:00",
        }
        mock_github_client.list_issue_comments.return_value = []
        mock_github_client.list_prs_for_branch.return_value = []
        mock_git_client.get_current_commit.return_value = "abc123"
        mock_git_client._run.return_value = ""

        bundle = collector.assemble_bundle(mode="issue", issue_number=123)

        assert bundle.collection_context.source_machine is not None
        assert bundle.collection_context.source_commit == "abc123"
        assert bundle.collection_context.source_db == "/tmp/test.db"


class TestFormatBundle:
    """Tests for formatting methods."""

    def test_format_bundle_json_output(
        self,
        collector: AuditEvidenceCollector,
        mock_sqlite_client: MagicMock,
        mock_github_client: MagicMock,
        mock_git_client: MagicMock,
    ) -> None:
        """Should output valid JSON."""
        mock_sqlite_client.get_flow_state.return_value = None
        mock_github_client.view_issue.return_value = {
            "number": 123,
            "title": "Test",
            "body": "Body",
            "state": "open",
            "author": {"login": "user"},
            "createdAt": "2026-06-18T08:00:00",
        }
        mock_github_client.list_issue_comments.return_value = []
        mock_github_client.list_prs_for_branch.return_value = []
        mock_git_client.get_current_commit.return_value = "abc123"
        mock_git_client._run.return_value = ""

        bundle = collector.assemble_bundle(mode="issue", issue_number=123)
        json_output = format_bundle_json(bundle)

        # Should be valid JSON
        import json

        parsed = json.loads(json_output)
        assert parsed["id"] == bundle.id
        assert parsed["schema_version"] == 1

    def test_format_bundle_summary_output(
        self,
        collector: AuditEvidenceCollector,
        mock_sqlite_client: MagicMock,
        mock_github_client: MagicMock,
        mock_git_client: MagicMock,
    ) -> None:
        """Should output human-readable summary."""
        mock_sqlite_client.get_flow_state.return_value = None
        mock_github_client.view_issue.return_value = {
            "number": 123,
            "title": "Test",
            "body": "Body",
            "state": "open",
            "author": {"login": "user"},
            "createdAt": "2026-06-18T08:00:00",
        }
        mock_github_client.list_issue_comments.return_value = []
        mock_github_client.list_prs_for_branch.return_value = []
        mock_git_client.get_current_commit.return_value = "abc123"
        mock_git_client._run.return_value = ""

        bundle = collector.assemble_bundle(mode="issue", issue_number=123)
        summary = format_bundle_summary(bundle)

        # Should contain key fields
        assert bundle.id in summary
        assert "Issue: 123" in summary
        assert "symptom" in summary.lower()
