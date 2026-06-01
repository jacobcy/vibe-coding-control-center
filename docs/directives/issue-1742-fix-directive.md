# Fix Directive: Issue #1742 — Color Map Event Name Mismatch

**Reference**: docs/reports/issue-1742-audit-report.md
**Verdict**: MAJOR
**Priority**: HIGH (blocking UI color rendering)

## Problem Summary

The color map entries use role names directly (e.g., `codeagent_planner_warning`), but `_severity_event_type()` uses `execution_prefix(role)` which produces different prefixes for planner/executor/reviewer roles. This mismatch causes events to render without colors in the timeline UI.

## Required Fixes

### Fix 1: Update color map keys (MAJOR)

**File**: `src/vibe3/ui/flow_ui_timeline.py` (lines 99-111)

Change 6 color keys from role names to execution prefixes:

```python
# BEFORE (wrong):
codeagent_planner_warning = "yellow"
codeagent_planner_error = "red"
codeagent_executor_warning = "yellow"
codeagent_executor_error = "red"
codeagent_reviewer_warning = "yellow"
codeagent_reviewer_error = "red"

# AFTER (correct):
codeagent_plan_warning = "yellow"
codeagent_plan_error = "red"
codeagent_run_warning = "yellow"
codeagent_run_error = "red"
codeagent_review_warning = "yellow"
codeagent_review_error = "red"
```

**Why**: `execution_prefix()` maps:
- planner → `plan`
- executor → `run`
- reviewer → `review`

### Fix 2: Add unit tests for `_severity_event_type` (MINOR)

**File**: Create `tests/vibe3/execution/test_codeagent_runner_severity.py`

Test all three severity mappings:
- WARNING → `*_warning`
- ERROR → `*_error`
- CRITICAL → `*_aborted`

Test all six roles to verify execution_prefix mapping.

## Verification Commands

```bash
# Run all tests
uv run pytest tests/ -xvs

# Type check
uv run mypy src/vibe3/

# Lint
uv run ruff check src/vibe3/

# Verify color map keys match execution_prefix output
uv run python -c "
from vibe3.execution.codeagent_runner import _severity_event_type
from vibe3.ui.flow_ui_timeline import EVENT_COLORS

roles = ['planner', 'executor', 'reviewer', 'manager', 'supervisor', 'governance']
for role in roles:
    for severity in ['WARNING', 'ERROR', 'CRITICAL']:
        event_type = _severity_event_type(role, severity)
        if event_type in EVENT_COLORS:
            print(f'✓ {event_type}: {EVENT_COLORS[event_type]}')
        else:
            print(f'✗ {event_type}: MISSING')
"
```

## Expected Outcome

After fix:
- All 12 new event types (6 roles × 2 severities) have matching color entries
- Timeline UI renders warning/error events with correct colors
- All tests pass
- Type checking and linting clean

## Commit Message

```
fix(ui): correct color map keys to match execution_prefix output

- Change codeagent_planner_* → codeagent_plan_*
- Change codeagent_executor_* → codeagent_run_*
- Change codeagent_reviewer_* → codeagent_review_*
- Add unit tests for _severity_event_type()

Fixes MAJOR finding from audit: color map entries were using role names
directly, but _severity_event_type uses execution_prefix which maps
differently for planner/executor/reviewer roles.
```
