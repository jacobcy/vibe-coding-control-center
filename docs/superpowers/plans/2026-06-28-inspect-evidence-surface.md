# Inspect Evidence Surface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild `inspect base`, contract `inspect files` and `inspect symbols`, and remove inspect promises that cannot be supported by direct evidence.

**Architecture:** A versioned `ReviewObservation` model combines exact Git facts with a repository-owned Review Kernel classifier. Separate single-purpose AST and symbol-provider adapters serve `files` and `symbols`; command renderers consume models and never perform analysis. Unsupported impact inference remains explicitly disabled.

**Tech Stack:** Python 3.12, Pydantic v2, Typer, PyYAML, Git CLI through `GitClient`, Serena 1.1.1 provider adapter, pytest.

## Global Constraints

- Git merge-base and Git diff are the only change-set truth.
- Architecture Kernel remains exactly `runtime + orchestra` from `runtime/taxonomy.py`.
- Review Kernel entries are exact files; directory patterns and substring matching are forbidden.
- `kernel_impact` is `none`, `small`, or `large`; it is not runtime impact prediction.
- No risk score, impacted-module expansion, dead-code verdict, call tree, snapshot baseline, automatic merge blocking, or DAG-based test selection may remain in the inspect path.
- `inspect files` reads exactly one Python file.
- `inspect symbols` only emits references with validated 1-based inclusive ranges; zero observations never mean unused.
- JSON/YAML/human renderers consume the same result models.
- Use `uv run` for Python tooling and targeted tests locally.
- Follow the repository two-step commit rule; never use `--no-verify`.

---

### Task 1: Versioned observation models and Review Kernel manifest

**Files:**
- Create: `src/vibe3/models/inspect_evidence.py`
- Create: `src/vibe3/analysis/review_kernel.py`
- Create: `config/v3/review_kernel.yaml`
- Modify: `src/vibe3/models/__init__.py`
- Modify: `src/vibe3/analysis/__init__.py`
- Modify: `tests/vibe3/test_modularity/test_core_budget.py`
- Create: `tests/vibe3/analysis/test_review_kernel.py`
- Create: `tests/vibe3/test_modularity/test_review_kernel_manifest.py`

**Interfaces:**
- Produces: `SourceRange`, `Diagnostic`, `ChangedFileFact`, `KernelHit`, `KernelObservation`, `ReviewPolicy`, `ImpactAnalysisStatus`, `ReviewObservation`.
- Produces: `load_review_kernel(path: Path) -> ReviewKernelManifest`.
- Produces: `classify_review_kernel(paths: dict[str, set[str]], manifest: ReviewKernelManifest) -> tuple[KernelObservation, ReviewPolicy]`.

- [ ] **Step 1: Write failing model and manifest tests**

```python
def test_architecture_hit_is_large_and_repeated(tmp_path: Path) -> None:
    manifest = write_manifest(
        tmp_path,
        path="src/vibe3/runtime/heartbeat.py",
        responsibilities=["heartbeat_timer", "event_ingestion"],
        review_floor="repeated",
    )
    kernel, review = classify_review_kernel(
        {"src/vibe3/runtime/heartbeat.py": {"committed"}}, manifest
    )
    assert kernel.impact == "large"
    assert kernel.architecture_hits[0].sources == ["committed"]
    assert review.minimum_depth == "repeated"


def test_manifest_rejects_directory_entry(tmp_path: Path) -> None:
    path = tmp_path / "review_kernel.yaml"
    path.write_text(
        "entries:\n- path: src/vibe3/services/\n"
        "  responsibilities: [flow]\n  reason: too broad\n"
        "  review_floor: focused\n",
        encoding="utf-8",
    )
    with pytest.raises(ReviewKernelConfigError, match="exact file"):
        load_review_kernel(path)
```

- [ ] **Step 2: Verify RED**

Run: `rtk proxy uv run pytest tests/vibe3/analysis/test_review_kernel.py tests/vibe3/test_modularity/test_review_kernel_manifest.py -q`

Expected: collection fails because `vibe3.analysis.review_kernel` and evidence models do not exist.

- [ ] **Step 3: Implement models, loader, classifier, and exact initial manifest**

