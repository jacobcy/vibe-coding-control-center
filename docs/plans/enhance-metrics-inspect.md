# Implementation Plan: vibe3 inspect metrics Enhancement

## Overview

Enhance the `vibe3 inspect metrics` command to include: (1) Scripts metrics from `scripts/` directory, (2) Hierarchical Python metrics by subdirectory, and (3) Dead function warnings using existing Serena symbol analysis.

## Requirements

- **Scripts Metrics**: Display metrics for `scripts/` directory based on `config/settings.yaml` `scripts_paths` configuration
- **Hierarchical Python Metrics**: Show LOC breakdown by subdirectory (clients, commands, services, etc.)
- **Dead Function Warnings**: List potentially dead functions (non-CLI functions with 0 references)

## Architecture Changes

| File | Change Description |
|------|-------------------|
| `src/vibe3/services/metrics_service.py` | Add ScriptsMetrics model, hierarchical Python metrics, and dead function detection |
| `src/vibe3/commands/inspect.py` | Update output format to display scripts metrics, hierarchical Python metrics, and dead functions |
| `config/settings.yaml` | Add scripts_total_loc limit (optional, for consistency) |

## Implementation Steps

### Phase 1: Data Model Extensions

**Step 1.1: Add ScriptsMetrics model** (File: `src/vibe3/services/metrics_service.py`)
- Action: Create `ScriptsMetrics` model similar to `LayerMetrics` but without file-level warnings/errors
- Why: Scripts have different quality requirements than core code
- Dependencies: None
- Risk: Low
- Estimated complexity: Small (10-15 lines)

```python
class ScriptsMetrics(BaseModel):
    """Scripts directory metrics (no strict limits)."""
    total_loc: int
    file_count: int
    max_file_loc: int
    files: list[FileMetrics]
```

**Step 1.2: Add SubdirMetrics model for hierarchical display** (File: `src/vibe3/services/metrics_service.py`)
- Action: Create `SubdirMetrics` model to hold per-subdirectory statistics
- Why: Enable hierarchical Python metrics breakdown
- Dependencies: None
- Risk: Low
- Estimated complexity: Small (10 lines)

```python
class SubdirMetrics(BaseModel):
    """Subdirectory metrics for hierarchical display."""
    name: str  # e.g., "services", "clients"
    loc: int
    file_count: int
    max_file_loc: int
```

**Step 1.3: Add PythonDetailedMetrics model** (File: `src/vibe3/services/metrics_service.py`)
- Action: Extend Python metrics to include subdirectory breakdown
- Why: Support hierarchical display while maintaining backward compatibility
- Dependencies: Steps 1.1, 1.2
- Risk: Low
- Estimated complexity: Small (15-20 lines)

```python
class PythonDetailedMetrics(BaseModel):
    """Python metrics with hierarchical breakdown."""
    total_loc: int
    file_count: int
    max_file_loc: int
    files: list[FileMetrics]
    limit_total: int
    limit_file_default: int
    limit_file_max: int
    subdirs: list[SubdirMetrics]  # NEW: hierarchical breakdown
```

**Step 1.4: Add DeadFunctionInfo model** (File: `src/vibe3/services/metrics_service.py`)
- Action: Create model for dead function information
- Why: Structure the dead function warning output
- Dependencies: None
- Risk: Low
- Estimated complexity: Small (10 lines)

```python
class DeadFunctionInfo(BaseModel):
    """Information about a potentially dead function."""
    name: str
    file: str
    line: int
    is_cli_candidate: bool  # True if in a file that might be CLI entry
```

**Step 1.5: Update MetricsReport model** (File: `src/vibe3/services/metrics_service.py`)
- Action: Add `scripts` field and `dead_functions` field to `MetricsReport`
- Why: Include new metrics in the report
- Dependencies: Steps 1.1-1.4
- Risk: Low
- Estimated complexity: Small (5 lines)

### Phase 2: Metrics Collection Functions

**Step 2.1: Add collect_scripts_metrics function** (File: `src/vibe3/services/metrics_service.py`)
- Action: Create function to collect scripts/ directory metrics
- Why: Support scripts metrics display
- Dependencies: Phase 1
- Risk: Low
- Estimated complexity: Medium (30-40 lines)
- Details: Read paths from `config.code_limits.scripts_paths.v2_shell`

**Step 2.2: Add _collect_python_subdir_metrics helper** (File: `src/vibe3/services/metrics_service.py`)
- Action: Create helper function to compute per-subdirectory metrics
- Why: Enable hierarchical display
- Dependencies: None
- Risk: Low
- Estimated complexity: Medium (25-35 lines)
- Details: Group files by parent directory (clients, commands, services, etc.)

**Step 2.3: Update collect_python_metrics function** (File: `src/vibe3/services/metrics_service.py`)
- Action: Modify to return `PythonDetailedMetrics` with subdirectory breakdown
- Why: Include hierarchical data in collection
- Dependencies: Step 2.2
- Risk: Medium (backward compatibility concern)
- Estimated complexity: Medium (20-30 lines)
- Note: Maintain backward compatibility with existing tests

**Step 2.4: Add detect_dead_functions function** (File: `src/vibe3/services/metrics_service.py`)
- Action: Create function to detect potentially dead functions
- Why: Enable dead function warnings
- Dependencies: None (uses existing SerenaService)
- Risk: Medium (Serena dependency, performance)
- Estimated complexity: Medium (40-50 lines)
- Details:
  - Iterate through Python files
  - For each function, check reference count via SerenaService
  - Identify non-CLI files with 0-reference functions
  - Handle gracefully if Serena is unavailable

