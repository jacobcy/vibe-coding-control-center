"""T050: spec-kit bridge extension — metadata + fixture hook behavior (US3).

Spec 012 US3, scenarios 1-4 + FR-014/015/016/017/018, SC-003:

1. after specify  -> spec_ref recorded
2. after plan     -> plan_ref recorded
3. implementation completion -> report_ref recorded
4. review completion -> audit_ref recorded
+ direct-superspec exit path still publishes (FR-017)
+ idempotent when both the hook path and the exit path observe the same
  artifact (FR-018)
+ external spec-kit/superspec sources stay untouched (FR-014)
+ adapters call PUBLIC Vibe handoff commands only (FR-015/016)

The adapter is a thin shell bridge (``hooks/publish-artifact.sh``) that
resolves a generated spec-kit artifact and invokes ``vibe3 handoff <kind>``,
which is itself the canonical writer (US1 #3311). The behavior tests below
drive that writer directly against a temp flow to prove the refs land and
stay idempotent — the CLI surface the adapter calls is already covered by
``tests/vibe3/commands/test_flow_update_spec.py`` and
``tests/vibe3/services/test_handoff_service.py``.
"""

import os
import stat
import subprocess
from pathlib import Path

import pytest
import yaml

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.services.handoff import HandoffService

REPO_ROOT = Path(__file__).resolve().parents[3]
EXT_DIR = REPO_ROOT / ".specify" / "extensions" / "vibe-spec-bridge"
SUPER_SPEC_DIR = REPO_ROOT / ".specify" / "extensions" / "superspec"
EXTENSIONS_CONFIG = REPO_ROOT / ".specify" / "extensions.yml"
ROOT_GITIGNORE = REPO_ROOT / ".gitignore"


# --- A. extension.yml metadata (T051) ---------------------------------------


def _load_extension_yml() -> dict:
    assert (
        EXT_DIR.is_dir()
    ), f"vibe-spec-bridge extension missing at {EXT_DIR} (FR-014: project-owned)"
    return yaml.safe_load((EXT_DIR / "extension.yml").read_text(encoding="utf-8"))


def test_extension_yml_declares_bridge_id() -> None:
    """FR-014: the bridge is a project-owned extension with a stable id."""
    meta = _load_extension_yml()
    assert meta["extension"]["id"] == "vibe-spec-bridge"


def test_extension_yml_declares_four_lifecycle_hooks() -> None:
    """FR-015: all four artifact kinds are wired to a lifecycle hook."""
    meta = _load_extension_yml()
    hooks = meta["hooks"]
    for lifecycle in ("after_specify", "after_plan", "after_implement", "after_review"):
        assert lifecycle in hooks, f"missing lifecycle hook: {lifecycle}"


def test_project_extension_is_declared_for_runtime_discovery() -> None:
    """Tracked config must let bootstrap materialize spec-kit's registry."""
    config = yaml.safe_load(EXTENSIONS_CONFIG.read_text(encoding="utf-8"))

    assert "vibe-spec-bridge" in config["installed"]
    registered = {
        (hook_name, hook["extension"], hook["command"])
        for hook_name, hooks in config["hooks"].items()
        for hook in hooks
    }
    assert (
        "after_specify",
        "vibe-spec-bridge",
        "speckit.vibe-spec-bridge.publish-spec",
    ) in registered
    assert (
        "after_plan",
        "vibe-spec-bridge",
        "speckit.vibe-spec-bridge.publish-plan",
    ) in registered
    assert (
        "after_implement",
        "vibe-spec-bridge",
        "speckit.vibe-spec-bridge.publish-report",
    ) in registered
    assert (
        "after_review",
        "vibe-spec-bridge",
        "speckit.vibe-spec-bridge.publish-audit",
    ) in registered


def test_project_extension_ignores_dev_materialization() -> None:
    """Local installs generate command caches that are not extension source."""
    patterns = ROOT_GITIGNORE.read_text(encoding="utf-8").splitlines()

    assert ".specify/extensions/vibe-spec-bridge/.specify-dev/" in patterns


def test_extension_yml_hooks_map_to_correct_publish_commands() -> None:
    """Each lifecycle hook maps to the publish command for its artifact kind
    (spec -> spec, plan -> plan, implement -> report, review -> audit)."""
    meta = _load_extension_yml()
    expected = {
        "after_specify": "publish-spec",
        "after_plan": "publish-plan",
        "after_implement": "publish-report",
        "after_review": "publish-audit",
    }
    for lifecycle, suffix in expected.items():
        cmd = meta["hooks"][lifecycle]["command"]
        assert cmd == f"speckit.vibe-spec-bridge.{suffix}", lifecycle


