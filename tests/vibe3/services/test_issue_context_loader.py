from unittest.mock import MagicMock

import pytest

from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.services.issue.context import load_issue_info


def test_load_issue_info_parses_github_payload() -> None:
    config = MagicMock(repo="owner/repo")
    github = MagicMock()
    github.view_issue.return_value = {
        "number": 436,
        "title": "Converge lifecycle",
        "state": "OPEN",
        "labels": [{"name": "state/claimed"}],
        "assignees": [],
        "comments": [],
    }

    issue = load_issue_info(436, config=config, github=github)

    assert issue == IssueInfo(
        number=436,
        title="Converge lifecycle",
        state=IssueState.CLAIMED,
        labels=["state/claimed"],
        assignees=[],
        milestone=None,
        github_state="OPEN",
    )


def test_load_issue_info_raises_user_error_on_network_failure() -> None:
    config = MagicMock(repo="owner/repo")
    github = MagicMock()
    github.view_issue.return_value = "network_error"

    with pytest.raises(Exception, match="无法读取 issue #436"):
        load_issue_info(436, config=config, github=github)
