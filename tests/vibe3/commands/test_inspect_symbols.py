"""CLI contract tests for validated symbol evidence."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.analysis.symbol_reference_service import (
    ProviderProvenance,
    SymbolInspectionResult,
    SymbolObservation,
    SymbolQuery,
)
from vibe3.commands.inspect import app

runner = CliRunner()


def _result(status: str = "ready") -> SymbolInspectionResult:
    return SymbolInspectionResult(
        status=status,  # type: ignore[arg-type]
        query=SymbolQuery(
            file="src/vibe3/commands/inspect_base.py",
            symbol="register",
            content_sha256="a" * 64,
        ),
        observation=(
            SymbolObservation(observed_reference_count=0) if status == "ready" else None
        ),
        provenance=ProviderProvenance(provider="serena", version="1.1.1"),
    )


def test_inspect_symbols_requires_file_and_symbol() -> None:
    result = runner.invoke(app, ["symbols", "src/vibe3/commands/inspect_base.py"])

    assert result.exit_code == 1
    assert "<file>:<symbol>" in result.output


def test_inspect_symbols_json_uses_evidence_schema() -> None:
    with (
        patch(
            "vibe3.commands.inspect_symbols.SerenaSymbolReferenceProvider",
            return_value=MagicMock(),
        ),
        patch(
            "vibe3.commands.inspect_symbols.inspect_symbol",
            return_value=_result(),
        ),
    ):
        result = runner.invoke(
            app,
            [
                "symbols",
                "src/vibe3/commands/inspect_base.py:register",
                "--json",
            ],
        )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["schema_version"] == 1
    assert payload["status"] == "ready"
    assert payload["observation"]["observed_reference_count"] == 0
    assert payload["observation"]["complete"] is False
    assert "reference_count" not in payload
    assert "unused" not in result.output


def test_inspect_symbols_disabled_returns_nonzero_and_valid_json() -> None:
    with (
        patch(
            "vibe3.commands.inspect_symbols.SerenaSymbolReferenceProvider",
            return_value=MagicMock(),
        ),
        patch(
            "vibe3.commands.inspect_symbols.inspect_symbol",
            return_value=_result(status="disabled"),
        ),
    ):
        result = runner.invoke(
            app,
            [
                "symbols",
                "src/vibe3/commands/inspect_base.py:register",
                "--json",
            ],
        )

    assert result.exit_code == 1
    assert json.loads(result.output)["status"] == "disabled"