def test_extension_yml_commands_use_namespace_prefix() -> None:
    """spec-kit namespace rule: every command is prefixed ``speckit.<id>.*``."""
    meta = _load_extension_yml()
    for cmd in meta["provides"]["commands"]:
        assert cmd["name"].startswith("speckit.vibe-spec-bridge."), cmd["name"]
        # The command file must exist on disk.
        fname = cmd["name"].split(".", 2)[2] + ".md"
        assert (EXT_DIR / "commands" / fname).is_file(), fname


def test_extension_yml_additive_hooks_do_not_collide_with_superspec() -> None:
    """after_specify/after_plan are ADDITIVE — superspec only declares
    after_tasks/before_implement/after_implement. The bridge must not
    redefine a hook superspec already owns.

    superspec is an externally-cloned extension (gitignored — absent in CI),
    so its hook set is treated as a stable contract and hard-coded. When
    superspec happens to be present locally, the on-disk manifest is
    cross-checked against the contract.
    """
    bridge = _load_extension_yml()["hooks"]
    bridge_hooks = set(bridge.keys())
    super_yml = SUPER_SPEC_DIR / "extension.yml"
    if super_yml.is_file():
        super_meta = yaml.safe_load(super_yml.read_text(encoding="utf-8"))
        super_hooks = set(super_meta["hooks"].keys())
    else:
        super_hooks = {"after_tasks", "before_implement", "after_implement"}
    # after_implement is allowed to co-exist (bridge publishes report;
    # superspec runs review) as long as both stay optional. The other three
    # hooks are additive and MUST be bridge-only.
    additive_only = bridge_hooks - super_hooks
    assert {"after_specify", "after_plan", "after_review"} <= additive_only
    # after_specify/after_plan are mandatory (#3331): spec_ref/plan_ref MUST
    # land for review verification. after_implement/after_review stay optional
    # (report/audit are post-completion records). The adapter degrades
    # gracefully so a mandatory hook never blocks specify/plan.
    mandatory = {"after_specify", "after_plan"}
    for lifecycle in bridge:
        expected_optional = lifecycle not in mandatory
        assert bridge[lifecycle].get("optional", False) is expected_optional, lifecycle


# --- B. publish-artifact.sh adapter (T052/T053) -----------------------------


def test_publish_artifact_adapter_exists_and_executable() -> None:
    """T052/T053: the shared adapter is present and executable."""
    adapter = EXT_DIR / "hooks" / "publish-artifact.sh"
    assert adapter.is_file(), "hooks/publish-artifact.sh missing"
    assert adapter.stat().st_mode & stat.S_IXUSR, "adapter not executable"


def _adapter_code_lines() -> list[str]:
    """Adapter source lines with full-line comments stripped (keeps inline)."""
    text = (EXT_DIR / "hooks" / "publish-artifact.sh").read_text(encoding="utf-8")
    return [
        ln for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")
    ]


def test_publish_artifact_adapter_invokes_public_handoff_only() -> None:
    """FR-015/016: the adapter reaches the flow ONLY through ``vibe3 handoff``
    — it never writes ``.git/vibe3`` or decides label/state transitions."""
    lines = _adapter_code_lines()
    joined = "\n".join(lines)
    assert "vibe3 handoff" in joined, "adapter must call the public handoff surface"
    # No direct shared-state write: forbid redirection / mkdir into the
    # protected handoff store path.
    for forbidden in ("> .git/vibe3", ">> .git/vibe3", ".git/vibe3/handoff"):
        assert forbidden not in joined, f"adapter writes shared state: {forbidden}"


def test_publish_artifact_adapter_maps_kind_to_artifact_path() -> None:
    """The adapter resolves each kind to its spec-kit artifact path."""
    joined = "\n".join(_adapter_code_lines())
    assert "spec.md" in joined
    assert "plan.md" in joined
    assert "report" in joined and "audit" in joined


def test_publish_artifact_adapter_accepts_all_four_kinds() -> None:
    """The adapter's kind switch covers spec|plan|report|audit."""
    joined = "\n".join(_adapter_code_lines())
    for kind in ("spec", "plan", "report", "audit"):
        assert kind in joined, f"adapter missing kind: {kind}"


def _write_vibe3_probe(bin_dir: Path) -> None:
    bin_dir.mkdir()
    probe = bin_dir / "vibe3"
    probe.write_text("#!/bin/sh\nprintf '%s\\n' \"$*\"\n", encoding="utf-8")
    probe.chmod(probe.stat().st_mode | stat.S_IXUSR)


