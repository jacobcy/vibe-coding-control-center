"""Contracts for post-merge Graphify artifact synchronization."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / ".github" / "workflows" / "graphify-sync.yml"


def _workflow() -> tuple[dict[str, object], str]:
    text = WORKFLOW.read_text(encoding="utf-8")
    parsed = yaml.load(text, Loader=yaml.BaseLoader)
    if not isinstance(parsed, dict):
        raise AssertionError("graphify-sync workflow must be a YAML mapping")
    return parsed, text


def test_graphify_sync_runs_after_non_graph_main_changes() -> None:
    workflow, _ = _workflow()
    triggers = workflow["on"]
    assert isinstance(triggers, dict)
    push = triggers["push"]
    assert isinstance(push, dict)
    assert push["branches"] == ["main"]
    assert push["paths-ignore"] == ["graphify-out/**"]
    assert "workflow_dispatch" in triggers


def test_graphify_sync_has_minimum_write_permissions() -> None:
    workflow, _ = _workflow()
    assert workflow["permissions"] == {"contents": "read"}


def test_graphify_sync_uses_pinned_tool_and_graph_only_delivery() -> None:
    _, text = _workflow()
    assert "uv tool install graphifyy==0.9.8" in text
    assert "graphify update ." in text
    assert "git diff --cached --quiet" in text
    assert 'SYNC_BRANCH="automation/graphify-sync"' in text
    assert "gh pr list" in text
    assert "--state open" in text
    assert 'if [[ -n "$PR_NUMBER" ]]' in text
    assert "git ls-remote --exit-code --heads" in text
    assert "--force-with-lease" in text
    assert "GRAPHIFY_SYNC_TOKEN is required" in text
    assert "secrets.GRAPHIFY_SYNC_TOKEN" in text
    assert "|| github.token" not in text
    assert "## Contributors" in text
    assert "github-actions[bot], graphify/0.9.8" in text
    for artifact in (
        "graphify-out/.graphify_labels.json",
        "graphify-out/GRAPH_REPORT.md",
        "graphify-out/graph.json",
        "graphify-out/manifest.json",
    ):
        assert artifact in text


def test_graphify_artifacts_are_generated_and_feature_branches_exclude_them() -> None:
    attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    claude = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")

    assert "graphify-out/** linguist-generated" in attributes
    assert "功能分支不提交 `graphify-out/`" in claude
    assert "Graphify Sync" in claude
