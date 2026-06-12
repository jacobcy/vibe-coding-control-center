from pathlib import Path

from vibe3.agents.models import (
    CodeagentCommand,
    CodeagentResult,
    create_codeagent_command,
)


def test_codeagent_command_instantiation():
    """Test CodeagentCommand can be instantiated with required fields."""

    def dummy_builder():
        return "context"

    cmd = CodeagentCommand(
        role="executor", context_builder=dummy_builder, task="test task"
    )

    assert cmd.role == "executor"
    assert cmd.context_builder() == "context"
    assert cmd.task == "test task"
    assert cmd.dry_run is False
    assert cmd.handoff_kind == "run"


def test_codeagent_result_instantiation():
    """Test CodeagentResult instantiation and defaults."""
    res = CodeagentResult(success=True, stdout="output")

    assert res.success is True
    assert res.stdout == "output"
    assert res.exit_code == 0
    assert res.stderr == ""
    assert res.handoff_file is None


def test_create_codeagent_command_factory_roles():
    """Test create_codeagent_command factory mapping for different roles."""

    def dummy_builder():
        return "context"

    # Test planner -> plan
    planner_cmd = create_codeagent_command(
        role="planner", context_builder=dummy_builder
    )
    assert planner_cmd.role == "planner"
    assert planner_cmd.handoff_kind == "plan"

    # Test executor -> run
    executor_cmd = create_codeagent_command(
        role="executor", context_builder=dummy_builder
    )
    assert executor_cmd.role == "executor"
    assert executor_cmd.handoff_kind == "run"

    # Test reviewer -> review
    reviewer_cmd = create_codeagent_command(
        role="reviewer", context_builder=dummy_builder
    )
    assert reviewer_cmd.role == "reviewer"
    assert reviewer_cmd.handoff_kind == "review"

    # Test manager -> indicate
    manager_cmd = create_codeagent_command(
        role="manager", context_builder=dummy_builder
    )
    assert manager_cmd.role == "manager"
    assert manager_cmd.handoff_kind == "indicate"


def test_create_codeagent_command_explicit_handoff_kind():
    """Test create_codeagent_command with explicit handoff_kind override."""

    def dummy_builder():
        return "context"

    cmd = create_codeagent_command(
        role="planner", context_builder=dummy_builder, handoff_kind="custom_kind"
    )
    assert cmd.role == "planner"
    assert cmd.handoff_kind == "custom_kind"


def test_create_codeagent_command_all_fields():
    """Test create_codeagent_command with all fields provided."""

    def dummy_builder():
        return "context"

    cwd = Path("/tmp")

    cmd = create_codeagent_command(
        role="executor",
        context_builder=dummy_builder,
        task="task",
        dry_run=True,
        handoff_kind="run",
        handoff_metadata={"key": "value"},
        agent="my-agent",
        backend="my-backend",
        model="my-model",
        cwd=cwd,
        config=None,
        branch="my-branch",
        issue_number=123,
        cli_args=["--arg"],
        resolved_options={"opt": 1},
        actor="my-actor",
        session_id="my-session",
        show_prompt=True,
        include_global_notice=False,
        fallback_prompt="fallback",
        fallback_include_global_notice=False,
        dry_run_summary={"sum": "mary"},
        tick_id=42,
    )

    assert cmd.role == "executor"
    assert cmd.task == "task"
    assert cmd.dry_run is True
    assert cmd.handoff_metadata == {"key": "value"}
    assert cmd.agent == "my-agent"
    assert cmd.backend == "my-backend"
    assert cmd.model == "my-model"
    assert cmd.cwd == cwd
    assert cmd.branch == "my-branch"
    assert cmd.issue_number == 123
    assert cmd.cli_args == ["--arg"]
    assert cmd.resolved_options == {"opt": 1}
    assert cmd.actor == "my-actor"
    assert cmd.session_id == "my-session"
    assert cmd.show_prompt is True
    assert cmd.include_global_notice is False
    assert cmd.fallback_prompt == "fallback"
    assert cmd.fallback_include_global_notice is False
    assert cmd.dry_run_summary == {"sum": "mary"}
    assert cmd.tick_id == 42
