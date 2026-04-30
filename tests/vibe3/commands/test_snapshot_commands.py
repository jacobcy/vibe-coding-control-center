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
        lambda branch: Path(f"/tmp/baseline_{branch.replace('/', '-')}.json"),
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
