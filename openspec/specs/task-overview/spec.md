# task-overview Specification

## Purpose
Display a comprehensive overview of all tasks across worktrees with health indicators and registration status.

## Requirements

### Requirement: Task health indicators
The system SHALL display health indicators for each task in the overview.

#### Scenario: Show registration status
- **WHEN** task overview is displayed
- **THEN** each task shows whether it is:
  - ✓ Properly registered (has task_id, assigned_worktree, and status)
  - ⚠ Missing worktree assignment (task exists but no worktree)
  - ✗ Not in registry (worktree exists but no task in registry)

#### Scenario: Show data quality status
- **WHEN** task has associated worktree
- **THEN** overview displays:
  - Branch field status (valid branch or null)
  - Dirty state (clean or number of uncommitted files)

#### Scenario: Highlight tasks needing attention
- **WHEN** task has health issues
- **THEN** system highlights it with warning icon and brief description

### Requirement: Unregistered task detection in overview
The system SHALL detect and display unregistered tasks during overview.

#### Scenario: Detect worktrees without tasks
- **WHEN** worktree exists in worktrees.json but has no corresponding task in registry
- **THEN** overview displays it as "Unregistered worktree" with worktree_name

#### Scenario: Detect branches without tasks
- **WHEN** branch exists matching task pattern but no task in registry
- **THEN** overview suggests it may be an unregistered task

#### Scenario: Show OpenSpec changes not in registry
- **WHEN** OpenSpec change exists but no task in registry
- **THEN** overview displays it as "Unsynced OpenSpec change"

### Requirement: Audit summary in overview
The system SHALL include a summary of task registration health.

#### Scenario: Display health summary
- **WHEN** task overview is displayed
- **THEN** system shows summary at top:
  - Total tasks registered
  - Tasks with issues (missing worktree, null branch, etc.)
  - Unregistered worktrees
  - Unsynced OpenSpec changes

#### Scenario: Suggest running audit
- **WHEN** overview detects health issues
- **THEN** system suggests: "Run `vibe task audit` for detailed analysis"

### Requirement: Enhanced worktree status display
The system SHALL display more detailed worktree status information.

#### Scenario: Show branch information
- **WHEN** worktree has a branch
- **THEN** overview displays branch name next to worktree

#### Scenario: Show PR status if available
- **WHEN** worktree's branch has an associated PR
- **THEN** overview displays PR number and state (open/merged/closed)

#### Scenario: Show last updated timestamp
- **WHEN** worktree entry has last_updated field
- **THEN** overview displays relative time (e.g., "2 hours ago")

### Requirement: Task overview filtering
The system SHALL support filtering tasks by health status.

#### Scenario: Filter by healthy tasks
- **WHEN** user runs `vibe task list --healthy`
- **THEN** system only shows tasks with no health issues

#### Scenario: Filter by tasks with issues
- **WHEN** user runs `vibe task list --issues`
- **THEN** system only shows tasks that need attention

#### Scenario: Filter by unregistered
- **WHEN** user runs `vibe task list --unregistered`
- **THEN** system shows worktrees/branches/changes not in registry

### Requirement: CLI task list command
The system SHALL provide a command to list all tasks across worktrees.

#### Scenario: List all tasks
- **WHEN** user runs `vibe task list`
- **THEN** system displays all tasks from registry in a formatted table

#### Scenario: JSON output
- **WHEN** user runs `vibe task list --json`
- **THEN** system outputs task data in JSON format including health metadata

#### Scenario: Filter by status
- **WHEN** user runs `vibe task list --status in_progress`
- **THEN** system only shows tasks with matching status

### Requirement: JSON output with health metadata
The system SHALL include health metadata in JSON output.

#### Scenario: Health field in JSON
- **WHEN** user runs `vibe task list --json`
- **THEN** each task includes a `health` object with:
  - `registered`: boolean
  - `has_worktree`: boolean
  - `branch_valid`: boolean
  - `issues`: array of issue descriptions

#### Scenario: Unregistered items in JSON
- **WHEN** JSON output includes unregistered items
- **THEN** they appear in a separate `unregistered` array with:
  - `type`: "worktree" | "branch" | "openspec_change"
  - `name`: identifier
  - `suggested_action`: what to do
