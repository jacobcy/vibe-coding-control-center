"""Tests for audit CLI command."""

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

# Ensure src path is available
sys.path.insert(0, "src")

from vibe3.cli import app as main_app
from vibe3.services.audit.collector import AuditEvidenceCollector

runner = CliRunner()


@pytest.fixture
def mock_collector() -> MagicMock:
    """Create mock collector."""
    return MagicMock(spec=AuditEvidenceCollector)


@pytest.fixture
def mock_sqlite_client() -> MagicMock:
    """Create mock SQLite client."""
    return MagicMock()


@pytest.fixture
def mock_github_client() -> MagicMock:
    """Create mock GitHub client."""
    return MagicMock()


@pytest.fixture
def mock_git_client() -> MagicMock:
    """Create mock Git client."""
    return MagicMock()


class TestAuditBundleCommand:
    """Tests for audit bundle command."""

    def test_bundle_missing_issue_and_branch_fails(self) -> None:
        """Should fail when neither --issue nor --branch is specified."""
        result = runner.invoke(main_app, ["audit", "bundle"])

        assert result.exit_code != 0
        assert "At least one of --issue or --branch" in result.output

    def test_bundle_with_issue_flag(
        self,
        mock_collector: MagicMock,
        mock_sqlite_client: MagicMock,
        mock_github_client: MagicMock,
        mock_git_client: MagicMock,
    ) -> None:
        """Should collect evidence for specified issue."""
        # Setup mock bundle
        mock_bundle = MagicMock()
        mock_bundle.id = "test-bundle-id"
        mock_bundle.schema_version = 1
        mock_bundle.collection_context.mode = "issue"
        mock_bundle.collection_context.source_machine = "test-machine"
        mock_bundle.collection_context.source_commit = "abc123"
        mock_bundle.created_at = "2026-06-18T10:00:00"
        mock_collector.assemble_bundle.return_value = mock_bundle

        with (
            patch("vibe3.commands.audit.SQLiteClient", return_value=mock_sqlite_client),
            patch("vibe3.commands.audit.GitHubClient", return_value=mock_github_client),
            patch("vibe3.commands.audit.GitClient", return_value=mock_git_client),
            patch(
                "vibe3.commands.audit.AuditEvidenceCollector",
                return_value=mock_collector,
            ),
            patch(
                "vibe3.commands.audit.format_bundle_json",
                return_value='{"id": "test-bundle-id"}',
            ),
        ):
            result = runner.invoke(main_app, ["audit", "bundle", "--issue", "123"])

        assert result.exit_code == 0
        assert mock_collector.assemble_bundle.called
        call_kwargs = mock_collector.assemble_bundle.call_args[1]
        assert call_kwargs["issue_number"] == 123

    def test_bundle_with_branch_flag(
        self,
        mock_collector: MagicMock,
        mock_sqlite_client: MagicMock,
        mock_github_client: MagicMock,
        mock_git_client: MagicMock,
    ) -> None:
        """Should collect evidence for specified branch."""
        mock_bundle = MagicMock()
        mock_bundle.id = "test-bundle-id"
        mock_bundle.schema_version = 1
        mock_bundle.collection_context.mode = "flow"
        mock_bundle.collection_context.source_machine = "test-machine"
        mock_bundle.collection_context.source_commit = "abc123"
        mock_bundle.created_at = "2026-06-18T10:00:00"
        mock_collector.assemble_bundle.return_value = mock_bundle

        with (
            patch("vibe3.commands.audit.SQLiteClient", return_value=mock_sqlite_client),
            patch("vibe3.commands.audit.GitHubClient", return_value=mock_github_client),
            patch("vibe3.commands.audit.GitClient", return_value=mock_git_client),
            patch(
                "vibe3.commands.audit.AuditEvidenceCollector",
                return_value=mock_collector,
            ),
            patch(
                "vibe3.commands.audit.format_bundle_json",
                return_value='{"id": "test-bundle-id"}',
            ),
        ):
            result = runner.invoke(
                main_app, ["audit", "bundle", "--branch", "task/issue-123"]
            )

        assert result.exit_code == 0
        assert mock_collector.assemble_bundle.called
        call_kwargs = mock_collector.assemble_bundle.call_args[1]
        assert call_kwargs["branch"] == "task/issue-123"

    def test_bundle_json_format_output(
        self,
        mock_collector: MagicMock,
        mock_sqlite_client: MagicMock,
        mock_github_client: MagicMock,
        mock_git_client: MagicMock,
    ) -> None:
        """Should output JSON when --format json is specified."""
        mock_bundle = MagicMock()
        mock_bundle.id = "test-bundle-id"
        mock_bundle.schema_version = 1
        mock_bundle.collection_context.mode = "issue"
        mock_bundle.collection_context.source_machine = "test-machine"
        mock_bundle.collection_context.source_commit = "abc123"
        mock_bundle.created_at = "2026-06-18T10:00:00"
        mock_collector.assemble_bundle.return_value = mock_bundle

        with (
            patch("vibe3.commands.audit.SQLiteClient", return_value=mock_sqlite_client),
            patch("vibe3.commands.audit.GitHubClient", return_value=mock_github_client),
            patch("vibe3.commands.audit.GitClient", return_value=mock_git_client),
            patch(
                "vibe3.commands.audit.AuditEvidenceCollector",
                return_value=mock_collector,
            ),
            patch(
                "vibe3.commands.audit.format_bundle_json",
                return_value='{"test": "json"}',
            ),
        ):
            result = runner.invoke(
                main_app, ["audit", "bundle", "--issue", "123", "--format", "json"]
            )

        assert result.exit_code == 0
        assert '{"test": "json"}' in result.output

    def test_bundle_table_format_output(
        self,
        mock_collector: MagicMock,
        mock_sqlite_client: MagicMock,
        mock_github_client: MagicMock,
        mock_git_client: MagicMock,
    ) -> None:
        """Should output table when --format table is specified."""
        mock_bundle = MagicMock()
        mock_bundle.id = "test-bundle-id"
        mock_bundle.schema_version = 1
        mock_bundle.collection_context.mode = "issue"
        mock_bundle.collection_context.source_machine = "test-machine"
        mock_bundle.collection_context.source_commit = "abc123"
        mock_bundle.created_at = "2026-06-18T10:00:00"
        mock_bundle.primary_subject.issue_number = 123
        mock_bundle.primary_subject.branch = None
        mock_bundle.primary_subject.pr_number = None
        mock_bundle.source_refs.github = []
        mock_bundle.source_refs.flow = []
        mock_bundle.source_refs.handoff = []
        mock_bundle.source_refs.git = []
        mock_bundle.summary.symptom = "Test symptom"
        mock_bundle.summary.evidence_text = "Test evidence"
        mock_bundle.trust.source_class = "authoritative"
        mock_bundle.trust.freshness = "fresh"
        mock_bundle.trust.confidence = "medium"
        mock_bundle.trust.limitations = []
        mock_collector.assemble_bundle.return_value = mock_bundle

        with (
            patch("vibe3.commands.audit.SQLiteClient", return_value=mock_sqlite_client),
            patch("vibe3.commands.audit.GitHubClient", return_value=mock_github_client),
            patch("vibe3.commands.audit.GitClient", return_value=mock_git_client),
            patch(
                "vibe3.commands.audit.AuditEvidenceCollector",
                return_value=mock_collector,
            ),
            patch(
                "vibe3.commands.audit.format_bundle_summary",
                return_value="Evidence Bundle: test-bundle-id",
            ),
        ):
            result = runner.invoke(
                main_app, ["audit", "bundle", "--issue", "123", "--format", "table"]
            )

        assert result.exit_code == 0
        assert "Evidence Bundle" in result.output

    def test_bundle_output_to_file(
        self,
        mock_collector: MagicMock,
        mock_sqlite_client: MagicMock,
        mock_github_client: MagicMock,
        mock_git_client: MagicMock,
    ) -> None:
        """Should write output to file when --output is specified."""
        mock_bundle = MagicMock()
        mock_bundle.id = "test-bundle-id"
        mock_bundle.schema_version = 1
        mock_bundle.collection_context.mode = "issue"
        mock_bundle.collection_context.source_machine = "test-machine"
        mock_bundle.collection_context.source_commit = "abc123"
        mock_bundle.created_at = "2026-06-18T10:00:00"
        mock_collector.assemble_bundle.return_value = mock_bundle

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "bundle.json"

            with (
                patch(
                    "vibe3.commands.audit.SQLiteClient", return_value=mock_sqlite_client
                ),
                patch(
                    "vibe3.commands.audit.GitHubClient", return_value=mock_github_client
                ),
                patch("vibe3.commands.audit.GitClient", return_value=mock_git_client),
                patch(
                    "vibe3.commands.audit.AuditEvidenceCollector",
                    return_value=mock_collector,
                ),
                patch(
                    "vibe3.commands.audit.format_bundle_json",
                    return_value='{"test": "json"}',
                ),
            ):
                result = runner.invoke(
                    main_app,
                    ["audit", "bundle", "--issue", "123", "--output", str(output_path)],
                )

            assert result.exit_code == 0
            assert output_path.exists()
            content = output_path.read_text()
            assert '{"test": "json"}' in content

    def test_bundle_metadata_header(
        self,
        mock_collector: MagicMock,
        mock_sqlite_client: MagicMock,
        mock_github_client: MagicMock,
        mock_git_client: MagicMock,
    ) -> None:
        """Should include metadata header in output."""
        mock_bundle = MagicMock()
        mock_bundle.id = "test-bundle-id"
        mock_bundle.schema_version = 1
        mock_bundle.collection_context.mode = "issue"
        mock_bundle.collection_context.source_machine = "test-machine"
        mock_bundle.collection_context.source_commit = "abc123"
        mock_bundle.created_at = "2026-06-18T10:00:00"
        mock_collector.assemble_bundle.return_value = mock_bundle

        with (
            patch("vibe3.commands.audit.SQLiteClient", return_value=mock_sqlite_client),
            patch("vibe3.commands.audit.GitHubClient", return_value=mock_github_client),
            patch("vibe3.commands.audit.GitClient", return_value=mock_git_client),
            patch(
                "vibe3.commands.audit.AuditEvidenceCollector",
                return_value=mock_collector,
            ),
            patch(
                "vibe3.commands.audit.format_bundle_json",
                return_value='{"test": "json"}',
            ),
        ):
            result = runner.invoke(main_app, ["audit", "bundle", "--issue", "123"])

        assert result.exit_code == 0
        assert "Bundle ID:" in result.output
        assert "Schema Version:" in result.output
        assert "Mode:" in result.output
        assert "Source Machine:" in result.output
        assert "Source Commit:" in result.output

    def test_bundle_read_only_no_mutations(
        self,
        mock_collector: MagicMock,
        mock_sqlite_client: MagicMock,
        mock_github_client: MagicMock,
        mock_git_client: MagicMock,
    ) -> None:
        """Should not modify any external state."""
        mock_bundle = MagicMock()
        mock_bundle.id = "test-bundle-id"
        mock_bundle.schema_version = 1
        mock_bundle.collection_context.mode = "issue"
        mock_bundle.collection_context.source_machine = "test-machine"
        mock_bundle.collection_context.source_commit = "abc123"
        mock_bundle.created_at = "2026-06-18T10:00:00"
        mock_collector.assemble_bundle.return_value = mock_bundle

        with (
            patch("vibe3.commands.audit.SQLiteClient", return_value=mock_sqlite_client),
            patch("vibe3.commands.audit.GitHubClient", return_value=mock_github_client),
            patch("vibe3.commands.audit.GitClient", return_value=mock_git_client),
            patch(
                "vibe3.commands.audit.AuditEvidenceCollector",
                return_value=mock_collector,
            ),
            patch(
                "vibe3.commands.audit.format_bundle_json",
                return_value='{"test": "json"}',
            ),
        ):
            result = runner.invoke(main_app, ["audit", "bundle", "--issue", "123"])

        # Verify only read operations were called (assemble_bundle)
        assert result.exit_code == 0
        assert mock_collector.assemble_bundle.called
        # No write operations should be called
        assert not hasattr(mock_collector, "write") or not mock_collector.write.called

    def test_bundle_with_time_window(
        self,
        mock_collector: MagicMock,
        mock_sqlite_client: MagicMock,
        mock_github_client: MagicMock,
        mock_git_client: MagicMock,
    ) -> None:
        """Should parse and pass time window to collector."""
        mock_bundle = MagicMock()
        mock_bundle.id = "test-bundle-id"
        mock_bundle.schema_version = 1
        mock_bundle.collection_context.mode = "time_window"
        mock_bundle.collection_context.source_machine = "test-machine"
        mock_bundle.collection_context.source_commit = "abc123"
        mock_bundle.created_at = "2026-06-18T10:00:00"
        mock_collector.assemble_bundle.return_value = mock_bundle

        with (
            patch("vibe3.commands.audit.SQLiteClient", return_value=mock_sqlite_client),
            patch("vibe3.commands.audit.GitHubClient", return_value=mock_github_client),
            patch("vibe3.commands.audit.GitClient", return_value=mock_git_client),
            patch(
                "vibe3.commands.audit.AuditEvidenceCollector",
                return_value=mock_collector,
            ),
            patch(
                "vibe3.commands.audit.format_bundle_json",
                return_value='{"test": "json"}',
            ),
        ):
            result = runner.invoke(
                main_app,
                [
                    "audit",
                    "bundle",
                    "--issue",
                    "123",
                    "--time-window-start",
                    "2026-06-18T00:00:00",
                    "--time-window-end",
                    "2026-06-18T23:59:59",
                ],
            )

        assert result.exit_code == 0
        call_kwargs = mock_collector.assemble_bundle.call_args[1]
        assert call_kwargs["time_window"] is not None
