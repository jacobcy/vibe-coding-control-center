## Why

Currently, several parts of the system treat `worktree/path` and `worktrees.json` as logical anchors for a flow or task, rather than just "open site containers". According to `docs/standards/v2/git-workflow-standard.md`, flows should only be bound to branches, not worktrees. This change removes these legacy worktree dependencies to align the codebase with the updated standard and prevent data quality issues related to worktree path bindings.

## What Changes

- Remove worktree directory and path dependencies from `lib/flow_runtime.sh`.
- Update `lib/task_query.sh` to stop reverse-looking up `current_task` via `worktrees.json` using the current directory path.
- Refactor `lib/check_pr_status.sh` to read branch bindings directly instead of checking `assigned_worktree` and `worktrees.json`.
- Remove legacy worktree branch repair logic from `lib/task_audit.sh` and `lib/task_audit_branches.sh`, as worktrees no longer dictacte branch data quality.
- Update `lib/task_actions.sh` remove/bind actions to no longer check `worktrees.json` for task bindings.
- Update documentation in `docs/standards/v2/command-standard.md` to clarify that vibe flow does not use `worktrees.json` to express the open site/container as a logical anchor.

## Capabilities

### New Capabilities
- `worktree-logic-decoupling`: Refactoring the flow and task resolution to fully decouple from worktree physical paths and `worktrees.json` bindings, relying exclusively on branches as the logical anchor.

### Modified Capabilities


## Impact

- **Code**: `lib/flow_runtime.sh`, `lib/task_query.sh`, `lib/check_pr_status.sh`, `lib/task_audit.sh`, `lib/task_audit_branches.sh`, `lib/task_actions.sh`.
- **Documentation**: `docs/standards/v2/command-standard.md`.
- **System**: Flow and task resolution will no longer fail or behave unexpectedly if a worktree is moved or removed, as branch bindings are the sole source of truth.
