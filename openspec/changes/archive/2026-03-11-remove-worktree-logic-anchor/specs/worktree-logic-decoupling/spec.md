## ADDED Requirements

### Requirement: Branch-Based Flow Anchoring
The current flow and task resolution must be derived entirely from the currently checked-out Git branch, rather than the physical path of the worktree directory.

#### Scenario: Identifying Current Flow
- **WHEN** a user executes a `vibe flow` command inside any worktree or the main repository
- **THEN** the system identifies the flow based on the current branch name, ignoring any `worktrees.json` mappings or `git rev-parse --show-toplevel` path comparisons.

### Requirement: Task Binding Independent of Worktrees
Task bindings (assigned/removed) must not rely on `worktrees.json` to dictate validation or data quality.

#### Scenario: Auditing Task Bindings
- **WHEN** the system audits task registry or branch data quality
- **THEN** it does not evaluate or repair `worktrees.json` branch mappings as a component of task data health.