```python
class KernelImpact(StrEnum):
    NONE = "none"
    SMALL = "small"
    LARGE = "large"


class ReviewDepth(StrEnum):
    NORMAL = "normal"
    FOCUSED = "focused"
    REPEATED = "repeated"


class ReviewKernelEntry(BaseModel):
    path: str
    responsibilities: list[str] = Field(min_length=1)
    reason: str = Field(min_length=1)
    review_floor: ReviewDepth


def is_architecture_path(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return len(parts) >= 3 and parts[:2] == ("src", "vibe3") and parts[2] in {
        name for name, category in MODULE_CATEGORY_MAP.items()
        if category == ModuleCategory.KERNEL
    }
```

Move the current `CORE_RESPONSIBILITIES` file ownership into `review_kernel.yaml`, deduplicating `runtime.heartbeat` into a single entry with two responsibilities. Add the 13 exact non-architecture files listed in the approved spec.

- [ ] **Step 4: Verify GREEN and modularity coverage**

Run: `rtk proxy uv run pytest tests/vibe3/analysis/test_review_kernel.py tests/vibe3/test_modularity/test_review_kernel_manifest.py tests/vibe3/test_modularity/test_core_budget.py tests/vibe3/test_modularity/test_taxonomy.py -q`

Expected: all tests pass; every non-`__init__.py` file in runtime/orchestra has exactly one manifest entry.

- [ ] **Step 5: Commit with the required two-step gate**

```bash
rtk git add config/v3/review_kernel.yaml src/vibe3/models/inspect_evidence.py src/vibe3/models/__init__.py src/vibe3/analysis/review_kernel.py src/vibe3/analysis/__init__.py tests/vibe3/analysis/test_review_kernel.py tests/vibe3/test_modularity/test_review_kernel_manifest.py tests/vibe3/test_modularity/test_core_budget.py
rtk git commit -m "temp: validate review kernel evidence model"
rtk proxy git reset --mixed HEAD^
rtk git add config/v3/review_kernel.yaml src/vibe3/models/inspect_evidence.py src/vibe3/models/__init__.py src/vibe3/analysis/review_kernel.py src/vibe3/analysis/__init__.py tests/vibe3/analysis/test_review_kernel.py tests/vibe3/test_modularity/test_review_kernel_manifest.py tests/vibe3/test_modularity/test_core_budget.py
rtk git commit -m "feat(inspect): define review kernel evidence model"
```

### Task 2: Exact Git observation adapter and `inspect base`

**Files:**
- Modify: `src/vibe3/clients/git_client.py`
- Create: `src/vibe3/analysis/review_observation.py`
- Rewrite: `src/vibe3/commands/inspect_base.py`
- Rewrite: `src/vibe3/commands/inspect_base_helpers.py`
- Rewrite: `tests/vibe3/commands/test_inspect_base.py`
- Rewrite: `tests/vibe3/commands/test_inspect_base_helpers.py`
- Create: `tests/vibe3/analysis/test_review_observation.py`

**Interfaces:**
- Produces on `GitClient`: `resolve_revision(ref: str) -> str`, `get_diff_metadata(base: str, head: str, *, cached: bool = False) -> tuple[str, str]`.
- Consumes: `classify_review_kernel` and evidence models from Task 1.
- Produces: `build_review_observation(requested_base: str | None, *, git: GitClient, manifest_path: Path) -> ReviewObservation`.

- [ ] **Step 1: Write failing Git fixture tests**

```python
def test_observation_splits_committed_staged_unstaged_and_untracked(
    git_repo: Path,
) -> None:
    # Fixture creates one file in each partition and a file modified in both
    # staged and unstaged partitions.
    result = build_review_observation(
        "main",
        git=GitClient(cwd=git_repo),
        manifest_path=git_repo / "config/v3/review_kernel.yaml",
    )
    assert [f.path for f in result.changes.committed] == ["committed.py"]
    assert [f.path for f in result.changes.staged] == ["both.py", "staged.py"]
    assert [f.path for f in result.changes.unstaged] == ["both.py", "unstaged.py"]
    assert [f.path for f in result.changes.untracked] == ["untracked.py"]
    assert result.comparison.merge_base_sha == git(
        git_repo, "merge-base", "main", "HEAD"
    )
```

