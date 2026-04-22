"""Tests for verdict service."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from vibe3.models.verdict import VerdictRecord
from vibe3.services.verdict_service import VerdictService


class TestVerdictService:
    """Test cases for VerdictService."""

    @pytest.fixture
    def mock_store(self) -> MagicMock:
        """Create mock SQLiteClient."""
        return MagicMock()

    @pytest.fixture
    def mock_git_client(self) -> MagicMock:
        """Create mock GitClient."""
        client = MagicMock()
        client.get_current_branch.return_value = "test-branch"
        return client

    @pytest.fixture
    def mock_flow_service(self) -> MagicMock:
        """Create mock FlowService."""
        return MagicMock()

    @pytest.fixture
    def mock_handoff_service(self) -> MagicMock:
        """Create mock HandoffService."""
        return MagicMock()

    @pytest.fixture
    def verdict_service(
        self,
        mock_store: MagicMock,
        mock_git_client: MagicMock,
        mock_flow_service: MagicMock,
        mock_handoff_service: MagicMock,
    ) -> VerdictService:
        """Create VerdictService instance with mocked dependencies."""
        return VerdictService(
            store=mock_store,
            git_client=mock_git_client,
            flow_service=mock_flow_service,
            handoff_service=mock_handoff_service,
        )

    def test_write_verdict_success(
        self,
        verdict_service: VerdictService,
        mock_store: MagicMock,
        mock_git_client: MagicMock,
        mock_handoff_service: MagicMock,
    ) -> None:
        """Test writing a verdict successfully."""
        # Setup
        mock_git_client.get_current_branch.return_value = "feature/test"
        mock_store.get_flow_state.return_value = {}  # Flow exists

        # Mock signature service
        with patch(
            "vibe3.services.verdict_service.SignatureService.resolve_for_branch"
        ) as mock_resolve:
            mock_resolve.return_value = "claude/claude-sonnet-4-6"

            # Execute
            record = verdict_service.write_verdict(
                verdict="MAJOR",
                reason="Found indentation errors",
                issues="Missing docstrings",
                branch=None,
            )

        # Assert
        assert record.verdict == "MAJOR"
        assert record.reason == "Found indentation errors"
        assert record.issues == "Missing docstrings"
        assert record.flow_branch == "feature/test"
        assert record.actor == "claude/claude-sonnet-4-6"
        assert record.role == "agent"

        # Verify handoff was appended
        mock_handoff_service.append_current_handoff.assert_called_once()

        # Verify flow state was updated
        mock_store.update_flow_state.assert_called_once()

        # Verify event was added
        mock_store.add_event.assert_called_once()

    def test_write_verdict_with_manager_role(
        self,
        verdict_service: VerdictService,
        mock_store: MagicMock,
        mock_handoff_service: MagicMock,
    ) -> None:
        """Test writing a verdict with manager role."""
        # Setup
        mock_store.get_flow_state.return_value = {}

        with patch(
            "vibe3.services.verdict_service.SignatureService.resolve_for_branch"
        ) as mock_resolve:
            mock_resolve.return_value = "manager"

            # Execute
            record = verdict_service.write_verdict(
                verdict="PASS",
                reason="Code looks good",
                branch="test-branch",
            )

        # Assert
        assert record.role == "manager"

    def test_get_latest_verdict_exists(
        self,
        verdict_service: VerdictService,
        mock_store: MagicMock,
    ) -> None:
        """Test getting latest verdict when it exists."""
        # Setup
        verdict_data = {
            "verdict": "MAJOR",
            "actor": "reviewer",
            "role": "reviewer",
            "timestamp": "2026-04-22T08:00:00+00:00",
            "reason": "Test reason",
            "issues": None,
            "flow_branch": "test-branch",
        }
        mock_store.get_flow_state.return_value = {"latest_verdict": verdict_data}

        # Execute
        record = verdict_service.get_latest_verdict("test-branch")

        # Assert
        assert record is not None
        assert record.verdict == "MAJOR"
        assert record.actor == "reviewer"
        assert record.role == "reviewer"
        assert record.reason == "Test reason"

    def test_get_latest_verdict_not_exists(
        self,
        verdict_service: VerdictService,
        mock_store: MagicMock,
    ) -> None:
        """Test getting latest verdict when it doesn't exist."""
        # Setup
        mock_store.get_flow_state.return_value = None

        # Execute
        record = verdict_service.get_latest_verdict("test-branch")

        # Assert
        assert record is None

    def test_get_latest_verdict_no_verdict_field(
        self,
        verdict_service: VerdictService,
        mock_store: MagicMock,
    ) -> None:
        """Test getting latest verdict when field is missing."""
        # Setup
        mock_store.get_flow_state.return_value = {}  # No latest_verdict field

        # Execute
        record = verdict_service.get_latest_verdict("test-branch")

        # Assert
        assert record is None

    def test_extract_role_from_actor_known_role(
        self, verdict_service: VerdictService
    ) -> None:
        """Test extracting role from known role actor."""
        assert verdict_service._extract_role_from_actor("manager") == "manager"
        assert verdict_service._extract_role_from_actor("planner") == "planner"
        assert verdict_service._extract_role_from_actor("executor") == "executor"
        assert verdict_service._extract_role_from_actor("reviewer") == "reviewer"

    def test_extract_role_from_actor_with_prefix(
        self, verdict_service: VerdictService
    ) -> None:
        """Test extracting role from actor with role prefix."""
        assert verdict_service._extract_role_from_actor("manager/backend") == "manager"
        assert verdict_service._extract_role_from_actor("reviewer/claude") == "reviewer"

    def test_extract_role_from_actor_unknown(
        self, verdict_service: VerdictService
    ) -> None:
        """Test extracting role from unknown actor."""
        assert (
            verdict_service._extract_role_from_actor("claude/claude-sonnet-4-6")
            == "agent"
        )
        assert verdict_service._extract_role_from_actor("unknown") == "agent"


class TestVerdictRecord:
    """Test cases for VerdictRecord model."""

    def test_to_handoff_markdown_full(self) -> None:
        """Test converting verdict record to markdown with all fields."""
        record = VerdictRecord(
            verdict="MAJOR",
            actor="reviewer",
            role="reviewer",
            timestamp=datetime.now(UTC),
            reason="Found issues",
            issues="Missing tests",
            flow_branch="test-branch",
        )

        markdown = record.to_handoff_markdown()

        assert "verdict: MAJOR" in markdown
        assert "reason: Found issues" in markdown
        assert "issues: Missing tests" in markdown

    def test_to_handoff_markdown_minimal(self) -> None:
        """Test converting verdict record to markdown with minimal fields."""
        record = VerdictRecord(
            verdict="PASS",
            actor="manager",
            role="manager",
            timestamp=datetime.now(UTC),
            flow_branch="test-branch",
        )

        markdown = record.to_handoff_markdown()

        assert "verdict: PASS" in markdown
        assert "reason:" not in markdown
        assert "issues:" not in markdown
