"""Tests for flow_manage CLI status filter option (Issue #3189)."""

import typing

from vibe3.commands.flow_manage import StatusFilterOption


def test_status_filter_option_accepts_terminal_statuses() -> None:
    """--status must accept review/failed/aborted (PR-backed terminal states)."""
    # StatusFilterOption = Annotated[Literal[...] | None, typer.Option(...)]
    annotated_args = typing.get_args(StatusFilterOption)
    union = annotated_args[0]  # Literal[...] | None
    literal, _none = typing.get_args(union)
    values = set(typing.get_args(literal))

    assert {"review", "failed", "aborted"} <= values
    assert {"active", "blocked", "done", "stale"} <= values