Add cases for rename, delete, binary numstat, missing base, missing manifest, and a new unregistered file under `src/vibe3/runtime/`.

- [ ] **Step 2: Verify RED**

Run: `rtk proxy uv run pytest tests/vibe3/analysis/test_review_observation.py -q`

Expected: tests fail because `build_review_observation` and new Git methods do not exist.

- [ ] **Step 3: Add narrow Git read methods and parsers**

```python
def get_diff_metadata(
    self, base: str, head: str, *, cached: bool = False
) -> tuple[str, str]:
    prefix = ["diff", "--cached"] if cached else ["diff"]
    revision_args = [] if cached else [base, head]
    name_status = self._run([*prefix, "--find-renames", "--name-status", *revision_args])
    numstat = self._run([*prefix, "--find-renames", "--numstat", *revision_args])
    return name_status, numstat
```

Use `merge_base..HEAD` for committed, `HEAD` with `cached=True` for staged, and an empty revision pair for unstaged. Parse name-status and numstat by path, preserving rename old/new paths and `-` as binary `None` values. Untracked facts have `status=A` and null numstat.

- [ ] **Step 4: Build observation and rewire CLI renderers**

```python
observation = build_review_observation(
    resolved_base,
    git=GitClient(),
    manifest_path=Path("config/v3/review_kernel.yaml"),
)
if json_out:
    typer.echo(observation.model_dump_json(indent=2))
elif yaml_out:
    typer.echo(yaml.safe_dump(observation.model_dump(mode="json"), sort_keys=False))
else:
    render_review_observation(observation)
```

Remove Serena, DAG, changed-symbol and score calls from both base modules. Preserve the shared base resolver and explicit base validation.

- [ ] **Step 5: Verify GREEN and real CLI parity**

Run: `rtk proxy uv run pytest tests/vibe3/analysis/test_review_observation.py tests/vibe3/commands/test_inspect_base.py tests/vibe3/commands/test_inspect_base_helpers.py -q`

Run: `rtk proxy uv run python src/vibe3/cli.py inspect base origin/main --json > /tmp/inspect-base.json`

Run: `rtk proxy uv run python -c 'import json; d=json.load(open("/tmp/inspect-base.json")); assert d["schema_version"] == 1; assert d["impact_analysis"]["status"] == "disabled"'`

Expected: targeted tests pass and real JSON is valid without `score` or `impacted_modules`.

- [ ] **Step 6: Commit with the required two-step gate**

```bash
rtk git add src/vibe3/clients/git_client.py src/vibe3/analysis/review_observation.py src/vibe3/commands/inspect_base.py src/vibe3/commands/inspect_base_helpers.py tests/vibe3/analysis/test_review_observation.py tests/vibe3/commands/test_inspect_base.py tests/vibe3/commands/test_inspect_base_helpers.py
rtk git commit -m "temp: validate exact inspect base observation"
rtk proxy git reset --mixed HEAD^
rtk git add src/vibe3/clients/git_client.py src/vibe3/analysis/review_observation.py src/vibe3/commands/inspect_base.py src/vibe3/commands/inspect_base_helpers.py tests/vibe3/analysis/test_review_observation.py tests/vibe3/commands/test_inspect_base.py tests/vibe3/commands/test_inspect_base_helpers.py
rtk git commit -m "feat(inspect): rebuild base on exact git evidence"
```

### Task 3: Contract `inspect files` to one Python AST surface

**Files:**
- Create: `src/vibe3/analysis/python_file_inspector.py`
- Modify: `src/vibe3/commands/inspect.py`
- Rewrite: `tests/vibe3/commands/test_inspect_files.py`
- Create: `tests/vibe3/analysis/test_python_file_inspector.py`

**Interfaces:**
- Produces: `inspect_python_file(path: Path, *, repo_root: Path) -> FileInspectionResult`.
- Consumes: `SourceRange` and `Diagnostic` from Task 1.

- [ ] **Step 1: Write failing AST contract tests**

```python
def test_inspects_nested_declarations_and_direct_imports(tmp_path: Path) -> None:
    source = tmp_path / "sample.py"
    source.write_text(
        "import os as operating_system\n"
        "from .ports import Port as P\n\n"
        "class Worker:\n"
        "    async def run(self):\n"
        "        def nested():\n"
        "            return 1\n",
        encoding="utf-8",
    )
    result = inspect_python_file(source, repo_root=tmp_path)
    assert [d.qualified_name for d in result.declarations] == [
        "Worker", "Worker.run", "Worker.run.nested"
    ]
    assert result.imports[1].module == "ports"
    assert result.imports[1].level == 1
```

