"""Tests for flow model migrations."""

from vibe3.models.flow import FlowState, IssueLink


class TestFlowStatusMigration:
    """Tests for flow_status field migration (idle->active, missing->stale)."""

    def test_migrate_idle_to_active(self):
        """Test that 'idle' status is migrated to 'active'."""
        flow = FlowState(branch="test-branch", flow_slug="test", flow_status="idle")
        assert flow.flow_status == "active"

    def test_migrate_missing_to_stale(self):
        """Test that 'missing' status is migrated to 'stale'."""
        flow = FlowState(branch="test-branch", flow_slug="test", flow_status="missing")
        assert flow.flow_status == "stale"

    def test_active_status_unchanged(self):
        """Test that 'active' status is not modified."""
        flow = FlowState(branch="test-branch", flow_slug="test", flow_status="active")
        assert flow.flow_status == "active"

    def test_blocked_status_unchanged(self):
        """Test that 'blocked' status is not modified."""
        flow = FlowState(branch="test-branch", flow_slug="test", flow_status="blocked")
        assert flow.flow_status == "blocked"

    def test_done_status_unchanged(self):
        """Test that 'done' status is not modified."""
        flow = FlowState(branch="test-branch", flow_slug="test", flow_status="done")
        assert flow.flow_status == "done"

    def test_stale_status_unchanged(self):
        """Test that 'stale' status is not modified."""
        flow = FlowState(branch="test-branch", flow_slug="test", flow_status="stale")
        assert flow.flow_status == "stale"


class TestIssueRoleMigration:
    """Tests for issue_role field migration (related->repo)."""

    def test_migrate_related_to_repo(self):
        """Test that 'related' role is migrated to 'repo'."""
        link = IssueLink(branch="test-branch", issue_number=123, issue_role="related")
        assert link.issue_role == "repo"

    def test_task_role_unchanged(self):
        """Test that 'task' role is not modified."""
        link = IssueLink(branch="test-branch", issue_number=123, issue_role="task")
        assert link.issue_role == "task"

    def test_repo_role_unchanged(self):
        """Test that 'repo' role is not modified."""
        link = IssueLink(branch="test-branch", issue_number=123, issue_role="repo")
        assert link.issue_role == "repo"


class TestModelSerialization:
    """Tests for model serialization with migrated values."""

    def test_flow_state_dict_serialization(self):
        """Test that FlowState serializes with migrated values."""
        flow = FlowState(branch="test-branch", flow_slug="test", flow_status="idle")
        data = flow.model_dump()
        assert data["flow_status"] == "active"

    def test_issue_link_dict_serialization(self):
        """Test that IssueLink serializes with migrated values."""
        link = IssueLink(branch="test-branch", issue_number=123, issue_role="related")
        data = link.model_dump()
        assert data["issue_role"] == "repo"

    def test_flow_state_json_serialization(self):
        """Test that FlowState JSON serialization uses migrated values."""
        flow = FlowState(branch="test-branch", flow_slug="test", flow_status="missing")
        json_str = flow.model_dump_json()
        assert '"flow_status":"stale"' in json_str

    def test_issue_link_json_serialization(self):
        """Test that IssueLink JSON serialization uses migrated values."""
        link = IssueLink(branch="test-branch", issue_number=123, issue_role="related")
        json_str = link.model_dump_json()
        assert '"issue_role":"repo"' in json_str
