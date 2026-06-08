# Fix Directive: Issue #2435 - Validation Gate Bug

## Verdict
MAJOR - Validation blocks valid config-backend + CLI-model workflow

## Problem
`validate_model_backend_dependency` in `command_options.py:56` only checks CLI `backend` parameter but is called before `load_runtime_config()` in all three command files (`run.py:87`, `plan.py:62`, `review.py:76`).

This blocks the exact scenario Step 3 is designed to handle:
- User has `backend: "claude"` in settings.yaml
- User runs: `vibe3 plan --model opus`
- Current behavior: Error "–model requires --backend to be specified."
- Expected behavior: Should work (config provides backend, CLI provides model)

The Step 3 fix (`model or config_model` in `codeagent_support.py:53`) is correct but unreachable via CLI when config provides the backend.

## Required Fix

### Option A: Move validation after config loading (RECOMMENDED)

**Files to modify**: `run.py`, `plan.py`, `review.py`

**Pattern**: Load config before validation, pass config_backend to validation

```python
# Current (run.py:85-88)
backend: str | None = option_backend
model: str | None = option_model
validate_model_backend_dependency(model, backend)  # Too early
config = load_runtime_config(ctx)

# Fixed
backend: str | None = option_backend
model: str | None = option_model
config = load_runtime_config(ctx)  # Load config first
config_backend = config.backend if config else None
validate_model_backend_dependency(model, backend, config_backend)  # Pass config info
```

Apply the same pattern to:
- `run.py:87` (run_command function)
- `run.py:264` (default function)
- `plan.py:62` (_plan_for_branch function)
- `plan.py:170` (_plan_spec_impl function)
- `review.py:76` (_review_branch_impl function)
- `review.py:227` (base function)

### Update validation function

**File**: `src/vibe3/commands/command_options.py:56`

```python
def validate_model_backend_dependency(
    model: str | None,
    backend: str | None,
    config_backend: str | None = None,
) -> None:
    """Validate that --model requires backend (CLI or config)."""
    if model and not backend and not config_backend:
        typer.echo(
            "Error: --model requires --backend to be specified on CLI or in config.",
            err=True
        )
        raise typer.Exit(1)
```

## Fix Verification

After fix, this should work:
```bash
# User has backend: "claude" in settings.yaml
vibe3 plan --model opus
# Should succeed: config provides backend, CLI provides model
# resolve_command_agent_options should use CLI model (opus) overriding config model
```

## Minor Issue to Also Fix

**File**: `run.py:264` - Remove redundant validation call

When `default()` entry point delegates to `run_command()`, the validation at line 264 runs before the call, then `run_command()` validates again at line 87. Remove the call at line 264 (keep only one validation).

## Reference
- Audit report: docs/reports/issue-2435-audit-report.md
- Plan: docs/plans/issue-2435-implementation-plan.md (Step 3 intent)
