"""Tests for code-auditor governance role utilities and context building."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from vibe3.models.orchestra_config import GovernanceConfig, OrchestraConfig
from vibe3.roles.governance import build_governance_snapshot_context
from vibe3.roles.governance_utils import resolve_test_path, select_audit_module
from vibe3.services.orchestra.status import OrchestraSnapshot

# ---------------------------------------------------------------------------
# select_audit_module
# ---------------------------------------------------------------------------


class TestSelectAuditModule:
    def test_returns_path_object(self, tmp_path: Path) -> None:
        _make_fake_src(tmp_path, ["services/flow_service.py"])
        result = select_audit_module(0, repo_root=tmp_path)
        assert isinstance(result, Path)

    def test_deterministic_for_same_tick(self, tmp_path: Path) -> None:
        _make_fake_src(tmp_path, ["services/flow_service.py", "commands/flow.py"])
        assert select_audit_module(0, tmp_path) == select_audit_module(0, tmp_path)

    def test_rotates_with_tick(self, tmp_path: Path) -> None:
        _make_fake_src(
            tmp_path,
            ["services/flow_service.py", "commands/flow.py", "models/flow.py"],
        )
        results = {select_audit_module(i, tmp_path) for i in range(3)}
        assert len(results) == 3

    def test_wraps_around_modulo(self, tmp_path: Path) -> None:
        files = ["a.py", "b.py"]
        _make_fake_src(tmp_path, files)
        assert select_audit_module(0, tmp_path) == select_audit_module(2, tmp_path)
        assert select_audit_module(1, tmp_path) == select_audit_module(3, tmp_path)

    def test_excludes_init_files(self, tmp_path: Path) -> None:
        _make_fake_src(
            tmp_path,
            ["services/__init__.py", "services/flow_service.py"],
        )
        result = select_audit_module(0, tmp_path)
        assert result.name != "__init__.py"

    def test_naturally_excludes_pycache_files(self, tmp_path: Path) -> None:
        # rglob("*.py") naturally excludes .pyc files, no filter needed
        src = tmp_path / "src" / "vibe3"
        src.mkdir(parents=True)
        cache = src / "__pycache__"
        cache.mkdir()
        (cache / "flow.cpython-312.pyc").touch()
        (src / "cli.py").write_text("")
        result = select_audit_module(0, tmp_path)
        assert "__pycache__" not in result.parts

    def test_fallback_when_no_candidates(self, tmp_path: Path) -> None:
        src = tmp_path / "src" / "vibe3"
        src.mkdir(parents=True)
        (src / "__init__.py").touch()
        result = select_audit_module(0, tmp_path)
        assert result == src / "cli.py"

    def test_selection_is_sorted_stable(self, tmp_path: Path) -> None:
        _make_fake_src(tmp_path, ["z_module.py", "a_module.py"])
        first = select_audit_module(0, tmp_path)
        assert first.name == "a_module.py"

    def test_uses_cwd_when_no_repo_root(self, tmp_path: Path, monkeypatch) -> None:
        _make_fake_src(tmp_path, ["services/flow_service.py"])
        monkeypatch.chdir(tmp_path)
        result = select_audit_module(0)
        assert result.name == "flow_service.py"


# ---------------------------------------------------------------------------
# resolve_test_path
# ---------------------------------------------------------------------------


class TestResolveTestPath:
    def test_top_level_module(self, tmp_path: Path) -> None:
        module = tmp_path / "src" / "vibe3" / "cli.py"
        result = resolve_test_path(module, repo_root=tmp_path)
        assert result == tmp_path / "tests" / "vibe3"

    def test_subpackage_module(self, tmp_path: Path) -> None:
        module = tmp_path / "src" / "vibe3" / "services" / "flow_service.py"
        result = resolve_test_path(module, repo_root=tmp_path)
        assert result == tmp_path / "tests" / "vibe3" / "services"

    def test_nested_subpackage(self, tmp_path: Path) -> None:
        module = tmp_path / "src" / "vibe3" / "domain" / "handlers" / "manager.py"
        result = resolve_test_path(module, repo_root=tmp_path)
        assert result == tmp_path / "tests" / "vibe3" / "domain" / "handlers"

    def test_returns_path_object(self, tmp_path: Path) -> None:
        module = tmp_path / "src" / "vibe3" / "cli.py"
        result = resolve_test_path(module, repo_root=tmp_path)
        assert isinstance(result, Path)

    def test_fallback_for_unrecognized_path(self, tmp_path: Path) -> None:
        module = tmp_path / "some" / "other" / "path.py"
        result = resolve_test_path(module, repo_root=tmp_path)
        assert result == tmp_path / "tests" / "vibe3"

    def test_uses_cwd_when_no_repo_root(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        module = Path("src/vibe3/services/flow_service.py")
        result = resolve_test_path(module)
        assert result == tmp_path / "tests" / "vibe3" / "services"


# ---------------------------------------------------------------------------
# build_governance_snapshot_context (code-auditor branch)
# ---------------------------------------------------------------------------


class TestBuildGovernanceSnapshotContextCodeAuditor:
    def test_returns_dict_for_code_auditor_material(self, tmp_path: Path) -> None:
        snapshot = _make_snapshot()
        config = _make_config()
        _make_fake_src(tmp_path, ["services/flow_service.py"])

        with (
            patch(
                "vibe3.roles.governance_utils.select_audit_module",
                return_value=tmp_path
                / "src"
                / "vibe3"
                / "services"
                / "flow_service.py",
            ),
            patch(
                "vibe3.roles.governance_utils.resolve_test_path",
                return_value=tmp_path / "tests" / "vibe3" / "services",
            ),
        ):
            result = build_governance_snapshot_context(
                snapshot,
                config=config,
                tick_count=0,
                material_override="code-auditor",
            )

        assert isinstance(result, dict)

    def test_scope_note_contains_module_path(self, tmp_path: Path) -> None:
        snapshot = _make_snapshot()
        config = _make_config()
        module_path = tmp_path / "src" / "vibe3" / "services" / "flow_service.py"

        with (
            patch(
                "vibe3.roles.governance_utils.select_audit_module",
                return_value=module_path,
            ),
            patch(
                "vibe3.roles.governance_utils.resolve_test_path",
                return_value=tmp_path / "tests" / "vibe3" / "services",
            ),
        ):
            result = build_governance_snapshot_context(
                snapshot,
                config=config,
                tick_count=0,
                material_override="code-auditor",
            )

        assert str(module_path) in result["scope_note"]

    def test_scope_note_contains_test_path(self, tmp_path: Path) -> None:
        snapshot = _make_snapshot()
        config = _make_config()
        module_path = tmp_path / "src" / "vibe3" / "services" / "flow_service.py"
        test_path = tmp_path / "tests" / "vibe3" / "services"

        with (
            patch(
                "vibe3.roles.governance_utils.select_audit_module",
                return_value=module_path,
            ),
            patch(
                "vibe3.roles.governance_utils.resolve_test_path", return_value=test_path
            ),
        ):
            result = build_governance_snapshot_context(
                snapshot,
                config=config,
                tick_count=0,
                material_override="code-auditor",
            )

        assert str(test_path) in result["scope_note"]

    def test_issue_scope_name_indicates_audit(self, tmp_path: Path) -> None:
        snapshot = _make_snapshot()
        config = _make_config()

        with (
            patch(
                "vibe3.roles.governance_utils.select_audit_module",
                return_value=tmp_path / "src" / "vibe3" / "cli.py",
            ),
            patch(
                "vibe3.roles.governance_utils.resolve_test_path",
                return_value=tmp_path / "tests" / "vibe3",
            ),
        ):
            result = build_governance_snapshot_context(
                snapshot,
                config=config,
                tick_count=0,
                material_override="code-auditor",
            )

        assert "审计" in result["issue_scope_name"]

    def test_does_not_call_github(self, tmp_path: Path) -> None:
        snapshot = _make_snapshot()
        config = _make_config()

        with (
            patch(
                "vibe3.roles.governance_utils.select_audit_module",
                return_value=tmp_path / "src" / "vibe3" / "cli.py",
            ),
            patch(
                "vibe3.roles.governance_utils.resolve_test_path",
                return_value=tmp_path / "tests" / "vibe3",
            ),
            patch("vibe3.roles.governance.GitHubClient") as mock_github,
        ):
            build_governance_snapshot_context(
                snapshot,
                config=config,
                tick_count=0,
                material_override="code-auditor",
            )

        mock_github.assert_not_called()


class TestBuildGovernanceSnapshotContextAuditObservation:
    def test_scope_orients_to_stable_status_commands(self) -> None:
        snapshot = _make_snapshot()
        result = build_governance_snapshot_context(
            snapshot,
            config=_make_config(),
            material_override="audit-observation",
        )

        assert result["issue_scope_name"] == "blocked/aborted flow observation"
        assert "flow status --all --format json" in result["scope_note"]
        assert "task status --all --format json" in result["scope_note"]
        assert "governance" in result["scope_note"]

    @patch("vibe3.roles.governance.GitHubClient")
    def test_does_not_call_github(self, mock_github) -> None:
        build_governance_snapshot_context(
            _make_snapshot(),
            config=_make_config(),
            material_override="audit-observation",
        )

        mock_github.assert_not_called()


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_fake_src(root: Path, relative_paths: list[str]) -> None:
    """Create fake Python source files under root/src/vibe3/."""
    base = root / "src" / "vibe3"
    base.mkdir(parents=True, exist_ok=True)
    for rel in relative_paths:
        target = base / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"# {rel}\n")


def _make_snapshot() -> OrchestraSnapshot:
    return OrchestraSnapshot(
        timestamp=0.0,
        server_running=True,
        active_issues=(),
        active_flows=0,
        active_worktrees=0,
        circuit_breaker_state="closed",
        circuit_breaker_failures=0,
        queued_issues=(),
    )


def _make_config() -> OrchestraConfig:
    return OrchestraConfig(
        repo="owner/repo",
        governance=GovernanceConfig(),
    )
