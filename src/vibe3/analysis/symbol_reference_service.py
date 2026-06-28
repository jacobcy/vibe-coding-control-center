"""Validated positive symbol evidence for ``inspect symbols``."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

from vibe3.models import Diagnostic, SourceRange

_REFERENCE_MARKER = re.compile(r"^\s*>\s*(\d+):\s?(.*)$", re.MULTILINE)


@dataclass(frozen=True)
class ProviderSymbol:
    """Provider-neutral zero-based symbol location."""

    path: str
    identity: str
    start_line: int
    end_line: int
    context: str = ""


class SymbolReferenceProvider(Protocol):
    """Minimal provider contract required by the public inspect surface."""

    name: str
    version: str

    def find_definition(self, file: str, symbol: str) -> ProviderSymbol | None: ...

    def find_references(self, file: str, identity: str) -> list[ProviderSymbol]: ...


class SerenaClientProtocol(Protocol):
    """Narrow Serena client boundary used by the evidence adapter."""

    def find_symbol(self, name_path: str, relative_file: str) -> Any: ...

    def find_references(self, name_path: str, relative_file: str) -> Any: ...


class SerenaSymbolReferenceProvider:
    """Translate Serena output into validated, provider-neutral records."""

    name = "serena"

    def __init__(self, client: SerenaClientProtocol) -> None:
        self.client = client
        try:
            self.version = version("serena-agent")
        except PackageNotFoundError:
            self.version = "unavailable"

    def find_definition(self, file: str, symbol: str) -> ProviderSymbol | None:
        payload = self.client.find_symbol(symbol, file)
        candidates = [
            record
            for record in _walk_dicts(payload)
            if _is_symbol_record(record)
            and _matches_symbol(str(record.get("name_path", "")), symbol)
        ]
        if not candidates:
            return None
        if len(candidates) != 1:
            raise ValueError(
                f"Serena returned {len(candidates)} matching definitions; "
                "use a more specific symbol path"
            )
        record = candidates[0]
        location = record["body_location"]
        return ProviderSymbol(
            path=str(record.get("relative_path") or file),
            identity=str(record["name_path"]),
            start_line=int(location["start_line"]),
            end_line=int(location["end_line"]),
        )

    def find_references(self, file: str, identity: str) -> list[ProviderSymbol]:
        payload = self.client.find_references(identity, file)
        references: list[ProviderSymbol] = []
        for path_hint, record in _walk_reference_records(payload):
            context = record.get("content_around_reference")
            if not isinstance(context, str):
                continue
            marker = _REFERENCE_MARKER.search(context)
            zero_based_line = int(marker.group(1)) - 1 if marker else -1
            references.append(
                ProviderSymbol(
                    path=str(record.get("relative_path") or path_hint or ""),
                    identity=str(record.get("name_path") or identity),
                    start_line=zero_based_line,
                    end_line=zero_based_line,
                    context=context,
                )
            )
        return references


def _walk_dicts(payload: Any) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        records.append(payload)
        for value in payload.values():
            records.extend(_walk_dicts(value))
    elif isinstance(payload, list):
        for value in payload:
            records.extend(_walk_dicts(value))
    return records


def _walk_reference_records(
    payload: Any,
    path_hint: str | None = None,
) -> list[tuple[str | None, dict[str, Any]]]:
    records: list[tuple[str | None, dict[str, Any]]] = []
    if isinstance(payload, dict):
        if isinstance(payload.get("content_around_reference"), str):
            records.append((path_hint, payload))
        for key, value in payload.items():
            child_hint = (
                key if isinstance(key, str) and key.endswith(".py") else path_hint
            )
            records.extend(_walk_reference_records(value, child_hint))
    elif isinstance(payload, list):
        for value in payload:
            records.extend(_walk_reference_records(value, path_hint))
    return records


def _is_symbol_record(record: dict[str, Any]) -> bool:
    location = record.get("body_location")
    return (
        isinstance(record.get("name_path"), str)
        and isinstance(location, dict)
        and isinstance(location.get("start_line"), int)
        and isinstance(location.get("end_line"), int)
    )


def _matches_symbol(identity: str, requested: str) -> bool:
    return identity == requested or identity.endswith(f"/{requested}")


class SymbolQuery(BaseModel):
    file: str
    symbol: str
    content_sha256: str


class SymbolEvidence(BaseModel):
    path: str
    range: SourceRange
    context: str = ""


class SymbolObservation(BaseModel):
    observed_reference_count: int = Field(ge=0)
    complete: Literal[False] = False
    scope: Literal["static_provider"] = "static_provider"


class ProviderProvenance(BaseModel):
    provider: str
    version: str


class SymbolInspectionResult(BaseModel):
    schema_version: Literal[1] = 1
    status: Literal["ready", "partial", "not_found", "disabled", "error"]
    query: SymbolQuery | None = None
    definition: SymbolEvidence | None = None
    references: list[SymbolEvidence] = Field(default_factory=list)
    observation: SymbolObservation | None = None
    provenance: ProviderProvenance
    unknowns: list[Diagnostic] = Field(default_factory=list)


def _normalize_record(
    record: ProviderSymbol,
    *,
    repo_root: Path,
) -> SymbolEvidence | None:
    target = repo_root / record.path
    if not target.is_file():
        return None
    try:
        line_count = len(target.read_text(encoding="utf-8").splitlines())
    except (OSError, UnicodeDecodeError):
        return None
    if (
        record.start_line < 0
        or record.end_line < record.start_line
        or record.end_line >= line_count
    ):
        return None
    return SymbolEvidence(
        path=record.path,
        range=SourceRange(
            start_line=record.start_line + 1,
            end_line=record.end_line + 1,
        ),
        context=record.context,
    )


def inspect_symbol(
    path: Path,
    symbol: str,
    *,
    provider: SymbolReferenceProvider,
    repo_root: Path,
) -> SymbolInspectionResult:
    """Return validated positive evidence without completeness claims."""
    provenance = ProviderProvenance(provider=provider.name, version=provider.version)
    if not path.is_file():
        return SymbolInspectionResult(
            status="error",
            provenance=provenance,
            unknowns=[Diagnostic(code="file_not_found", message="File does not exist")],
        )
    try:
        relative_path = path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return SymbolInspectionResult(
            status="error",
            provenance=provenance,
            unknowns=[
                Diagnostic(
                    code="outside_repository",
                    message="File must be inside the current worktree",
                    path=path.as_posix(),
                )
            ],
        )
    raw = path.read_bytes()
    query = SymbolQuery(
        file=relative_path,
        symbol=symbol,
        content_sha256=hashlib.sha256(raw).hexdigest(),
    )

    try:
        definition_record = provider.find_definition(relative_path, symbol)
        if definition_record is None:
            return SymbolInspectionResult(
                status="not_found",
                query=query,
                provenance=provenance,
            )
        definition = _normalize_record(definition_record, repo_root=repo_root)
        if definition is None:
            return SymbolInspectionResult(
                status="disabled",
                query=query,
                provenance=provenance,
                unknowns=[
                    Diagnostic(
                        code="invalid_definition_range",
                        message="Provider definition is not valid source evidence",
                    )
                ],
            )
        reference_records = provider.find_references(
            relative_path, definition_record.identity
        )
    except Exception as exc:  # provider boundary intentionally catches all failures
        return SymbolInspectionResult(
            status="disabled",
            query=query,
            provenance=provenance,
            unknowns=[Diagnostic(code="provider_unavailable", message=str(exc))],
        )

    references: list[SymbolEvidence] = []
    unknowns: list[Diagnostic] = []
    for record in reference_records:
        normalized = _normalize_record(record, repo_root=repo_root)
        if normalized is None:
            unknowns.append(
                Diagnostic(
                    code="invalid_provider_range",
                    message="Provider reference is not valid source evidence",
                    path=record.path,
                )
            )
        else:
            references.append(normalized)
    return SymbolInspectionResult(
        status="partial" if unknowns else "ready",
        query=query,
        definition=definition,
        references=references,
        observation=SymbolObservation(observed_reference_count=len(references)),
        provenance=provenance,
        unknowns=unknowns,
    )
