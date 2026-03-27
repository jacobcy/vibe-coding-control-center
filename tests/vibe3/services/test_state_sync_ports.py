"""Tests for state sync ports."""

from vibe3.services.state_sync_ports import GhIssueLabelPort


def test_gh_issue_label_port_appends_repo(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd, *_, **__) -> object:
        calls.append(cmd)

        class Result:
            def __init__(self, stdout: str = "", returncode: int = 0) -> None:
                self.stdout = stdout
                self.returncode = returncode
                self.stderr = ""

        if "view" in cmd:
            return Result(stdout='{"labels": []}')
        return Result()

    monkeypatch.setattr("vibe3.services.state_sync_ports.subprocess.run", fake_run)

    port = GhIssueLabelPort(repo="owner/repo")

    assert port.get_issue_labels(12) == []
    assert port.add_issue_label(12, "state/ready") is True
    assert port.remove_issue_label(12, "state/ready") is True

    assert calls[0] == [
        "gh",
        "issue",
        "view",
        "12",
        "--json",
        "labels",
        "--repo",
        "owner/repo",
    ]
    assert calls[1] == [
        "gh",
        "issue",
        "edit",
        "12",
        "--add-label",
        "state/ready",
        "--repo",
        "owner/repo",
    ]
    assert calls[2] == [
        "gh",
        "issue",
        "edit",
        "12",
        "--remove-label",
        "state/ready",
        "--repo",
        "owner/repo",
    ]
