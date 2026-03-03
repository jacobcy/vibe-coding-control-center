# Proposal: Multi-Task Worktree Alignment

## Problems
1. **1:1 Constraint**: Currently, each worktree is bound to a single `current_task`. This makes it difficult to work on multiple related tasks or subtasks within the same isolation environment (branch/worktree).
2. **Semantic Confusion**: The parameter `--base` is used in `vibe flow start` to specify the starting branch, but in `vibe task` context, `--branch` is more common and intuitive.
3. **Implicit Flow**: When running `vibe flow start --task <id>` inside an existing worktree, the system should ideally allow assigning that task to the current environment rather than just erroring out or trying to create a new one.

## What Changes
1. **Multi-Task Binding**:
   - Update `worktrees.json` to support a list of tasks per worktree.
   - Designate the first or explicitly selected task as the "Main Task".
2. **Refined Start Logic**:
   - `vibe flow start <feature>` creates a new worktree (existing behavior).
   - `vibe flow start --task <id>` inside a worktree assigns the task to that worktree (new behavior).
3. **Semantic Consolidation**:
   - Change `--base` parameters to `--branch` in `vibe flow` and `vibe task` commands.
   - Update help documentation to reflect these changes.
4. **Data Integrity**:
   - Ensure `vibe task update --bind-current` correctly handles the new multi-task structure.

## Capabilities

### New Capabilities
- `multi-task-support`: Implementation of multiple tasks per worktree in `worktrees.json` and logic to manage them.

### Modified Capabilities
- `flow-workflow`: Update `vibe flow start` and `vibe flow status` to handle multi-tasking and renamed parameters.
- `task-management`: Update `vibe task` actions to support multiple assignments and `--branch` parameter.

## Impact
- **Files**: `lib/flow.sh`, `lib/flow_help.sh`, `lib/task_actions.sh`, `lib/task_write.sh`, `lib/task_render.sh`.
- **Data**: `worktrees.json` schema will be extended.
- **Documentation**: CLI help strings and possibly README/specs.
