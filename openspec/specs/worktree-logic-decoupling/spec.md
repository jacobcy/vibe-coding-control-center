# Worktree Logic Decoupling

## Purpose
Decouple flow and task runtimes from `worktrees.json` and physical paths, using the currently checked-out branch as the sole logical anchor.

## Requirements

### Requirement: Branch-Based Flow Anchoring
The system must derive flow and task resolution entirely from the currently checked-out Git branch, rather than the physical path of the worktree directory. When a role declares `worktree_requirement` in its `RoleDefinition`, the `ExecutionCoordinator` SHALL resolve the worktree through the environment layer, not through role-specific logic.

#### Scenario: Identifying Current Flow
- **WHEN** a user executes a `vibe flow` command inside any worktree or the main repository
- **THEN** the system identifies the flow based on the current branch name, ignoring any `worktrees.json` mappings or `git rev-parse --show-toplevel` path comparisons.

#### Scenario: Role declares worktree requirement
- **WHEN** a role's `RoleDefinition` specifies `worktree_requirement=PERMANENT`
- **THEN** `ExecutionCoordinator` SHALL use `WorktreeManager` from the environment layer to resolve or create the worktree
- **AND** the role module SHALL NOT contain any worktree creation or management logic

#### Scenario: Role declares no worktree requirement
- **WHEN** a role's `RoleDefinition` specifies `worktree_requirement=NONE`
- **THEN** `ExecutionCoordinator` SHALL use the current repository root as the execution cwd
- **AND** no worktree resolution SHALL occur

### Requirement: Task Binding Independent of Worktrees
Task bindings (assigned/removed) must not rely on `worktrees.json` to dictate validation or data quality. Worktree management SHALL be fully encapsulated in the environment layer and driven by `RoleDefinition.worktree_requirement`.

#### Scenario: Auditing Task Bindings
- **WHEN** the system audits task registry or branch data quality
- **THEN** it does not evaluate or repair `worktrees.json` branch mappings as a component of task data health.

#### Scenario: Role execution with worktree
- **WHEN** a role execution is dispatched and the role requires a worktree
- **THEN** the environment layer SHALL manage worktree lifecycle independently
- **AND** the role module SHALL NOT be aware of worktree implementation details