Add syntax-error, directory, non-Python, missing-file and content-SHA cases.

- [ ] **Step 2: Verify RED**

Run: `rtk proxy uv run pytest tests/vibe3/analysis/test_python_file_inspector.py -q`

Expected: import failure for `python_file_inspector`.

- [ ] **Step 3: Implement minimal AST visitor and result model**

```python
def inspect_python_file(path: Path, *, repo_root: Path) -> FileInspectionResult:
    raw = path.read_bytes()
    source = raw.decode("utf-8")
    tree = ast.parse(source, filename=str(path))
    visitor = DeclarationAndImportVisitor()
    visitor.visit(tree)
    return FileInspectionResult(
        schema_version=1,
        status="ready",
        file=InspectedFile(
            path=path.resolve().relative_to(repo_root.resolve()).as_posix(),
            language="python",
            content_sha256=hashlib.sha256(raw).hexdigest(),
        ),
        metrics=FileMetrics(total_lines=len(source.splitlines())),
        declarations=visitor.declarations,
        imports=visitor.imports,
    )
```

The visitor maintains a declaration-name stack to create qualified names and distinguishes methods, async methods, and nested functions.

- [ ] **Step 4: Replace `files` command behavior**

Require a path, reject directories and unsupported extensions, delete full-repo collection, shell regex and all DAG/imported-by calls. Render the single model for JSON/YAML/human formats.

- [ ] **Step 5: Verify GREEN and real CLI**

Run: `rtk proxy uv run pytest tests/vibe3/analysis/test_python_file_inspector.py tests/vibe3/commands/test_inspect_files.py -q`

Run: `rtk proxy uv run python src/vibe3/cli.py inspect files src/vibe3/commands/inspect_base.py --json`

Expected: output contains `content_sha256`, declarations and direct imports; it does not contain `imported_by`.

- [ ] **Step 6: Commit with the required two-step gate**

```bash
rtk git add src/vibe3/analysis/python_file_inspector.py src/vibe3/commands/inspect.py tests/vibe3/analysis/test_python_file_inspector.py tests/vibe3/commands/test_inspect_files.py
rtk git commit -m "temp: validate inspect files AST contract"
rtk proxy git reset --mixed HEAD^
rtk git add src/vibe3/analysis/python_file_inspector.py src/vibe3/commands/inspect.py tests/vibe3/analysis/test_python_file_inspector.py tests/vibe3/commands/test_inspect_files.py
rtk git commit -m "feat(inspect): contract files to python syntax evidence"
```

### Task 4: Contract `inspect symbols` and gate Serena 1.1.1

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `src/vibe3/clients/serena_client.py`
- Create: `src/vibe3/analysis/symbol_reference_service.py`
- Rewrite: `src/vibe3/commands/inspect_symbols.py`
- Rewrite: `tests/vibe3/commands/test_inspect_symbols.py`
- Create: `tests/vibe3/analysis/test_symbol_reference_service.py`
- Modify: `tests/vibe3/analysis/test_serena_service.py`

**Interfaces:**
- Produces protocol: `SymbolReferenceProvider.find_definition(file: str, symbol: str) -> object` and `find_references(file: str, identity: str) -> list[object]`.
- Produces: `inspect_symbol(file: Path, symbol: str, provider: SymbolReferenceProvider) -> SymbolInspectionResult`.

- [ ] **Step 1: Write failing provider-normalization tests**

```python
def test_invalid_reference_range_becomes_partial(tmp_path: Path) -> None:
    source = write_source(tmp_path, "def target():\n    pass\ntarget()\n")
    provider = FakeProvider(
        definition=record(source, 0, 1, identity="target"),
        references=[record(source, 2, 2), record(source, 0, 0)],
    )
    result = inspect_symbol(source, "target", provider=provider)
    assert result.status == "partial"
    assert result.references[0].range.start_line == 3
    assert result.observation.observed_reference_count == 1
    assert result.observation.complete is False
    assert result.unknowns[0].code == "invalid_provider_range"
```

