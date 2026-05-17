"""Tests for command option types."""

from typing import get_args

from vibe3.commands.command_options import SourceOption


def test_source_option_literal_values():
    """SourceOption accepts expected literal values."""
    # Extract Literal values from the Annotated type
    literal_args = get_args(SourceOption)
    # First arg is the Literal type
    literal_type = literal_args[0]
    # Get the Literal values
    values = get_args(literal_type)

    assert "local" in values
    assert "remote" in values
    assert "auto" in values
    assert len(values) == 3


def test_source_option_is_annotated():
    """SourceOption is properly annotated for Typer CLI use."""
    from typing import Annotated, Literal, get_args, get_origin

    # Should be Annotated[Literal["local", "remote", "auto"], ...]
    assert get_origin(SourceOption) is Annotated

    # Check the wrapped type is Literal
    args = get_args(SourceOption)
    assert len(args) >= 1
    assert get_origin(args[0]) is Literal


def test_source_option_default_value():
    """SourceOption can be used with 'auto' as default."""
    # This tests that we can assign the string literal
    # In actual commands, it will be used as:
    # source: SourceOption = "auto"
    source_value: SourceOption = "auto"
    assert source_value == "auto"
