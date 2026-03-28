"""Additional flow-bind command semantics tests."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.commands.flow import app as flow_app

runner = CliRunner(env={"NO_COLOR": "1"})


def test_flow_bind_with_multiple_related_roles() -> None:
    with patch("vibe3.commands.flow.TaskService", create=True) as task_service_cls:
        task_service = MagicMock()
        task_service_cls.return_value = task_service
        task_service.link_issue.side_effect = [
            MagicMock(issue_number=219, issue_role="related", branch="task/demo"),
            MagicMock(issue_number=220, issue_role="related", branch="task/demo"),
        ]

        flow_service = MagicMock()
        flow_service.get_current_branch.return_value = "task/demo"
        with patch("vibe3.commands.flow.FlowService", return_value=flow_service):
            result = runner.invoke(
                flow_app, ["bind", "219", "220", "--role", "related"]
            )

    assert result.exit_code == 0
    assert task_service.link_issue.call_args_list[0].args == (
        "task/demo",
        219,
        "related",
    )
    assert task_service.link_issue.call_args_list[0].kwargs == {"actor": None}
    assert task_service.link_issue.call_args_list[1].args == (
        "task/demo",
        220,
        "related",
    )
    assert task_service.link_issue.call_args_list[1].kwargs == {"actor": None}
