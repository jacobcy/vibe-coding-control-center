# Unify Sync/Async Codeagent Command Construction

## Background

Current state: sync and async modes have separate code paths for building codeagent commands.

- **Sync**: `command → usecase → execution_pipeline → execute_agent → run_review_agent()`
- **Async**: `build_async_*()` → tmux → child re-enters CLI → sync path

The `build_async_*` methods manually concatenate CLI arguments, duplicating typer's parameter definitions.

## Problem

3 duplicate methods that manually build CLI commands:

| File | Method | Lines |
|------|--------|-------|
| `run_usecase.py` | `build_async_command()` | 122-145 |
| `plan_usecase.py` | `build_async_task_command()` | 113-140 |
| `plan_usecase.py` | `build_async_spec_command()` | 141-170 |

These methods are redundant because the async child re-enters the same CLI, which then goes through the same codeagent command construction in `run_review_agent()`. The manual CLI argument concatenation is fragile and drifts from typer's actual parameter definitions.

## Goal

Sync and async should share ONE codeagent command construction path. The ONLY difference between sync and async is execution: direct subprocess vs tmux session.

## Plan

### Phase 1: Unify async entry point

Replace `build_async_*` methods with a single generic function that reconstructs the current CLI invocation for tmux:

```python
# In async_execution_service.py or a shared module
def build_self_invocation(extra_args: list[str] | None = None) -> list[str]:
    """Build the vibe3 CLI command for async re-invocation."""
    cmd = ["uv", "run", "python", "src/vibe3/cli.py"]
    if extra_args:
        cmd.extend(extra_args)
    return cmd
```

Or simpler: extract `sys.argv` and strip `--async`, pass remaining args to tmux.

### Phase 2: Remove build_async_* methods

Delete from:
- `src/vibe3/services/run_usecase.py` — `build_async_command()`
- `src/vibe3/services/plan_usecase.py` — `build_async_task_command()`, `build_async_spec_command()`

Update callers in:
- `src/vibe3/commands/run.py` — L136
- `src/vibe3/commands/plan.py` — L93, L188

### Phase 3: Ensure workdir is always passed

The recent fix in `review_runner.py` passes `project_root` as a positional arg to codeagent-wrapper. Verify this works for all modes (run/plan/review, sync/async).

## Files to Change

- `src/vibe3/services/async_execution_service.py` — add generic command builder
- `src/vibe3/services/run_usecase.py` — remove `build_async_command()`
- `src/vibe3/services/plan_usecase.py` — remove `build_async_task_command()`, `build_async_spec_command()`
- `src/vibe3/commands/run.py` — use unified builder
- `src/vibe3/commands/plan.py` — use unified builder
- `tests/vibe3/services/test_async_execution_service.py` — update tests

## Risk

- Low: async child currently re-enters CLI, which handles flow state and handoff correctly. Must preserve this behavior.
- Medium: `sys.argv` approach is fragile if CLI structure changes. Prefer explicit argument passing.

## Next Steps

- Review will likely find more duplicate code in plan/review command layers
- Consider whether review command also needs async support (currently missing `build_async_review_command`)
