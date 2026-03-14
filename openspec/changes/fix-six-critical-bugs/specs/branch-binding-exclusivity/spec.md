# Spec: Branch Binding Exclusivity

## ADDED Requirements

### Requirement: Automatic Branch Inference
The system SHALL automatically infer the current git branch when `--bind-current` flag is used, without requiring explicit branch argument.

#### Scenario: Bind current branch
- **WHEN** user runs `vibe task update <task-id> --bind-current`
- **THEN** the system SHALL detect the current git branch using `git branch --show-current`
- **AND** the detected branch SHALL be persisted as `runtime_branch` in the task metadata
- **AND** no explicit `--branch` argument SHALL be required

#### Scenario: No current branch (detached HEAD)
- **WHEN** user runs `vibe task update <task-id> --bind-current` in detached HEAD state
- **THEN** the system SHALL fail with an error message
- **AND** the error SHALL explain that binding requires being on a named branch

### Requirement: Branch Exclusivity Enforcement
The system SHALL prevent binding a branch to a task if that branch is already bound to another active task.

#### Scenario: Conflict detection
- **WHEN** user attempts to bind a branch that is already bound to another active task
- **THEN** the system SHALL fail with an error message containing:
  - The conflicting task ID
  - The conflicting task status
  - The branch name
  - The worktree path (if available)
- **AND** the binding SHALL NOT be created

#### Scenario: Non-active task conflict
- **WHEN** a branch is bound to a task with status `done` or `archived`
- **THEN** the system SHALL allow rebinding to a new task
- **AND** the old binding SHALL be automatically cleared

#### Scenario: Same task rebind
- **WHEN** user binds a branch to the same task that already owns it
- **THEN** the system SHALL succeed (idempotent operation)
- **AND** no error SHALL be raised

### Requirement: Binding Persistence
The system SHALL persist branch bindings in the task registry with atomic write semantics.

#### Scenario: Atomic binding update
- **WHEN** a branch binding is created or updated
- **THEN** the task registry file SHALL be updated atomically (write to temp, then rename)
- **AND** concurrent reads SHALL not see partial updates

#### Scenario: Registry query performance
- **WHEN** checking for existing branch bindings
- **THEN** the system SHALL use indexed lookup (jq select with branch field)
- **AND** lookup time SHALL be O(n) where n is the number of active tasks
- **AND** performance SHALL be acceptable for registries with up to 100 active tasks
