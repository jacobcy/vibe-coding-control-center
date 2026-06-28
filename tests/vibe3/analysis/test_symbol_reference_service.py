"""Provider-neutral symbol evidence contract tests."""

from __future__ import annotations

from pathlib import Path

from vibe3.analysis.symbol_reference_service import (
    ProviderSymbol,
    SerenaSymbolReferenceProvider,
    inspect_symbol,
)


class FakeProvider:
    name = "fake"
    version = "1.0"

    def __init__(
        self,
        *,
        definition: ProviderSymbol | None,
        references: list[ProviderSymbol] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.definition = definition
        self.references = references or []
        self.error = error

    def find_definition(self, file: str, symbol: str) -> ProviderSymbol | None:
        if self.error is not None:
            raise self.error
        return self.definition

    def find_references(self, file: str, identity: str) -> list[ProviderSymbol]:
        if self.error is not None:
            raise self.error
        return self.references


def _source(tmp_path: Path) -> Path:
    source = tmp_path / "sample.py"
    source.write_text("def target():\n    pass\ntarget()\n", encoding="utf-8")
    return source


def _record(
    path: Path,
    start: int,
    end: int,
    *,
    identity: str = "target",
    context: str = "",
) -> ProviderSymbol:
    return ProviderSymbol(
        path=path.name,
        identity=identity,
        start_line=start,
        end_line=end,
        context=context,
    )


def test_ready_result_contains_only_valid_one_based_ranges(tmp_path: Path) -> None:
    source = _source(tmp_path)
    provider = FakeProvider(
        definition=_record(source, 0, 1),
        references=[_record(source, 2, 2, context="target()")],
    )

    result = inspect_symbol(
        source,
        "target",
        provider=provider,
        repo_root=tmp_path,
    )

    assert result.status == "ready"
    assert result.definition is not None
    assert result.definition.range.start_line == 1
    assert result.definition.range.end_line == 2
    assert result.references[0].range.start_line == 3
    assert result.references[0].context == "target()"
    assert result.observation is not None
    assert result.observation.observed_reference_count == 1
    assert result.observation.complete is False
    assert result.provenance.provider == "fake"


def test_invalid_reference_range_becomes_partial_unknown(tmp_path: Path) -> None:
    source = _source(tmp_path)
    provider = FakeProvider(
        definition=_record(source, 0, 1),
        references=[
            _record(source, 2, 2),
            _record(source, -1, -1),
        ],
    )

    result = inspect_symbol(
        source,
        "target",
        provider=provider,
        repo_root=tmp_path,
    )

    assert result.status == "partial"
    assert len(result.references) == 1
    assert result.unknowns[0].code == "invalid_provider_range"


def test_zero_observed_references_does_not_claim_completeness(tmp_path: Path) -> None:
    source = _source(tmp_path)
    provider = FakeProvider(definition=_record(source, 0, 1))

    result = inspect_symbol(
        source,
        "target",
        provider=provider,
        repo_root=tmp_path,
    )

    assert result.status == "ready"
    assert result.references == []
    assert result.observation is not None
    assert result.observation.observed_reference_count == 0
    assert result.observation.complete is False


def test_missing_definition_is_not_found(tmp_path: Path) -> None:
    source = _source(tmp_path)

    result = inspect_symbol(
        source,
        "missing",
        provider=FakeProvider(definition=None),
        repo_root=tmp_path,
    )

    assert result.status == "not_found"
    assert result.definition is None
    assert result.references == []


def test_provider_timeout_is_disabled_not_zero_references(tmp_path: Path) -> None:
    source = _source(tmp_path)

    result = inspect_symbol(
        source,
        "target",
        provider=FakeProvider(definition=None, error=TimeoutError("slow")),
        repo_root=tmp_path,
    )

    assert result.status == "disabled"
    assert result.observation is None
    assert result.unknowns[0].code == "provider_unavailable"


def test_serena_adapter_uses_reference_marker_not_container_range() -> None:
    class FakeSerenaClient:
        def find_symbol(self, name_path: str, relative_file: str):  # noqa: ANN202
            return [
                {
                    "name_path": "register",
                    "relative_path": relative_file,
                    "body_location": {"start_line": 17, "end_line": 83},
                }
            ]

        def find_references(self, name_path: str, relative_file: str):  # noqa: ANN202
            return {
                "src/vibe3/commands/inspect.py": {
                    "File": [
                        {
                            "name_path": "inspect",
                            "body_location": {"start_line": 0, "end_line": 347},
                            "content_around_reference": (
                                "...  14:from x import y\n"
                                "  >  15:from inspect_base import register\n"
                                "...  16:next_line"
                            ),
                        }
                    ]
                }
            }

    provider = SerenaSymbolReferenceProvider(client=FakeSerenaClient())  # type: ignore[arg-type]

    definition = provider.find_definition(
        "src/vibe3/commands/inspect_base.py", "register"
    )
    references = provider.find_references(
        "src/vibe3/commands/inspect_base.py", "register"
    )

    assert definition is not None
    assert definition.start_line == 17
    assert definition.end_line == 83
    assert references[0].path == "src/vibe3/commands/inspect.py"
    assert references[0].start_line == 14
    assert references[0].end_line == 14
    assert "register" in references[0].context