def test_explicit_artifact_does_not_require_spec_directory(tmp_path: Path) -> None:
    """Report/audit exit paths may publish without any spec directory."""
    artifact = tmp_path / "docs" / "report.md"
    artifact.parent.mkdir()
    artifact.write_text("# Report\n", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    _write_vibe3_probe(bin_dir)

    result = subprocess.run(
        [
            str(EXT_DIR / "hooks" / "publish-artifact.sh"),
            "report",
            "--artifact",
            "docs/report.md",
            "--branch",
            "dev/issue-3312",
        ],
        cwd=tmp_path,
        env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == (
        "handoff report docs/report.md --branch dev/issue-3312"
    )


def test_implicit_artifact_selects_greatest_spec_directory_by_name(
    tmp_path: Path,
) -> None:
    """Fallback selection follows documented NNN/name ordering, not mtime."""
    old = tmp_path / ".specify" / "specs" / "012-old"
    current = tmp_path / ".specify" / "specs" / "013-current"
    old.mkdir(parents=True)
    current.mkdir(parents=True)
    (old / "spec.md").write_text("# Old\n", encoding="utf-8")
    (current / "spec.md").write_text("# Current\n", encoding="utf-8")
    os.utime(old, (2_000_000_000, 2_000_000_000))
    os.utime(current, (1_000_000_000, 1_000_000_000))
    bin_dir = tmp_path / "bin"
    _write_vibe3_probe(bin_dir)

    result = subprocess.run(
        [str(EXT_DIR / "hooks" / "publish-artifact.sh"), "spec"],
        cwd=tmp_path,
        env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == ("handoff spec .specify/specs/013-current/spec.md")


def _write_failing_vibe3_probe(bin_dir: Path) -> None:
    """A vibe3 stub that always fails (simulates no flow bound / write error)."""
    bin_dir.mkdir()
    probe = bin_dir / "vibe3"
    probe.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    probe.chmod(probe.stat().st_mode | stat.S_IXUSR)


def test_publish_artifact_adapter_degrades_gracefully_static() -> None:
    """#3331: the adapter source contains the non-blocking degradation pattern."""
    joined = "\n".join(_adapter_code_lines())
    assert "skipping publish (non-blocking)" in joined
    assert "if !" in joined and "exit 0" in joined


def test_publish_artifact_adapter_non_blocking_when_handoff_fails(
    tmp_path: Path,
) -> None:
    """#3331: when vibe3 handoff fails, the adapter exits 0 (non-blocking) so
    the mandatory after_specify/after_plan hook does not stall specify/plan."""
    spec_dir = tmp_path / ".specify" / "specs" / "013-test"
    spec_dir.mkdir(parents=True)
    (spec_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    _write_failing_vibe3_probe(bin_dir)

    result = subprocess.run(
        [str(EXT_DIR / "hooks" / "publish-artifact.sh"), "spec"],
        cwd=tmp_path,
        env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, "adapter must not block on handoff failure"
    assert "skipping publish (non-blocking)" in result.stderr


# --- C. EXIT_CONTRACT + FR-014 (T054) ---------------------------------------


def test_exit_contract_document_describes_direct_superspec_path() -> None:
    """FR-017: a documented exit contract lets a direct superspec skill path
    still publish artifacts through the public surface."""
    doc = (EXT_DIR / "EXIT_CONTRACT.md").read_text(encoding="utf-8")
    lowered = doc.lower()
    assert "superspec" in lowered
    assert "vibe3 handoff" in doc
    # FR-018: the contract must call out idempotency when both paths observe
    # the same artifact.
    assert "idempotent" in lowered or "idempot" in lowered


def test_external_superspec_source_untouched() -> None:
    """FR-014: the bridge lives ONLY under vibe-spec-bridge/ — no file is
    added into the external superspec/ source tree. superspec itself is
    gitignored and may be absent (CI); the guarantee checked here is that
    NOTHING under vibe-spec-bridge/ leaks into the superspec namespace."""
    for root, _dirs, files in os.walk(EXT_DIR):
        for f in files:
            rel = Path(root).relative_to(EXT_DIR) / f
            assert "superspec" not in str(
                rel
            ), f"bridge file leaks into superspec namespace: {rel}"


# --- D. fixture hook behavior: record_* writes ref + idempotent (FR-018) ----


class _StubGit:
    """Minimal git client stand-in (mirrors test_handoff_service.py)."""

    def __init__(self, worktree_root: Path, git_common: Path, branch: str) -> None:
        self._worktree_root = worktree_root
        self._git_common = git_common
        self._branch = branch

    def get_current_branch(self) -> str:
        return self._branch

    def get_git_common_dir(self) -> str:
        return str(self._git_common)

    def get_worktree_root(self) -> str:
        return str(self._worktree_root)

    def find_worktree_path_for_branch(self, branch: str) -> Path | None:
        return self._worktree_root if branch == self._branch else None


@pytest.fixture
def bridge_env(tmp_path: Path) -> tuple[SQLiteClient, HandoffService, Path]:
    """Temp flow + fixture spec-kit workflow with all four artifacts present.

    Simulates the disk state after a full spec-kit run (specify → plan →
    implement → review) so each publish adapter has a resolvable artifact.
    """
    worktree_root = tmp_path / "wt"
    git_common = tmp_path / ".git"
    worktree_root.mkdir()
    git_common.mkdir()

    spec_dir = worktree_root / ".specify" / "specs" / "012-fixture"
    spec_dir.mkdir(parents=True)
    (spec_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")
    (spec_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    reports = worktree_root / "docs" / "reports"
    reports.mkdir(parents=True)
    (reports / "012-fixture-report.md").write_text("# Report\n", encoding="utf-8")
    (reports / "012-fixture-audit.md").write_text("# Audit\n", encoding="utf-8")

    store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))
    service = HandoffService(
        store=store,
        git_client=_StubGit(worktree_root, git_common, "task/issue-3312"),
    )
    return store, service, worktree_root


def test_after_specify_publishes_spec_ref(
    bridge_env: tuple[SQLiteClient, HandoffService, Path],
) -> None:
    """Scenario 1: after_specify -> ``handoff spec`` records spec_ref."""
    store, service, _ = bridge_env
    service.record_spec(
        ".specify/specs/012-fixture/spec.md", actor="speckit/after_specify"
    )
    state = store.get_flow_state("task/issue-3312")
    assert state is not None
    assert state["spec_ref"] == ".specify/specs/012-fixture/spec.md"


def test_after_plan_publishes_plan_ref(
    bridge_env: tuple[SQLiteClient, HandoffService, Path],
) -> None:
    """Scenario 2: after_plan -> ``handoff plan`` records plan_ref."""
    store, service, _ = bridge_env
    service.record_plan(
        ".specify/specs/012-fixture/plan.md", actor="speckit/after_plan"
    )
    state = store.get_flow_state("task/issue-3312")
    assert state is not None
    assert state["plan_ref"] == ".specify/specs/012-fixture/plan.md"


def test_after_implement_publishes_report_ref(
    bridge_env: tuple[SQLiteClient, HandoffService, Path],
) -> None:
    """Scenario 3: implementation completion -> ``handoff report`` records
    report_ref."""
    store, service, _ = bridge_env
    service.record_report(
        "docs/reports/012-fixture-report.md", actor="speckit/after_implement"
    )
    state = store.get_flow_state("task/issue-3312")
    assert state is not None
    assert state["report_ref"] == "docs/reports/012-fixture-report.md"


def test_after_review_publishes_audit_ref(
    bridge_env: tuple[SQLiteClient, HandoffService, Path],
) -> None:
    """Scenario 4: review completion -> ``handoff audit`` records audit_ref."""
    store, service, _ = bridge_env
    service.record_audit(
        "docs/reports/012-fixture-audit.md", actor="speckit/after_review"
    )
    state = store.get_flow_state("task/issue-3312")
    assert state is not None
    assert state["audit_ref"] == "docs/reports/012-fixture-audit.md"


def test_same_artifact_idempotent_across_hook_and_exit_paths(
    bridge_env: tuple[SQLiteClient, HandoffService, Path],
) -> None:
    """FR-018: when the hook path and the direct-superspec exit path observe
    the SAME artifact, re-recording is safe — the ref value is stable and no
    duplicate-spec corruption occurs. (Event-level dedup is the writer's
    contract, covered by ``test_record_spec_idempotent_rerecord``.)"""
    store, service, _ = bridge_env
    canonical = ".specify/specs/012-fixture/spec.md"

    # Hook path publishes first, then the exit path re-publishes the same ref.
    service.record_spec(canonical, actor="speckit/after_specify")
    service.record_spec(canonical, actor="superspec/exit-contract")

    state = store.get_flow_state("task/issue-3312")
    assert state is not None
    assert state["spec_ref"] == canonical
