"""Tests for AgentCommandBuilder."""

from pathlib import Path

from vibe3.agents.command_builder import AgentCommandBuilder


def test_build_plan_command() -> None:
    """Test plan command construction."""
    cmd = AgentCommandBuilder.build_plan_command(42)

    # Check command structure
    assert cmd[0] == "uv"
    assert cmd[1] == "run"
    assert cmd[2] == "--project"
    assert cmd[4] == "python"
    assert cmd[5] == "-I"

    # Check CLI entry path is valid
    cli_entry = cmd[6]
    assert cli_entry.endswith("cli.py")
    assert Path(cli_entry).exists()

    # Check command arguments
    assert cmd[7] == "plan"
    assert cmd[8] == "--issue"
    assert cmd[9] == "42"
    assert cmd[10] == "--no-async"


def test_build_run_command() -> None:
    """Test run command construction."""
    plan_file = ".agent/plans/plan-42.md"
    cmd = AgentCommandBuilder.build_run_command(plan_file)

    # Check command structure
    assert cmd[0] == "uv"
    assert cmd[1] == "run"
    assert cmd[2] == "--project"
    assert cmd[4] == "python"
    assert cmd[5] == "-I"

    # Check CLI entry path is valid
    cli_entry = cmd[6]
    assert cli_entry.endswith("cli.py")

    # Check command arguments
    assert cmd[7] == "run"
    assert cmd[8] == "--plan"
    assert cmd[9] == plan_file


def test_build_review_command() -> None:
    """Test review command construction."""
    cmd = AgentCommandBuilder.build_review_command()

    # Check command structure
    assert cmd[0] == "uv"
    assert cmd[1] == "run"
    assert cmd[2] == "--project"
    assert cmd[4] == "python"
    assert cmd[5] == "-I"

    # Check CLI entry path is valid
    cli_entry = cmd[6]
    assert cli_entry.endswith("cli.py")

    # Check command arguments
    assert cmd[7] == "review"


def test_all_commands_use_same_project_root() -> None:
    """Test all commands use the same project root."""
    plan_cmd = AgentCommandBuilder.build_plan_command(42)
    run_cmd = AgentCommandBuilder.build_run_command("plan.md")
    review_cmd = AgentCommandBuilder.build_review_command()

    # Extract project roots
    plan_root = plan_cmd[3]
    run_root = run_cmd[3]
    review_root = review_cmd[3]

    # All should be the same
    assert plan_root == run_root == review_root
    assert Path(plan_root).exists()


def test_all_commands_use_same_cli_entry() -> None:
    """Test all commands use the same CLI entry."""
    plan_cmd = AgentCommandBuilder.build_plan_command(42)
    run_cmd = AgentCommandBuilder.build_run_command("plan.md")
    review_cmd = AgentCommandBuilder.build_review_command()

    # Extract CLI entries
    plan_entry = plan_cmd[6]
    run_entry = run_cmd[6]
    review_entry = review_cmd[6]

    # All should be the same
    assert plan_entry == run_entry == review_entry
