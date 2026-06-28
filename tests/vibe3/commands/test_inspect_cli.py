"""Public contract for the evidence-only inspect command group."""


def test_inspect_no_args_shows_help(cli_runner, inspect_app_fixture) -> None:
    result = cli_runner.invoke(inspect_app_fixture, [])

    assert result.exit_code in (0, 2)
    assert "Usage" in result.output or "inspect" in result.output.lower()


def test_inspect_help_only_lists_evidence_commands(
    cli_runner, inspect_app_fixture
) -> None:
    result = cli_runner.invoke(inspect_app_fixture, ["--help"])

    assert result.exit_code == 0
    for command in ("base", "files", "symbols"):
        assert command in result.output
    for removed in ("uncommit", "dead-code"):
        assert removed not in result.output
    assert "commands [" not in result.output
