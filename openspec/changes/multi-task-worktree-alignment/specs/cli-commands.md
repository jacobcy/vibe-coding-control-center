## MODIFIED Requirements for cli-commands.yaml

### Requirement: flow-start-parameter-alignment
The `vibe flow start` command should use `--branch` instead of `--base` to specify the starting branch.

#### Scenario: Using --branch in flow start
- **WHEN** user runs `vibe flow start my-feature --branch develop`
- **THEN** it should create a worktree based on `develop` branch.

### Requirement: flow-start-assign-task
The `vibe flow start --task <id>` command should support assigning a task to the current worktree if already inside one.

#### Scenario: Assign task to current worktree
- **WHEN** user is in `wt-feature-1` and runs `vibe flow start --task task-2`
- **THEN** it should bind `task-2` to `wt-feature-1` and record it in `worktrees.json`.

### Requirement: multi-task-binding-schema
The `worktrees.json` should support multiple tasks per worktree.

#### Scenario: Multiple tasks in registry
- **WHEN** user binds a second task to a worktree
- **THEN** both tasks should be visible in `vibe flow status`.
