"""#3327: vibe-explore extension — metadata + before_specify hook + contract.

Validates the project-owned explore-before-spec extension:
- extension.yml declares id + mandatory before_specify hook
- extensions.yml registers it for runtime discovery
- command uses spec-kit namespace + file exists
- before_specify is additive (owned solely by vibe-explore; no collision)
- explore.md states the no-handoff + graceful-degradation contract
- .gitignore tracks the extension (un-ignore + .specify-dev exception)

explore output is ephemeral evidence (not a handoff artifact) — there is no
writer/CLI to behavior-test, so coverage is metadata + contract-document,
mirroring the metadata half of ``test_spec_kit_bridge.py``.
"""

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
EXT_DIR = REPO_ROOT / ".specify" / "extensions" / "vibe-explore"
EXTENSIONS_CONFIG = REPO_ROOT / ".specify" / "extensions.yml"
ROOT_GITIGNORE = REPO_ROOT / ".gitignore"


def _load_extension_yml() -> dict:
    assert EXT_DIR.is_dir(), f"vibe-explore extension missing at {EXT_DIR}"
    return yaml.safe_load((EXT_DIR / "extension.yml").read_text(encoding="utf-8"))


def _load_extensions_config() -> dict:
    return yaml.safe_load(EXTENSIONS_CONFIG.read_text(encoding="utf-8"))


def _explore_command_text() -> str:
    return (EXT_DIR / "commands" / "explore.md").read_text(encoding="utf-8")


# --- A. extension.yml metadata ------------------------------------------------


def test_extension_yml_declares_explore_id() -> None:
    """The extension is a project-owned extension with a stable id."""
    meta = _load_extension_yml()
    assert meta["extension"]["id"] == "vibe-explore"


def test_extension_yml_declares_before_specify_hook() -> None:
    """explore wires to the before_specify lifecycle event."""
    meta = _load_extension_yml()
    assert "before_specify" in meta["hooks"]


def test_before_specify_hook_is_mandatory() -> None:
    """explore MUST auto-run before specify (optional: false) so context is
    always gathered — per the Explore Before Spec convention."""
    meta = _load_extension_yml()
    hook = meta["hooks"]["before_specify"]
    assert hook["optional"] is False
    assert hook["command"] == "speckit.vibe-explore.explore"


def test_extension_yml_command_uses_namespace_prefix() -> None:
    """spec-kit namespace rule: command prefixed ``speckit.<id>.*`` + file exists."""
    meta = _load_extension_yml()
    for cmd in meta["provides"]["commands"]:
        assert cmd["name"].startswith("speckit.vibe-explore."), cmd["name"]
        fname = cmd["name"].split(".", 2)[2] + ".md"
        assert (EXT_DIR / "commands" / fname).is_file(), fname


# --- B. runtime discovery (extensions.yml) ------------------------------------


def test_project_extension_is_declared_for_runtime_discovery() -> None:
    """Tracked config must let bootstrap materialize spec-kit's registry."""
    config = _load_extensions_config()
    assert "vibe-explore" in config["installed"]


def test_before_specify_hook_registered_in_extensions_yml() -> None:
    """The mandatory before_specify hook is registered in the tracked config."""
    config = _load_extensions_config()
    registered = {
        (hook_name, hook["extension"], hook["command"], hook["optional"])
        for hook_name, hooks in config["hooks"].items()
        for hook in hooks
    }
    assert (
        "before_specify",
        "vibe-explore",
        "speckit.vibe-explore.explore",
        False,
    ) in registered


# --- C. additive (no collision) -----------------------------------------------


def test_before_specify_hook_additive_no_collision() -> None:
    """before_specify is owned solely by vibe-explore; superspec and
    vibe-spec-bridge declare after_* / before_implement only, so adding
    before_specify cannot collide."""
    config = _load_extensions_config()
    owners = [
        hook["extension"]
        for hook_name, hooks in config["hooks"].items()
        for hook in hooks
        if hook_name == "before_specify"
    ]
    assert owners == ["vibe-explore"]


# --- D. contract document (explore.md) ----------------------------------------


def test_explore_command_states_no_handoff_invariant() -> None:
    """explore output is ephemeral evidence; MUST NOT write handoff / explore_ref."""
    text = _explore_command_text()
    assert "MUST NOT write to handoff" in text
    assert "explore_ref" in text
    assert "NOT a handoff artifact" in text


def test_explore_command_states_graceful_degradation() -> None:
    """Missing tools yield limitation notes, never a hook failure — specify
    must still proceed when graphify/claude-mem are absent."""
    text = _explore_command_text().lower()
    assert "gracefully" in text
    assert "limitation note" in text


# --- E. gitignore tracks the extension ----------------------------------------


def test_gitignore_tracks_extension_and_ignores_dev() -> None:
    """The extension ships in-tree (un-ignored) but its local .specify-dev/
    materialization stays ignored — same pattern as vibe-spec-bridge."""
    patterns = ROOT_GITIGNORE.read_text(encoding="utf-8").splitlines()
    assert "!.specify/extensions/vibe-explore/" in patterns
    assert ".specify/extensions/vibe-explore/.specify-dev/" in patterns