**Step 2.5: Update collect_metrics function** (File: `src/vibe3/services/metrics_service.py`)
- Action: Include scripts metrics and dead functions in report
- Why: Complete the enhanced report
- Dependencies: Steps 2.1, 2.3, 2.4
- Risk: Low
- Estimated complexity: Small (10-15 lines)

### Phase 3: Command Output Updates

**Step 3.1: Update metrics command output** (File: `src/vibe3/commands/inspect.py`)
- Action: Modify `metrics` command to display new sections
- Why: Show enhanced metrics to users
- Dependencies: Phase 2
- Risk: Low
- Estimated complexity: Medium (40-50 lines)

### Phase 4: Configuration (Optional)

**Step 4.1: Add scripts total_loc limit** (File: `config/settings.yaml`)
- Action: Add `scripts_total_loc` configuration option
- Why: Consistency with other metrics sections
- Dependencies: None
- Risk: Low
- Estimated complexity: Trivial (2 lines)

### Phase 5: Testing

**Step 5.1: Add tests for ScriptsMetrics** (File: `tests/vibe3/services/test_metrics_service.py`)
- Action: Add unit tests for scripts metrics collection
- Dependencies: Phase 2
- Risk: Low
- Estimated complexity: Medium (30-40 lines)

**Step 5.2: Add tests for hierarchical Python metrics** (File: `tests/vibe3/services/test_metrics_service.py`)
- Action: Add unit tests for subdirectory metrics
- Dependencies: Phase 2
- Risk: Low
- Estimated complexity: Medium (30-40 lines)

**Step 5.3: Add tests for dead function detection** (File: `tests/vibe3/services/test_metrics_service.py`)
- Action: Add unit tests with mocked SerenaService
- Dependencies: Phase 2
- Risk: Low
- Estimated complexity: Medium (40-50 lines)

## Proposed Output Format

```
=== Shell Metrics ===
  Total LOC : 5234 / 7000 OK
  Max file  : 189 / 300 OK
  Files     : 42

=== Scripts Metrics ===
  Total LOC : 1256
  Max file  : 234
  Files     : 18

=== Python Metrics ===
  Total LOC : 8934 / 12000 OK
  Max file  : 287 / 300 OK
  Files     : 76

  By Directory:
    clients/     : 2134 LOC, 13 files, max 189
    commands/    : 2341 LOC, 21 files, max 234
    config/      :  456 LOC,  4 files, max 156
    exceptions/  :   89 LOC,  1 file,  max  89
    models/      :  567 LOC,  7 files, max 134
    observability:  234 LOC,  4 files, max  98
    services/    : 2678 LOC, 19 files, max 287
    ui/          :  345 LOC,  4 files, max 123
    utils/       :   90 LOC,  3 files, max  45

=== Dead Functions Warning ===
  Potentially unused functions (0 references):
    _helper_func in src/vibe3/services/flow_service.py:234
    deprecated_action in src/vibe3/commands/pr.py:89 (possible CLI entry)

  Note: CLI commands may show 0 code references (invoked via CLI, not imported)
```

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| **Serena unavailable** | Gracefully skip dead function detection; show warning message |
| **Performance (dead function scan)** | Limit scan to core services/commands; cache results; make it optional with flag |
| **False positives (dead functions)** | Mark CLI candidates clearly; document that 0 refs does not mean dead |
| **Backward compatibility** | `MetricsReport` model extension is additive; existing `shell` and `python` fields unchanged |
| **Configuration changes** | Use existing `scripts_paths` from config; no new required fields |

## Success Criteria

- [ ] `vibe3 inspect metrics` displays Scripts Metrics section
- [ ] Python Metrics shows hierarchical breakdown by subdirectory
- [ ] Dead function warnings are displayed when functions have 0 references
- [ ] CLI command functions are properly identified (not marked as dead)
- [ ] Existing tests pass
- [ ] New tests cover added functionality
- [ ] JSON output (`--json` flag) includes all new fields
- [ ] Graceful degradation when Serena is unavailable

## Dependencies

- **SerenaService**: Existing service for symbol analysis (already in codebase)
- **config/settings.yaml**: Already has `scripts_paths` configuration
- **typer**: For checking CLI files (already used)

## Files Summary

| File Path | Lines to Modify | Complexity |
|-----------|-----------------|------------|
| `src/vibe3/services/metrics_service.py` | ~150 new lines | Medium |
| `src/vibe3/commands/inspect.py` | ~50 lines modified | Low-Medium |
| `config/settings.yaml` | ~2 lines (optional) | Trivial |
| `tests/vibe3/services/test_metrics_service.py` | ~120 new lines | Medium |

## Recommended Implementation Order

1. Phase 1 (Data Models) - Foundation for all changes
2. Phase 2.1 (Scripts Metrics) - Quickest win, uses existing patterns
3. Phase 2.2-2.3 (Hierarchical Python) - Medium complexity, high value
4. Phase 3.1 (Output Updates for Scripts + Hierarchical) - Can be tested incrementally
5. Phase 2.4-2.5 (Dead Functions) - More complex, depends on Serena
6. Phase 3.1 continued (Dead Functions Output)
7. Phase 5 (Tests) - Validate all changes