Provider records are normalized from 0-based provider coordinates to 1-based public coordinates before validation. Add ready, zero-reference, not-found, timeout and unavailable cases.

- [ ] **Step 2: Verify RED**

Run: `rtk proxy uv run pytest tests/vibe3/analysis/test_symbol_reference_service.py -q`

Expected: import failure for `symbol_reference_service`.

- [ ] **Step 3: Upgrade and adapt Serena**

Change the dependency to `serena-agent>=1.1.1,<1.2` and run `rtk proxy uv lock`. Add a strict `find_definition` wrapper using `find_symbol`, then query `find_referencing_symbols` with the returned name path and relative path. Return plain dictionaries containing only path, name path, body range and context.

```python
definition = provider.find_definition(relative_file, symbol)
if definition is None:
    return SymbolInspectionResult.not_found(query, provenance)
references = provider.find_references(relative_file, definition.identity)
return normalize_symbol_evidence(query, definition, references, provenance)
```

- [ ] **Step 4: Rewrite CLI to explicit file:symbol mode**

Delete file-only listing and CLI/dead-code inference. Invalid input produces an error result. Provider creation failure produces `status=disabled` with `provider_unavailable`.

- [ ] **Step 5: Verify unit contracts and real provider gate**

Run: `rtk proxy uv run pytest tests/vibe3/analysis/test_symbol_reference_service.py tests/vibe3/commands/test_inspect_symbols.py tests/vibe3/analysis/test_serena_service.py -q`

Run: `rtk proxy uv run python src/vibe3/cli.py inspect symbols src/vibe3/commands/inspect_base.py:register --json`

Expected: either `ready/partial` with every returned range positive and in-bounds, or honest `disabled`; line `0` is forbidden.

- [ ] **Step 6: Commit with the required two-step gate**

```bash
rtk git add pyproject.toml uv.lock src/vibe3/clients/serena_client.py src/vibe3/analysis/symbol_reference_service.py src/vibe3/commands/inspect_symbols.py tests/vibe3/analysis/test_symbol_reference_service.py tests/vibe3/commands/test_inspect_symbols.py tests/vibe3/analysis/test_serena_service.py
rtk git commit -m "temp: validate symbol evidence provider contract"
rtk proxy git reset --mixed HEAD^
rtk git add pyproject.toml uv.lock src/vibe3/clients/serena_client.py src/vibe3/analysis/symbol_reference_service.py src/vibe3/commands/inspect_symbols.py tests/vibe3/analysis/test_symbol_reference_service.py tests/vibe3/commands/test_inspect_symbols.py tests/vibe3/analysis/test_serena_service.py
rtk git commit -m "feat(inspect): expose validated symbol reference evidence"
```

### Task 5: Delete invalid commands, inference engines, and downstream consumers

**Files:**
- Delete: `src/vibe3/commands/inspect_change.py`
- Delete: `src/vibe3/analysis/command_analyzer.py`
- Delete: `src/vibe3/analysis/command_analyzer_helpers.py`
- Delete: `src/vibe3/analysis/dead_code_rules.py`
- Delete if no remaining consumer: `src/vibe3/analysis/dag_service.py`
- Delete: `tests/vibe3/commands/test_inspect_uncommit.py`
- Delete: `tests/vibe3/analysis/test_command_analyzer.py`
- Delete: `tests/vibe3/analysis/test_dead_code_rules.py`
- Delete if service is removed: `tests/vibe3/analysis/test_dag_service.py`
- Modify: `src/vibe3/commands/inspect.py`
- Modify: `src/vibe3/analysis/__init__.py`
- Modify: `src/vibe3/models/inspection.py`
- Modify: `src/vibe3/analysis/pre_push_test_selector.py`
- Modify: `src/vibe3/commands/pr_quality_gates.py`
- Modify: `src/vibe3/commands/pr_query.py`
- Modify: `src/vibe3/services/pr/create.py`
- Modify: `src/vibe3/roles/review.py`
- Modify: relevant targeted tests under `tests/vibe3/commands`, `tests/vibe3/analysis`, and `tests/vibe3/services`.

