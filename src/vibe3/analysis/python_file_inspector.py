"""Single-file Python syntax evidence for ``inspect files``."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from vibe3.models.inspect_evidence import Diagnostic, SourceRange


class InspectedFile(BaseModel):
    """Identity of the exact file content that was parsed."""

    path: str
    language: Literal["python"] = "python"
    content_sha256: str


class FileMetrics(BaseModel):
    """Direct metrics derived from the current file content."""

    total_lines: int = Field(ge=0)


class DeclarationEvidence(BaseModel):
    """One AST declaration with its qualified lexical name."""

    kind: Literal[
        "class",
        "function",
        "async_function",
        "method",
        "async_method",
        "nested_function",
    ]
    name: str
    qualified_name: str
    range: SourceRange


class ImportEvidence(BaseModel):
    """One direct Python import syntax node."""

    kind: Literal["import", "from"]
    module: str
    names: list[str] = Field(default_factory=list)
    aliases: dict[str, str] = Field(default_factory=dict)
    level: int = Field(default=0, ge=0)
    range: SourceRange


class FileInspectionResult(BaseModel):
    """Versioned result for one explicit Python file."""

    schema_version: Literal[1] = 1
    status: Literal["ready", "error", "unsupported"]
    file: InspectedFile | None = None
    metrics: FileMetrics | None = None
    declarations: list[DeclarationEvidence] = Field(default_factory=list)
    imports: list[ImportEvidence] = Field(default_factory=list)
    diagnostics: list[Diagnostic] = Field(default_factory=list)


class _EvidenceVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.declarations: list[DeclarationEvidence] = []
        self.imports: list[ImportEvidence] = []
        self._scope: list[tuple[str, str]] = []

    def _qualified_name(self, name: str) -> str:
        return ".".join([*(scope_name for scope_name, _ in self._scope), name])

    @staticmethod
    def _range(node: ast.AST) -> SourceRange:
        start = getattr(node, "lineno")
        end = getattr(node, "end_lineno", start) or start
        return SourceRange(start_line=start, end_line=end)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.declarations.append(
            DeclarationEvidence(
                kind="class",
                name=node.name,
                qualified_name=self._qualified_name(node.name),
                range=self._range(node),
            )
        )
        self._scope.append((node.name, "class"))
        self.generic_visit(node)
        self._scope.pop()

    def _function_kind(self, *, asynchronous: bool) -> str:
        if self._scope and self._scope[-1][1] == "class":
            return "async_method" if asynchronous else "method"
        if any(kind == "function" for _, kind in self._scope):
            return "nested_function"
        return "async_function" if asynchronous else "function"

    def _visit_function(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, *, asynchronous: bool
    ) -> None:
        self.declarations.append(
            DeclarationEvidence(
                kind=self._function_kind(asynchronous=asynchronous),  # type: ignore[arg-type]
                name=node.name,
                qualified_name=self._qualified_name(node.name),
                range=self._range(node),
            )
        )
        self._scope.append((node.name, "function"))
        self.generic_visit(node)
        self._scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node, asynchronous=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node, asynchronous=True)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            aliases = {alias.name: alias.asname} if alias.asname else {}
            self.imports.append(
                ImportEvidence(
                    kind="import",
                    module=alias.name,
                    aliases=aliases,
                    range=self._range(node),
                )
            )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        names = [alias.name for alias in node.names]
        aliases = {alias.name: alias.asname for alias in node.names if alias.asname}
        self.imports.append(
            ImportEvidence(
                kind="from",
                module=node.module or "",
                names=names,
                aliases=aliases,
                level=node.level,
                range=self._range(node),
            )
        )


def _relative_path(path: Path, repo_root: Path) -> str:
    return path.resolve().relative_to(repo_root.resolve()).as_posix()


def inspect_python_file(path: Path, *, repo_root: Path) -> FileInspectionResult:
    """Inspect exactly one Python file without dependency inference."""
    if not path.exists():
        return FileInspectionResult(
            status="error",
            diagnostics=[
                Diagnostic(code="file_not_found", message="File does not exist")
            ],
        )
    if path.is_dir():
        return FileInspectionResult(
            status="unsupported",
            diagnostics=[
                Diagnostic(
                    code="directory_not_supported",
                    message="inspect files requires a single Python file",
                )
            ],
        )
    if path.suffix != ".py":
        return FileInspectionResult(
            status="unsupported",
            diagnostics=[
                Diagnostic(
                    code="unsupported_file_type",
                    message="Only Python files are supported",
                    path=path.as_posix(),
                )
            ],
        )

    try:
        relative_path = _relative_path(path, repo_root)
    except ValueError:
        return FileInspectionResult(
            status="error",
            diagnostics=[
                Diagnostic(
                    code="outside_repository",
                    message="File must be inside the current worktree",
                    path=path.as_posix(),
                )
            ],
        )

    raw = path.read_bytes()
    try:
        source = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return FileInspectionResult(
            status="error",
            diagnostics=[
                Diagnostic(
                    code="decode_error",
                    message=str(exc),
                    path=relative_path,
                )
            ],
        )

    try:
        tree = ast.parse(source, filename=relative_path)
    except SyntaxError as exc:
        line = max(exc.lineno or 1, 1)
        return FileInspectionResult(
            status="error",
            diagnostics=[
                Diagnostic(
                    code="syntax_error",
                    message=exc.msg,
                    path=relative_path,
                    range=SourceRange(start_line=line, end_line=line),
                )
            ],
        )

    visitor = _EvidenceVisitor()
    visitor.visit(tree)
    return FileInspectionResult(
        status="ready",
        file=InspectedFile(
            path=relative_path,
            content_sha256=hashlib.sha256(raw).hexdigest(),
        ),
        metrics=FileMetrics(total_lines=len(source.splitlines())),
        declarations=visitor.declarations,
        imports=visitor.imports,
    )
