"""Tests for GitHub label client ports."""

import subprocess

from vibe3.clients.github_client import GitHubClient
from vibe3.clients.github_labels import GhIssueLabelPort


def test_gh_issue_label_port_appends_repo(monkeypatch) -> None:
    """Write operations (add/remove) still shell out to `gh issue edit` directly."""
    calls: list[list[str]] = []

    def fake_run(cmd, *_, **__) -> object:
        calls.append(cmd)

        class Result:
            def __init__(self, stdout: str = "", returncode: int = 0) -> None:
                self.stdout = stdout
                self.returncode = returncode
                self.stderr = ""

        return Result()

    monkeypatch.setattr("vibe3.clients.github_labels.subprocess.run", fake_run)

    port = GhIssueLabelPort(repo="owner/repo")

    assert port.add_issue_label(12, "state/ready") is True
    assert port.remove_issue_label(12, "state/ready") is True

    assert calls[0] == [
        "gh",
        "issue",
        "edit",
        "12",
        "--add-label",
        "state/ready",
        "--repo",
        "owner/repo",
    ]
    assert calls[1] == [
        "gh",
        "issue",
        "edit",
        "12",
        "--remove-label",
        "state/ready",
        "--repo",
        "owner/repo",
    ]


def test_gh_issue_label_port_returns_false_on_timeout(monkeypatch) -> None:
    def fake_run(cmd, *_, **__) -> object:
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=30)

    monkeypatch.setattr("vibe3.clients.github_labels.subprocess.run", fake_run)

    port = GhIssueLabelPort(repo="owner/repo")

    assert port.add_issue_label(12, "state/ready") is False
    assert port.remove_issue_label(12, "state/ready") is False


def test_gh_issue_label_port_get_issue_labels_delegates_to_github_client(
    monkeypatch,
) -> None:
    """get_issue_labels reuses GitHubClient.view_issue instead of its own gh subprocess.

    Regression guard: this used to be a second, independent `gh issue view`
    implementation (raw subprocess) duplicating GitHubClient.view_issue.
    """
    calls: list[dict] = []

    def fake_view_issue(self, issue_number, repo=None, fields=None):
        calls.append({"issue_number": issue_number, "repo": repo, "fields": fields})
        return {"labels": [{"name": "state/ready"}, {"name": "type/feature"}]}

    monkeypatch.setattr(GitHubClient, "view_issue", fake_view_issue)

    port = GhIssueLabelPort(repo="owner/repo")

    assert port.get_issue_labels(12) == ["state/ready", "type/feature"]
    assert calls == [{"issue_number": 12, "repo": "owner/repo", "fields": ["labels"]}]


def test_gh_issue_label_port_get_issue_labels_returns_none_on_failure(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        GitHubClient, "view_issue", lambda self, *a, **kw: "network_error"
    )

    port = GhIssueLabelPort(repo="owner/repo")

    assert port.get_issue_labels(12) is None
