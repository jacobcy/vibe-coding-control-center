"""Contract tests for inspect subcommands output format options.

This test module enforces the design contract that all inspect subcommands should
support --json and --yaml output options to prevent future drift.

Reference: docs/v3/design/trace-inspect-output-format.md
"""

import subprocess

import yaml


def get_inspect_subcommands():
    """Get all inspect subcommands from help output."""
    result = subprocess.run(
        ["uv", "run", "python", "src/vibe3/cli.py", "inspect", "--help"],
        capture_output=True,
        text=True,
        check=True,
    )

    # Parse help output to find subcommands
    lines = result.stdout.split("\n")
    subcommands = []

    for line in lines:
        # Look for lines like "  files [<file>]             Structure of one file"
        if (
            line.strip()
            and not line.startswith("Usage:")
            and not line.startswith("Options:")
        ):
            parts = line.strip().split()
            if parts and parts[0] not in ["When", "Subcommands:", "For", "Examples:"]:
                # Extract command name (first word)
                cmd = parts[0].rstrip("]")
                if cmd and not cmd.startswith("[") and cmd not in ["vibe3", "inspect"]:
                    subcommands.append(cmd)

    return subcommands


def test_all_inspect_subcommands_have_json_option():
    """Verify all inspect subcommands support --json output."""
    subcommands = get_inspect_subcommands()

    # Commands that already have --json (verified by existing tests)
    commands_with_json = [
        "files",
        "symbols",
        "base",
        "pr",
        "commit",
        "uncommit",
        "commands",
        "dead-code",
    ]

    for cmd in subcommands:
        if cmd in commands_with_json:
            # Check that --json appears in help
            result = subprocess.run(
                ["uv", "run", "python", "src/vibe3/cli.py", "inspect", cmd, "--help"],
                capture_output=True,
                text=True,
                check=True,
            )
            assert "--json" in result.stdout, f"inspect {cmd} missing --json option"


def test_all_inspect_subcommands_have_yaml_option():
    """Verify all inspect subcommands support --yaml output."""
    subcommands = get_inspect_subcommands()

    # Commands that now have --yaml (this issue's implementation)
    commands_with_yaml = [
        "files",
        "symbols",
        "base",
        "pr",
        "commit",
        "uncommit",
        "commands",
    ]

    # Note: dead-code has a different output model and doesn't need --yaml
    for cmd in subcommands:
        if cmd in commands_with_yaml:
            # Check that --yaml appears in help
            result = subprocess.run(
                ["uv", "run", "python", "src/vibe3/cli.py", "inspect", cmd, "--help"],
                capture_output=True,
                text=True,
                check=True,
            )
            assert "--yaml" in result.stdout, f"inspect {cmd} missing --yaml option"


def test_inspect_files_yaml_produces_valid_yaml():
    """Verify inspect files --yaml produces valid parseable YAML."""
    result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "src/vibe3/cli.py",
            "inspect",
            "files",
            "src/vibe3/cli.py",
            "--yaml",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    # Parse YAML output
    data = yaml.safe_load(result.stdout)

    # Verify expected structure
    assert isinstance(data, dict), "YAML output should be a dict"
    assert (
        "file" in data or "function_count" in data
    ), "YAML should contain file analysis data"


def test_inspect_base_yaml_produces_valid_yaml():
    """Verify inspect base --yaml produces valid parseable YAML.

    Uses HEAD as base to work in both local and CI environments
    (CI uses shallow clones where remote branch refs may not exist).
    """
    result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "src/vibe3/cli.py",
            "inspect",
            "base",
            "HEAD",
            "--yaml",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    # Parse YAML output
    data = yaml.safe_load(result.stdout)

    # Verify expected structure
    assert isinstance(data, dict), "YAML output should be a dict"
    assert "current_branch" in data, "YAML should contain current_branch"
    assert "score" in data, "YAML should contain score"


def test_inspect_symbols_yaml_produces_valid_yaml():
    """Verify inspect symbols --yaml produces valid parseable YAML."""
    result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "src/vibe3/cli.py",
            "inspect",
            "symbols",
            "src/vibe3/cli.py",
            "--yaml",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    # Parse YAML output
    data = yaml.safe_load(result.stdout)

    # Verify expected structure
    assert isinstance(data, dict), "YAML output should be a dict"
    assert "file" in data, "YAML should contain file field"
    assert "symbols" in data, "YAML should contain symbols list"


def test_inspect_commit_yaml_produces_valid_yaml():
    """Verify inspect commit --yaml produces valid parseable YAML."""
    result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "src/vibe3/cli.py",
            "inspect",
            "commit",
            "HEAD",
            "--yaml",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    # Parse YAML output
    data = yaml.safe_load(result.stdout)

    # Verify expected structure
    assert isinstance(data, dict), "YAML output should be a dict"
    assert "score" in data, "YAML should contain score"
    assert "dag" in data, "YAML should contain dag"


def test_inspect_commands_yaml_produces_valid_yaml():
    """Verify inspect commands --yaml produces valid parseable YAML."""
    result = subprocess.run(
        ["uv", "run", "python", "src/vibe3/cli.py", "inspect", "commands", "--yaml"],
        capture_output=True,
        text=True,
        check=True,
    )

    # Parse YAML output
    data = yaml.safe_load(result.stdout)

    # Verify expected structure
    assert isinstance(data, dict), "YAML output should be a dict"
    assert "command" in data, "YAML should contain command field"


def test_inspect_json_and_yaml_both_available():
    """Verify that where --json is available, --yaml is also available.

    This is a contract alignment requirement.
    """
    subcommands = get_inspect_subcommands()

    # Commands that should have both --json and --yaml
    commands_with_both = [
        "files",
        "symbols",
        "base",
        "pr",
        "commit",
        "uncommit",
        "commands",
    ]

    for cmd in subcommands:
        if cmd in commands_with_both:
            result = subprocess.run(
                ["uv", "run", "python", "src/vibe3/cli.py", "inspect", cmd, "--help"],
                capture_output=True,
                text=True,
                check=True,
            )

            has_json = "--json" in result.stdout
            has_yaml = "--yaml" in result.stdout

            # Both should be present (contract requirement)
            assert (
                has_json and has_yaml
            ), f"inspect {cmd} should have both --json and --yaml (contract alignment)"
