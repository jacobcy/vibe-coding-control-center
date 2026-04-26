import asyncio
from unittest.mock import MagicMock

from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueState
from vibe3.orchestra.services.state_label_dispatch import StateLabelDispatchService
from vibe3.roles.manager import MANAGER_ROLE


def test_manager_collects_ready_issue_without_live_session_gate() -> None:
    config = OrchestraConfig(manager_usernames=["manager-bot"])
    github = MagicMock()
    github.list_issues.return_value = [
        {
            "number": 340,
            "title": "Manager issue",
            "labels": [{"name": IssueState.READY.to_label()}],
            "assignees": [{"login": "manager-bot"}],
            "state": "open",
        }
    ]

    service = StateLabelDispatchService(
        config,
        github=github,
        role_def=MANAGER_ROLE,
    )
    service._flow_context = MagicMock(return_value=("", None))

    issues = asyncio.run(service.collect_ready_issues())
    assert [issue.number for issue in issues] == [340]
