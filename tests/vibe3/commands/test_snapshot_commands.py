"""Tests for vibe snapshot command behavior."""

from pathlib import Path
from unittest.mock import MagicMock

from typer.testing import CliRunner

from vibe3.commands.snapshot import app
from vibe3.models.snapshot import StructureMetrics, StructureSnapshot

runner = CliRunner()


def _snapshot(
    snapshot_id: str, *, baseline_for: str | None = None
) -> StructureSnapshot:
    return StructureSnapshot(
        snapshot_id=snapshot_id,
        branch="feature/test",
        commit="abcdef1234567890",
        commit_short="abcdef1",
        created_at="2026-04-30T10:00:00+00:00",
        root="src/vibe3",
        files=[],
        modules=[],
        dependencies=[],
        metrics=StructureMetrics(
            total_files=10,
            total_loc=1000,
            total_functions=50,
            python_files=10,
        ),
        baseline_for=baseline_for,
    )


def test_snapshot_save_as_baseline_json_outputs_saved_baseline(monkeypatch):
    """--as-baseline JSON output should describe the saved branch baseline."""
    from vibe3.commands import snapshot as snapshot_command

    fake_git = MagicMock()
    fake_git.get_current_branch.return_value = "feature/test"
    monkeypatch.setattr("vibe3.clients.git_client.GitClient", lambda: fake_git)
    monkeypatch.setattr(
        snapshot_command.snapshot_service,
        "save_branch_baseline",
        lambda branch, force=False: Path(
            f"/tmp/baseline_{branch.replace('/', '-')}.json"
        ),
    )
    monkeypatch.setattr(
        snapshot_command.snapshot_service,
        "load_branch_baseline",
        lambda branch: _snapshot("saved-baseline", baseline_for=branch),
    )
    monkeypatch.setattr(
        snapshot_command.snapshot_service,
        "build_snapshot",
        lambda: _snapshot("second-build"),
    )

    result = runner.invoke(app, ["save", "--as-baseline", "--json"])

    assert result.exit_code == 0
    assert '"snapshot_id": "saved-baseline"' in result.output
    assert '"baseline_for": "feature/test"' in result.output
    assert "second-build" not in result.output


def test_snapshot_save_as_baseline_force(monkeypatch):
    """--force flag should be passed through to save_branch_baseline."""
    from vibe3.commands import snapshot as snapshot_command

    fake_git = MagicMock()
    fake_git.get_current_branch.return_value = "feature/test"
    monkeypatch.setattr("vibe3.clients.git_client.GitClient", lambda: fake_git)

    # Track calls to save_branch_baseline
    calls = []

    def mock_save_branch_baseline(branch: str, force: bool = False):
        calls.append((branch, force))
        return Path(f"/tmp/baseline_{branch.replace('/', '-')}.json")

    monkeypatch.setattr(
        snapshot_command.snapshot_service,
        "save_branch_baseline",
        mock_save_branch_baseline,
    )
    monkeypatch.setattr(
        snapshot_command.snapshot_service,
        "load_branch_baseline",
        lambda branch: _snapshot("saved-baseline", baseline_for=branch),
    )

    # Test without --force (default force=False)
    result = runner.invoke(app, ["save", "--as-baseline"])
    assert result.exit_code == 0
    assert len(calls) == 1
    assert calls[0] == ("feature/test", False)

    # Test with --force
    calls.clear()
    result = runner.invoke(app, ["save", "--as-baseline", "--force"])
    assert result.exit_code == 0
    assert len(calls) == 1
    assert calls[0] == ("feature/test", True)

    # Test with --no-force
    calls.clear()
    result = runner.invoke(app, ["save", "--as-baseline", "--no-force"])
    assert result.exit_code == 0
    assert len(calls) == 1
    assert calls[0] == ("feature/test", False)


def test_repair_baselines_success(monkeypatch):
    """Test repair-baselines command reports counts and exits successfully."""
    from vibe3.commands import snapshot as snapshot_command

    # Mock backfill_baseline_registry to return success counts
    monkeypatch.setattr(
        snapshot_command.snapshot_service,
        "backfill_baseline_registry",
        lambda: {"registered": 100, "skipped": 10, "failed": 0},
    )

    result = runner.invoke(app, ["repair-baselines"])

    assert result.exit_code == 0
    assert "Repair complete" in result.output
    assert "Registered: 100" in result.output
    assert "Skipped: 10" in result.output
    assert "Failed: 0" in result.output


def test_repair_baselines_with_failures(monkeypatch):
    """Test repair-baselines exits with code 1 when there are failures."""
    from vibe3.commands import snapshot as snapshot_command

    # Mock backfill_baseline_registry to return failure counts
    monkeypatch.setattr(
        snapshot_command.snapshot_service,
        "backfill_baseline_registry",
        lambda: {"registered": 80, "skipped": 5, "failed": 15},
    )

    result = runner.invoke(app, ["repair-baselines"])

    assert result.exit_code == 1
    assert "Repair complete" in result.output
    assert "Registered: 80" in result.output
    assert "Skipped: 5" in result.output
    assert "Failed: 15" in result.output
    assert "Warning" in result.output