**Interfaces:**
- Consumes: `ReviewObservationService` from Task 2 for local branch consumers.
- Removes: `build_change_analysis`, `build_pr_analysis` impact/risk use, `ImpactGraph`, call-tree and dead-code public exports where no independent consumer remains.

- [ ] **Step 1: Write failing surface and consumer tests**

```python
def test_inspect_help_only_lists_evidence_commands() -> None:
    result = runner.invoke(cli_app, ["inspect", "--help"])
    assert result.exit_code == 0
    assert "base" in result.output
    assert "files" in result.output
    assert "symbols" in result.output
    for removed in ("uncommit", "dead-code", "commands"):
        assert removed not in result.output


def test_pr_show_payload_has_no_unreliable_analysis_fields() -> None:
    payload = build_payload_with_observation()
    rendered = json.dumps(payload)
    assert "risk_score" not in rendered
    assert "impacted_modules" not in rendered
```

Add a pre-push selector test proving it uses direct mapping/fallback without calling `_find_tests_via_dag`.

- [ ] **Step 2: Verify RED**

Run: `rtk proxy uv run pytest tests/vibe3/commands/test_inspect_cli.py tests/vibe3/commands/test_pr_show_local_review.py tests/vibe3/analysis/test_pre_push_test_selector.py -q`

Expected: removed commands and old risk/DAG consumers are still present.

- [ ] **Step 3: Remove registrations and implementations**

Remove `register_change`, `commands`, `dead_code`, associated help text and suggestion chains. Remove `_find_tests_via_dag`; direct file mapping and smoke fallback remain.

Before deleting `dag_service.py`, run:

`rtk rg -n "dag_service|expand_impacted_modules|ImpactGraph" src/vibe3 --glob '*.py'`

If only import extraction remains, move `_extract_imports` into `python_file_inspector.py` or delete the caller. No impact-expansion function remains.

- [ ] **Step 4: Remove or rewire downstream consumers**

- Delete `run_risk_gate`; it has no valid gate semantics.
- `pr show` omits analysis when exact local refs are unavailable; it never falls back to old score/DAG data.
- `pr create` local branch context uses `ReviewObservation` summary.
- Review request gets stable changed-file/Kernel evidence; snapshot-specific fields remain under #3215 until that issue lands, but no inspect DAG/risk field is populated.
- Delete compatibility re-exports only after `rg` proves no remaining consumer.

- [ ] **Step 5: Verify GREEN and absence**

Run: `rtk proxy uv run pytest tests/vibe3/commands/test_inspect_cli.py tests/vibe3/commands/test_pr_show_local_review.py tests/vibe3/analysis/test_pre_push_test_selector.py tests/vibe3/commands/test_pr_create_ai.py -q`

Run: `rtk rg -n "impacted_modules|expand_impacted_modules|scan_dead_code|analyze_command|inspect uncommit|inspect dead-code|inspect commands" src/vibe3`

Expected: tests pass; any remaining search hit is an explicitly unrelated historical/model term, not an inspect product consumer.

- [ ] **Step 6: Commit with the required two-step gate**

```bash
rtk git add -A src/vibe3 tests/vibe3
rtk git commit -m "temp: validate inspect inference retirement"
rtk proxy git reset --mixed HEAD^
rtk git add -A src/vibe3 tests/vibe3
rtk git commit -m "refactor(inspect): retire unsupported analysis promises"
```

### Task 6: Documentation, contract audit, and initial release verification

**Files:**
- Modify: `docs/v3/architecture/analysis-semantics.md`
- Modify: `docs/v3/infrastructure/07-command-standards.md`
- Modify: `docs/v3/README.md`
- Modify: `docs/v3/ROADMAP.md`
- Modify: `skills/vibe-instruction/SKILL.md`
- Modify: `skills/vibe-review-code/SKILL.md`
- Modify: `supervisor/policies/common.md`
- Modify: `supervisor/policies/review.md`
- Modify: `supervisor/policies/plan.md`
- Modify: `supervisor/manager.md`
- Modify: `docs/superpowers/specs/2026-06-28-inspect-evidence-surface-design.md` status to implemented only after verification.

**Interfaces:**
- Documents exactly `base/files/symbols` and schema version 1.
- Records the initial verification evidence without claiming runtime impact coverage.

- [ ] **Step 1: Remove stale command and promise references**

Run searches first:

