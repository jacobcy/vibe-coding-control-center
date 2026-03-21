"""Tests for handoff file operations."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.clients import SQLiteClient
from vibe3.clients.git_client import GitClient
from vibe3.exceptions import UserError
from vibe3.services.handoff_service import HandoffService


@pytest.fixture
def temp_git_dir():
    """Create a temporary git directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        git_dir = Path(tmpdir) / ".git"
        git_dir.mkdir()
        yield git_dir


@pytest.fixture
def mock_store():
    """Create a mock SQLiteClient."""
    return MagicMock(spec=SQLiteClient)


@pytest.fixture
def mock_git_client():
    """Create a mock GitClient."""
    client = MagicMock(spec=GitClient)
    client.get_current_branch.return_value = "feature/test-branch"
    client.get_git_common_dir.return_value = "/tmp/test-common-dir"
    return client


@pytest.fixture
def handoff_service(mock_store, mock_git_client):
    """Create a HandoffService instance with mocked dependencies."""
    return HandoffService(store=mock_store, git_client=mock_git_client)


class TestEnsureCurrentHandoff:
    """Tests for ensure_current_handoff method."""

    def test_ensure_current_handoff_creates_template(
        self, handoff_service, temp_git_dir, mock_git_client
    ):
        """Test that ensure_current_handoff creates template if not exists."""
        mock_git_client.get_git_common_dir.return_value = str(temp_git_dir)

        handoff_path = handoff_service.ensure_current_handoff()

        assert handoff_path.exists()
        content = handoff_path.read_text()
        assert "# Handoff: feature/test-branch" in content
        assert "lightweight handoff file" in content
        assert "## Summary" in content
        assert "## Findings" in content
        assert "## Blockers" in content
        assert "## Next Actions" in content
        assert "## Key Files" in content
        assert "## Evidence Refs" in content
        assert "## Updates" in content

    def test_ensure_current_handoff_existing_file_is_idempotent(
        self, handoff_service, temp_git_dir, mock_git_client
    ):
        """Test that existing file is returned without overwrite by default."""
        mock_git_client.get_git_common_dir.return_value = str(temp_git_dir)

        handoff_path = handoff_service.ensure_current_handoff()
        original_content = handoff_path.read_text()

        handoff_path2 = handoff_service.ensure_current_handoff()
        assert handoff_path == handoff_path2
        assert handoff_path.read_text() == original_content

    def test_ensure_current_handoff_force_overwrites_existing_file(
        self, handoff_service, temp_git_dir, mock_git_client
    ):
        """Test that force=True rewrites existing file with fresh template."""
        mock_git_client.get_git_common_dir.return_value = str(temp_git_dir)

        handoff_path = handoff_service.ensure_current_handoff()
        handoff_path.write_text("# Custom handoff\n")

        overwritten_path = handoff_service.ensure_current_handoff(force=True)

        assert overwritten_path == handoff_path
        assert "# Custom handoff" not in handoff_path.read_text()


class TestReadCurrentHandoff:
    """Tests for read_current_handoff method."""

    def test_read_current_handoff(
        self, handoff_service, temp_git_dir, mock_git_client
    ):
        """Test reading current handoff file."""
        mock_git_client.get_git_common_dir.return_value = str(temp_git_dir)

        handoff_service.ensure_current_handoff()

        content = handoff_service.read_current_handoff()
        assert "# Handoff: feature/test-branch" in content

    def test_read_current_handoff_not_found(self, handoff_service):
        """Test reading non-existent handoff file raises error."""
        with pytest.raises(UserError):
            handoff_service.read_current_handoff()


class TestAppendCurrentHandoff:
    """Tests for append_current_handoff method."""

    def test_append_current_handoff_creates_file_if_missing(
        self, handoff_service, temp_git_dir, mock_git_client
    ):
        """Test append creates current.md when missing."""
        mock_git_client.get_git_common_dir.return_value = str(temp_git_dir)

        handoff_path = handoff_service.append_current_handoff(
            message="Need to unify event taxonomy",
            actor="codex/gpt-5.4",
            kind="finding",
        )

        content = handoff_path.read_text()
        assert handoff_path.exists()
        assert "## Updates" in content
        assert "codex/gpt-5.4" in content
        assert "finding" in content
        assert "Need to unify event taxonomy" in content

    def test_append_current_handoff_appends_to_updates_section(
        self, handoff_service, temp_git_dir, mock_git_client
    ):
        """Test append adds a new block at the end of updates."""
        mock_git_client.get_git_common_dir.return_value = str(temp_git_dir)
        handoff_service.ensure_current_handoff()

        handoff_service.append_current_handoff(
            message="Blocked on GitHub Project mapping",
            actor="claude/sonnet-4.6",
            kind="blocker",
        )

        content = handoff_service.read_current_handoff()
        assert "## Updates" in content
        assert "Blocked on GitHub Project mapping" in content
        assert "claude/sonnet-4.6" in content
        assert "blocker" in content


class TestGetHandoffDir:
    """Tests for _get_handoff_dir method."""

    def test_get_handoff_dir_sanitizes_branch_name(
        self, handoff_service, temp_git_dir, mock_git_client
    ):
        """Test that branch name is sanitized for use in directory path."""
        mock_git_client.get_git_common_dir.return_value = str(temp_git_dir)
        mock_git_client.get_current_branch.return_value = "feature/complex/branch/name"

        handoff_dir = handoff_service._get_handoff_dir()

        # Branch name should be sanitized and include hash suffix for uniqueness
        assert "feature-complex-branch-name" in str(handoff_dir)
        # Should have a hash suffix (8 hex chars)
        import re
        assert re.search(r"-[a-f0-9]{8}$", handoff_dir.name)
        assert handoff_dir.exists()

    def test_get_handoff_dir_handles_leading_trailing_dashes(
        self, handoff_service, temp_git_dir, mock_git_client
    ):
        """Test that leading/trailing dashes are stripped."""
        mock_git_client.get_git_common_dir.return_value = str(temp_git_dir)
        mock_git_client.get_current_branch.return_value = "-branch-with-dashes-"

        handoff_dir = handoff_service._get_handoff_dir()

        # Dashes should be stripped, with hash suffix added
        assert "branch-with-dashes" in str(handoff_dir)

    def test_get_handoff_dir_fallback_for_empty_name(
        self, handoff_service, temp_git_dir, mock_git_client
    ):
        """Test fallback to 'default' when branch name sanitizes to empty."""
        mock_git_client.get_git_common_dir.return_value = str(temp_git_dir)
        mock_git_client.get_current_branch.return_value = "---"

        handoff_dir = handoff_service._get_handoff_dir()

        # Should use 'default' prefix with hash suffix
        assert "default" in str(handoff_dir)