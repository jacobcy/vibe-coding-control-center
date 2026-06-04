# Fix Instructions for Issue #1992

## MINOR Verdict: Three Issues to Fix

### Finding 1: Inaccurate xfail reason (cycle count)

**Severity**: MAJOR (part of MINOR verdict)
**Location**: tests/vibe3/test_modularity/test_dependency_direction.py:210-212
**Current State**:
```python
@pytest.mark.xfail(
    reason="Known architectural debt: 10 L3-internal circular deps remain in "
    "{domain, execution, orchestra, roles, runtime, services} SCC. "
    "Tracked by epic #1987."
)
```

**Problem**: The xfail reason states "10 L3-internal circular deps" but running the DFS algorithm finds **12** cycles within L3 core.

**Fix Required**: Update the reason string to reflect the accurate count:
```python
@pytest.mark.xfail(
    reason="Known architectural debt: 12 L3-internal circular deps remain in "
    "{domain, execution, orchestra, roles, runtime, services} SCC. "
    "Tracked by epic #1987."
)
```

**Verification**:
- Run the test and verify it still xfails correctly
- Count should match actual cycles found by DFS

### Finding 2: Stale reference to old test name

**Severity**: MINOR
**Location**: docs/standards/v3-module-architecture-standard.md:50
**Current State**:
```markdown
- **技术债**：SCC 内部的循环依赖（如 `domain ↔ runtime`、`orchestra ↔ services`）是已知技术债，由 `test_no_circular_deps` 追踪，待 epic #1987 Phase 1/2 通过 Protocol 注入与事件解耦消除（见 #1971/#1884/#1887/#1888）。
```

**Problem**: References old unified test name `test_no_circular_deps`, but the test has been split into:
- `test_no_circular_deps_outside_l3_core` (hard gate)
- `test_no_circular_deps_within_l3_core` (xfail)

**Fix Required**: Update to reference the correct test name:
```markdown
- **技术债**：SCC 内部的循环依赖（如 `domain ↔ runtime`、`orchestra ↔ services`）是已知技术债，由 `test_no_circular_deps_within_l3_core` 追踪，待 epic #1987 Phase 1/2 通过 Protocol 注入与事件解耦消除（见 #1971/#1884/#1887/#1888）。
```

**Verification**:
- Check that the document renders correctly
- Ensure test name matches actual implementation

### Finding 3: Duplicated DFS cycle-detection logic

**Severity**: MINOR
**Location**: tests/vibe3/test_modularity/test_dependency_direction.py:159-189 and :227-257
**Current State**: Both tests contain identical DFS cycle-detection code (~30 lines duplicated)

**Problem**: Code duplication reduces maintainability - if the cycle detection algorithm needs to change, both copies must be updated.

**Fix Required**: Extract the DFS logic into a helper method:

```python
def _detect_cycles_in_graph(
    self, import_graph: dict[str, list[str]]
) -> list[list[str]]:
    """Detect cycles in the import graph using DFS.

    Returns a list of cycles, where each cycle is represented as
    a list of module names forming a cycle.
    """
    graph = defaultdict(set)
    for module, imports in import_graph.items():
        for imp in imports:
            graph[module].add(imp)

    visited = set()
    rec_stack = set()
    cycles = []

    def dfs(node: str, path: list[str]) -> None:
        visited.add(node)
        rec_stack.add(node)
        path.append(node)

        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                dfs(neighbor, path)
            elif neighbor in rec_stack:
                # Found cycle
                cycle_start = path.index(neighbor)
                cycle = path[cycle_start:] + [neighbor]
                cycles.append(cycle)

        path.pop()
        rec_stack.remove(node)

    for module in graph:
        if module not in visited:
            dfs(module, [])

    return cycles
```

Then update both test methods to use the helper:
- `test_no_circular_deps_outside_l3_core`: call `_detect_cycles_in_graph(import_graph)`
- `test_no_circular_deps_within_l3_core`: call `_detect_cycles_in_graph(import_graph)`

**Verification**:
- Run both tests to ensure they still work correctly
- Verify the extracted method has no duplication
- Check that test results remain unchanged

## Execution Steps

1. **Fix Finding 1**: Update xfail reason in test_dependency_direction.py:210-212
2. **Fix Finding 2**: Update test reference in v3-module-architecture-standard.md:50
3. **Fix Finding 3**: Extract DFS helper method and update both tests
4. **Run Verification**: `uv run pytest tests/vibe3/test_modularity/ -v`
   - Expected: 10 passed, 6 xfailed, 0 xpassed
5. **Type Check**: `uv run mypy src/vibe3`
   - Expected: No errors

## Audit Reference

Full audit report: docs/reports/issue-1992-audit-report.md
View with: `vibe3 handoff show @audit --branch task/issue-1992`

## Notes

- All fixes are minor code quality improvements
- No functional changes to test behavior
- No changes to production code
- Scope remains limited to test files and documentation
