"""Tests for Orchestra dispatcher."""

from pathlib import Path
from unittest.mock import patch

from vibe3.models.orchestration import IssueState
from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.dispatcher import Dispatcher, FlowOrchestrator
from vibe3.orchestra.models import IssueInfo, Trigger


def make_issue(number: int = 42, title: str = "Test issue") -> IssueInfo:
    return IssueInfo(
        number=number,
        title=title,
        state=IssueState.CLAIMED,
        labels=["state/claimed"],
    )


def make_trigger(
    issue: IssueInfo | None = None,
    from_state: IssueState | None = IssueState.READY,
    to_state: IssueState = IssueState.CLAIMED,
    command: str = "plan",
    args: list[str] | None = None,
) -> Trigger:
    return Trigger(
        issue=issue or make_issue(),
        from_state=from_state,
        to_state=to_state,
        command=command,
        args=args or ["task"],
    )


class TestDispatcherBuildCommand:
    """Tests for Dispatcher._build_command()."""

    def test_plan_command_includes_issue_number(self):
        config = OrchestraConfig()
        dispatcher = Dispatcher(config)
        issue = make_issue(number=123)
        trigger = make_trigger(
            issue=issue,
            from_state=IssueState.READY,
            to_state=IssueState.CLAIMED,
            command="plan",
            args=["task"],
        )

        with patch.object(
            dispatcher.orchestrator,
            "create_flow_for_issue",
            return_value={"branch": "task/issue-123"},
        ):
            cmd = dispatcher._build_command(trigger)

        assert cmd is not None
        assert "vibe3" in cmd
        assert "plan" in cmd
        assert "task" in cmd
        assert "123" in cmd

    def test_run_command_no_extra_args(self):
        config = OrchestraConfig()
        dispatcher = Dispatcher(config)
        issue = make_issue()
        trigger = make_trigger(
            issue=issue,
            from_state=IssueState.CLAIMED,
            to_state=IssueState.IN_PROGRESS,
            command="run",
            args=["execute"],
        )

        with patch.object(
            dispatcher.orchestrator, "switch_to_flow_branch", return_value="task/test"
        ):
            cmd = dispatcher._build_command(trigger)

        assert cmd is not None
        assert "vibe3" in cmd
        assert "run" in cmd
        assert "execute" in cmd

    def test_review_command_includes_pr_number(self):
        config = OrchestraConfig()
        dispatcher = Dispatcher(config)
        issue = make_issue()
        trigger = make_trigger(
            issue=issue,
            from_state=IssueState.IN_PROGRESS,
            to_state=IssueState.REVIEW,
            command="review",
            args=["pr"],
        )

        with patch.object(
            dispatcher.orchestrator, "get_pr_for_issue", return_value=456
        ):
            cmd = dispatcher._build_command(trigger)

        assert cmd is not None
        assert "vibe3" in cmd
        assert "review" in cmd
        assert "pr" in cmd
        assert "456" in cmd

    def test_review_command_returns_none_without_pr(self):
        config = OrchestraConfig()
        dispatcher = Dispatcher(config)
        issue = make_issue()
        trigger = make_trigger(
            issue=issue,
            from_state=IssueState.IN_PROGRESS,
            to_state=IssueState.REVIEW,
            command="review",
            args=["pr"],
        )

        with patch.object(
            dispatcher.orchestrator, "get_pr_for_issue", return_value=None
        ):
            cmd = dispatcher._build_command(trigger)

        assert cmd is None


class TestFlowOrchestrator:
    """Tests for FlowOrchestrator."""

    def test_get_flow_for_issue(self):
        config = OrchestraConfig()
        orchestrator = FlowOrchestrator(config)

        with patch.object(
            orchestrator.store,
            "get_flows_by_issue",
            return_value=[{"branch": "task/test", "pr_number": 123}],
        ):
            flow = orchestrator.get_flow_for_issue(42)

        assert flow is not None
        assert flow["branch"] == "task/test"

    def test_get_flow_for_issue_returns_none(self):
        config = OrchestraConfig()
        orchestrator = FlowOrchestrator(config)

        with patch.object(orchestrator.store, "get_flows_by_issue", return_value=[]):
            flow = orchestrator.get_flow_for_issue(42)

        assert flow is None

    def test_get_pr_for_issue_from_flow(self):
        config = OrchestraConfig()
        orchestrator = FlowOrchestrator(config)

        with patch.object(
            orchestrator,
            "get_flow_for_issue",
            return_value={"branch": "task/test", "pr_number": 789},
        ):
            pr_number = orchestrator.get_pr_for_issue(42)

        assert pr_number == 789

    def test_get_pr_for_issue_returns_none_without_flow(self):
        config = OrchestraConfig()
        orchestrator = FlowOrchestrator(config)

        with patch.object(orchestrator, "get_flow_for_issue", return_value=None):
            pr_number = orchestrator.get_pr_for_issue(42)

        assert pr_number is None


class TestDispatcherDryRun:
    """Tests for dry run mode."""

    def test_dry_run_does_not_execute(self):
        config = OrchestraConfig(dry_run=True)
        dispatcher = Dispatcher(config, dry_run=True)
        trigger = make_trigger()

        with patch.object(
            dispatcher.orchestrator,
            "create_flow_for_issue",
            return_value={"branch": "task/issue-42"},
        ):
            with patch("subprocess.run") as mock_run:
                result = dispatcher.dispatch(trigger)

        assert result is True
        mock_run.assert_not_called()


class _Completed:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class TestDispatcherReviewWorktreeResolution:
    def test_dispatch_pr_review_uses_resolved_worktree(self):
        config = OrchestraConfig()
        dispatcher = Dispatcher(config, repo_path=Path("/tmp/repo"))

        with patch.object(
            dispatcher, "_resolve_review_cwd", return_value=Path("/tmp/wt-feature")
        ):
            with patch(
                "subprocess.run",
                return_value=_Completed(returncode=0),
            ) as mock_run:
                result = dispatcher.dispatch_pr_review(42)

        assert result is True
        mock_run.assert_called_once()
        assert mock_run.call_args.kwargs["cwd"] == Path("/tmp/wt-feature")

    def test_find_worktree_for_branch_parses_porcelain_output(self):
        config = OrchestraConfig()
        dispatcher = Dispatcher(config, repo_path=Path("/tmp/repo"))
        output = (
            "worktree /tmp/repo\n"
            "HEAD abcdef0\n"
            "branch refs/heads/main\n"
            "\n"
            "worktree /tmp/wt-feature\n"
            "HEAD 1234567\n"
            "branch refs/heads/task/issue250-orchestra-manager\n"
            "\n"
        )

        with patch(
            "subprocess.run",
            return_value=_Completed(returncode=0, stdout=output),
        ):
            wt = dispatcher._find_worktree_for_branch("task/issue250-orchestra-manager")

        assert wt == Path("/tmp/wt-feature")

    def test_resolve_review_cwd_falls_back_to_repo_path(self):
        config = OrchestraConfig()
        dispatcher = Dispatcher(config, repo_path=Path("/tmp/repo"))

        class _PR:
            head_branch = "task/missing"

        with patch(
            "vibe3.clients.github_client.GitHubClient.get_pr",
            return_value=_PR(),
        ):
            with patch.object(
                dispatcher,
                "_find_worktree_for_branch",
                return_value=None,
            ):
                cwd = dispatcher._resolve_review_cwd(99)

        assert cwd == Path("/tmp/repo")
