## Context
Currently, each isolation environment (worktree) in Vibe Center is mapped to exactly one task. This 1:1 mapping is too restrictive for complex workflows where multiple tasks might share the same context or where subtasks need to be isolated together. Additionally, parameter naming inconsistency between `vibe flow` and `vibe task` creates friction.

## Goals / Non-Goals

**Goals:**
- Support 1:N mapping (one worktree to multiple tasks) in the data layer (`worktrees.json`).
- Enable adding tasks to an existing worktree via `vibe flow start --task <id>`.
- Standardize on `--branch` as the primary parameter for specifying source/target branches across all commands.
- Update UI/Reports to show assigned tasks grouping.

**Non-Goals:**
- Implementing actual task dependency trees (parent/child) in this phase.
- Supporting cross-worktree task migration (moving a task from one WT to another seamlessly) - this remains manual unbind/bind.

## Decisions

### 1. Worktrees Schema Extension
We will update `worktrees.json` elements:
```json
{
  "worktree_name": "...",
  "current_task": "task-1", // The primary/focused task
  "tasks": ["task-1", "task-2"], // All bound tasks
  ...
}
```

### 2. Parameter Consolidation
- `vibe flow start` will now accept `--branch <ref>` instead of `--base <ref>`.
- `vibe task start/update` will use `--branch` consistently.
- For `vibe flow start`, if `--task` is provided and the user is already in a feature worktree, the system will bind the task to the current worktree instead of attempting to create a new one.

### 3. Rendering Refactor
`vibe task list` and `vibe flow status` will group tasks by their `assigned_worktree`.
- `● Current Worktree`
  - `Main Task: <id>`
  - `Sub Tasks: [<id>, <id>]`

## Risks / Trade-offs

- **Risk**: Potential data corruption if JQ filters are not robust enough to handle the array transition.
- **Trade-off**: Keeping `current_task` alongside the `tasks` array adds slight redundancy but ensures backward compatibility with existing tools and caches that only expect a single string.
