## Context

Historically, the vibe flow system used `worktree/path` and `worktrees.json` as a semantic anchor to determine the current flow and binding state. However, the standard `docs/standards/v2/git-workflow-standard.md` explicitly states that flows bind only to branches, not worktrees. Relying on physical directories for logical state leads to bugs and data inconsistencies (e.g., when a worktree is moved or removed, the flow state breaks).

## Goals / Non-Goals

**Goals:**
- Decouple all runtime flow logic from `worktree/path` and `worktrees.json`.
- Treat worktrees merely as "open site containers" without attaching logical flow state to their filesystem paths.
- Clean up `lib/flow_runtime.sh`, `lib/task_query.sh`, `lib/check_pr_status.sh`, `lib/task_audit.sh`, `lib/task_audit_branches.sh`, and `lib/task_actions.sh`.
- Rectify documentation `docs/standards/v2/command-standard.md` that still portrays worktrees as logical anchors.

**Non-Goals:**
- Completely remove the ability to use worktrees for development. Worktrees will still be used, but merely as physical directories checked out to branches.
- Change the structure of `tasks.json` or other non-worktree state unless necessary for the decoupling.

## Decisions

1. **Branch as the Sole Source of Truth**: When determining the current flow/task, the system will look at the currently checked-out branch using `git rev-parse --abbrev-ref HEAD` instead of looking up the current path in `worktrees.json`.
2. **Remove Worktree Auditing Logic**: Scripts that try to repair branch entries in `worktrees.json` as part of "data quality" (`lib/task_audit.sh`, `lib/task_audit_branches.sh`) will have that specific worktree-related repair logic removed, because `worktrees.json` is no longer the critical state holder for bindings.
3. **Task Actions Simplification**: Task bind/remove actions will no longer verify against `worktrees.json` to see if a task is "still bound to a worktree."

## Risks / Trade-offs

- **Risk**: Some edge-case scripts or third-party aliases might still rely on `worktrees.json` having exact mapping. We mitigate this by only removing the logical dependency in the core libs.
