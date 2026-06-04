---
name: vibe-closeout
description: Use when manager has signaled flow terminal state cleanup via handoff indicate. Reads cleanup instructions and executes FlowCleanupService. Do not use for code changes or PR creation.
---

# /vibe-closeout - Flow Terminal State Cleanup

This skill handles cleanup of flow scenes when they reach terminal states (done/aborted).

**Trigger Condition**: Manager has written handoff indicate with cleanup instructions for a terminal flow.

## Related Skills

- **vibe-done**: Human-initiated manual cleanup after PR merge (for human collaboration)
- **vibe-integrate**: PR merge workflow

Use `vibe-closeout` for **automated** cleanup triggered by Manager signal.
Use `vibe-done` for human-initiated cleanup after confirming PR merge.

## Purpose

Execute cleanup of flow resources (worktree, branches, handoff files, flow records) based on manager's cleanup instructions.

## When to Use

Use this skill when:
- Manager has detected a terminal flow (done/aborted)
- Handoff indicate contains cleanup instructions with `cleanup_mode` and `branch`
- Physical cleanup of flow scene is needed

Do NOT use for:
- Code changes or bug fixes
- PR creation or review
- Issue label changes (except via resume_issue)

## Core Workflow

### Step 1: Read Handoff Indicate

Read cleanup instructions from handoff indicate:

```bash
uv run python src/vibe3/cli.py handoff status <branch>
```

Expected instruction format:
- cleanup_mode: "preserve" (for done flows) or "reset" (for aborted flows)
- branch: <branch-name>
- reason: "flow reached terminal state"
- keep_flow_record: True/False

### Step 2: Verify Instructions

Before executing cleanup:
- Confirm handoff indicate exists and contains cleanup instructions
- Verify `cleanup_mode` is either "preserve" or "reset"
- Verify `branch` field is present and non-empty

If verification fails:
- Write handoff append: "Cleanup skipped - missing or invalid instructions"
- Exit

### Step 3: Execute Cleanup

Execute cleanup using existing cleanup service:

**Option A: Using CLI (Recommended)**

```bash
uv run python src/vibe3/cli.py check --clean-branch
```

This command will automatically detect and clean terminal flows.

**Option B: Using FlowCleanupService directly**

If more control is needed, the service can be invoked programmatically:

```python
from vibe3.services.flow_cleanup_service import FlowCleanupService
from vibe3.services.flow_service import FlowService
from vibe3.clients.sqlite_client import SQLiteClient

store = SQLiteClient()
flow_service = FlowService(store=store)
cleanup_service = FlowCleanupService(flow_service=flow_service)

# Determine parameters from cleanup_mode
keep_flow_record = (cleanup_mode == "preserve")

# Execute cleanup
results = cleanup_service.cleanup_flow_scene(
    branch=branch,
    include_remote=True,
    terminate_sessions=True,
    keep_flow_record=keep_flow_record,
    force_delete=False
)
```

### Step 4: Verify Cleanup Results

After cleanup execution:

1. Check worktree removal:
   ```bash
   git worktree list
   ```

2. Check branch deletion:
   ```bash
   git branch -a | grep <branch>
   ```

3. Check handoff cleanup:
   ```bash
   uv run python src/vibe3/cli.py handoff status <branch>
   ```

4. Check flow record:
   ```bash
   uv run python src/vibe3/cli.py flow show
   ```

### Step 5: Record Completion

Write handoff append confirming cleanup:

```bash
uv run python src/vibe3/cli.py handoff append "Cleanup completed: <branch> - mode: <cleanup_mode>" --kind note
```

## Cleanup Modes

### preserve (for done/merged flows)

- **keep_flow_record**: True
- **Behavior**: Preserve flow record as completion history
- **Actions**:
  - Remove worktree
  - Delete local branch
  - Delete remote branch
  - Clear handoff files
  - Keep flow record in database

### reset (for aborted flows)

- **keep_flow_record**: False
- **Behavior**: Soft delete flow record (preserve audit trail)
- **Actions**:
  - Remove worktree
  - Delete local branch
  - Delete remote branch
  - Clear handoff files
  - Soft delete flow record (can be recovered if needed)

## Permission Boundaries

**Allowed**:
- Read handoff indicate for cleanup instructions
- Execute cleanup via existing service/CLI
- Write handoff append for completion status
- Terminate tmux sessions (via FlowCleanupService)

**Forbidden**:
- Code changes (any file modifications)
- PR creation
- Issue label changes (except via resume_issue)
- Hard delete flow records (unless explicitly instructed)

## Error Handling

If cleanup fails:

1. **Record failure**: Write handoff append with failure details
2. **Do NOT retry**: Cleanup failures require human intervention
3. **Report**: Write issue comment if needed to notify stakeholders

Example handoff append for failure:
```bash
uv run python src/vibe3/cli.py handoff append "Cleanup failed for <branch>: <error-details>" --kind blocker
```

## Verification Commands

```bash
# Check flow status
uv run python src/vibe3/cli.py flow show

# View handoff events
uv run python src/vibe3/cli.py handoff status <branch>

# Execute cleanup (manual)
uv run python src/vibe3/cli.py check --clean-branch
```

## Architecture Alignment

- **Permission Contract**: Closeout reads handoff, executes cleanup, writes completion status
- **FlowCleanupService**: Existing service provides complete cleanup ability
- **Handoff Communication**: Manager signals via handoff indicate, closeout reads and executes
- **Single-writer principle**: Manager writes indicate, closeout reads and executes