```bash
rtk rg -n "inspect (pr|commit|uncommit|dead-code|commands)|risk score|impacted modules" docs skills .agent supervisor
```

Update active docs/skills/policies. Do not rewrite archived historical documents unless they are presented as current instructions.

- [ ] **Step 2: Run the complete targeted verification set**

```bash
rtk proxy uv run pytest \
  tests/vibe3/analysis/test_review_kernel.py \
  tests/vibe3/test_modularity/test_review_kernel_manifest.py \
  tests/vibe3/analysis/test_review_observation.py \
  tests/vibe3/analysis/test_python_file_inspector.py \
  tests/vibe3/analysis/test_symbol_reference_service.py \
  tests/vibe3/commands/test_inspect_base.py \
  tests/vibe3/commands/test_inspect_files.py \
  tests/vibe3/commands/test_inspect_symbols.py \
  tests/vibe3/commands/test_inspect_cli.py \
  tests/vibe3/analysis/test_pre_push_test_selector.py -q
rtk proxy uv run ruff check src/vibe3/models/inspect_evidence.py src/vibe3/analysis/review_kernel.py src/vibe3/analysis/review_observation.py src/vibe3/analysis/python_file_inspector.py src/vibe3/analysis/symbol_reference_service.py src/vibe3/clients/git_client.py src/vibe3/clients/serena_client.py src/vibe3/commands/inspect.py src/vibe3/commands/inspect_base.py src/vibe3/commands/inspect_base_helpers.py src/vibe3/commands/inspect_symbols.py src/vibe3/analysis/pre_push_test_selector.py src/vibe3/commands/pr_quality_gates.py src/vibe3/commands/pr_query.py src/vibe3/services/pr/create.py src/vibe3/roles/review.py
rtk proxy uv run mypy src/vibe3/models/inspect_evidence.py src/vibe3/analysis/review_kernel.py src/vibe3/analysis/review_observation.py src/vibe3/analysis/python_file_inspector.py src/vibe3/analysis/symbol_reference_service.py
```

Expected: all targeted tests, Ruff and mypy pass.

- [ ] **Step 3: Run real CLI acceptance checks**

```bash
rtk proxy uv run python src/vibe3/cli.py inspect --help
rtk proxy uv run python src/vibe3/cli.py inspect base origin/main --json
rtk proxy uv run python src/vibe3/cli.py inspect files src/vibe3/commands/inspect_base.py --json
rtk proxy uv run python src/vibe3/cli.py inspect symbols src/vibe3/commands/inspect_base.py:register --json
```

Expected: help lists only three commands; base and files are ready with schema 1; symbols is ready/partial with valid ranges or explicitly disabled.

- [ ] **Step 4: Audit requirements and complexity reduction**

```bash
rtk proxy git diff --check origin/main...HEAD
rtk proxy git diff --stat origin/main...HEAD
rtk rg -n "impacted_modules|expand_impacted_modules|scan_dead_code|analyze_command" src/vibe3
```

Compare every acceptance criterion in the approved spec with test or CLI evidence. Keep the work incomplete if any criterion lacks evidence.

- [ ] **Step 5: Commit documentation with the required two-step gate**

```bash
rtk git add docs/v3/architecture/analysis-semantics.md docs/v3/infrastructure/07-command-standards.md docs/v3/README.md docs/v3/ROADMAP.md skills/vibe-instruction/SKILL.md skills/vibe-review-code/SKILL.md supervisor/policies/common.md supervisor/policies/review.md supervisor/policies/plan.md supervisor/manager.md docs/superpowers/specs/2026-06-28-inspect-evidence-surface-design.md
rtk git commit -m "temp: validate inspect evidence documentation"
rtk proxy git reset --mixed HEAD^
rtk git add docs/v3/architecture/analysis-semantics.md docs/v3/infrastructure/07-command-standards.md docs/v3/README.md docs/v3/ROADMAP.md skills/vibe-instruction/SKILL.md skills/vibe-review-code/SKILL.md supervisor/policies/common.md supervisor/policies/review.md supervisor/policies/plan.md supervisor/manager.md docs/superpowers/specs/2026-06-28-inspect-evidence-surface-design.md
rtk git commit -m "docs(inspect): document evidence-only command surface"
```
