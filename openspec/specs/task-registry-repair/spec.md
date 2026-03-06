# task-registry-repair Specification

## Purpose
Automatically repair task registry data quality issues and register unregistered tasks to maintain task registry integrity.

## Requirements

### Requirement: Data quality repair
The system SHALL automatically fix data quality issues in worktrees.json.

#### Scenario: Repair null branch fields
- **WHEN** user runs `vibe task audit --fix-branches`
- **THEN** system queries git for each worktree's actual branch and updates worktrees.json

#### Scenario: Preserve existing data
- **WHEN** worktree already has a valid branch field
- **THEN** system does NOT overwrite it

#### Scenario: Backup before repair
- **WHEN** system modifies worktrees.json
- **THEN** it creates a backup at worktrees.json.backup before making changes

  - Backup file location

#### Scenario: Display repair summary
- **WHEN** repair completes
- **THEN** system displays:
  - Number of worktrees fixed
  - list of updated worktree_name → branch mappings
  - location of backup file

### Requirement: Batch task registration
The system SHALL support registering multiple unregistered tasks in a single operation.

#### Scenario: Register detected unregistered tasks
- **WHEN** user confirms registration of detected tasks
- **THEN** system calls `vibe task register` for each task

#### Scenario: generate task metadata
- **WHEN** registering a task from branch name
- **THEN** system derives:
  - task_id from branch name (YYYY-MM-DD-slug pattern)
  - title from slug
  - status as "in_progress"
  - assigned_worktree from branch's worktree

#### Scenario: register OpenSpec change as task
- **WHEN** registering a task from OpenSpec change
- **THEN** system:
  - Uses change name as task_id
  - reads title from change's proposal.md
  - sets status based on change completion status

### Requirement: Interactive repair confirmation
The system SHALL require user confirmation before executing repairs.

#### Scenario: preview repairs before execution
- **WHEN** user runs `vibe task audit` with repair intent
- **THEN** system displays all detected issues before asking for confirmation

#### Scenario: prompt for confirmation
- **WHEN** repairs are ready to execute
- **THEN** system prompts: "Proceed with repairs? [Y/n]"

#### Scenario: Selective repair
- **WHEN** user wants to review each issue individually
- **THEN** system prompts for each repair:
  ```
  Register task "2026-03-05-feature-a"? [y/n/q]
  y = yes, n = no, q = quit
  ```

#### Scenario: batch approval
- **WHEN** user selects batch mode
- **THEN** system applies all repairs without individual prompts

### Requirement: Repair validation
The system SHALL validate repairs after execution.

#### Scenario: verify task registration
- **WHEN** task is registered
- **THEN** system verifies it appears in registry.json

#### Scenario: verify worktree update
- **WHEN** worktrees.json is updated
- **THEN** system verifies the branch field is no longer null

#### Scenario: rollback on validation failure
- **WHEN** validation fails after repair
- **THEN** system restores from backup file

### Requirement: repair logging
The system SHALL log all repair operations for audit trail.

#### Scenario: log repair actions
- **WHEN** repair is executed
- **THEN** system logs to .agent/logs/repair.log:
  - Timestamp
  - operation type (register task, fix branch, etc.)
  - affected files
  - success/failure status

#### Scenario: display repair history
- **WHEN** user runs `vibe task audit --history`
- **THEN** system shows recent repair operations from log

### Requirement: dry-run mode
The system SHALL support previewing repairs without executing them.

#### scenario: preview repairs
- **WHEN** user runs `vibe task audit --dry-run`
- **THEN** system displays what would be repaired without making changes

#### Scenario: show repair commands
- **WHEN** dry-run mode is active
- **THEN** system displays the exact commands that would be executed

### Requirement: selective repair by category
The system SHALL allow repairing specific categories of issues.

#### Scenario: repair only data quality
- **WHEN** user runs `vibe task audit --fix-branches`
- **THEN** system only repairs null branch fields

#### Scenario: repair only unregistered tasks
- **WHEN** user runs `vibe task audit --register-tasks`
- **THEN** system only registers unregistered tasks from audit results

#### Scenario: repair all issues
- **WHEN** user runs `vibe task audit --fix-all`
- **THEN** system repairs all detected issues (data quality + unregistered tasks)

### Requirement: undo repairs
The system SHALL support undoing recent repairs.

#### Scenario: undo last repair
- **WHEN** user runs `vibe task audit --undo`
- **THEN** system restores from most recent backup file

#### Scenario: list available backups
- **WHEN** user runs `vibe task audit --list-backups`
- **THEN** system shows all backup files with timestamps

#### Scenario: restore specific backup
- **WHEN** user runs `vibe task audit --restore worktrees.json.backup.20260305`
- **THEN** system restores from specified backup file

### Requirement: conflict resolution
The system SHALL handle conflicts during repair.

#### Scenario: task already exists
- **WHEN** attempting to register a task that already exists
- **THEN** system skips registration and reports conflict

#### Scenario: branch assignment conflict
- **WHEN** worktree already has a different branch in git than in worktrees.json
- **THEN** system prompts user to choose which to keep

#### Scenario: Registry write failure
- **WHEN** registry.json cannot be written (permissions, disk full, etc.)
- **THEN** system reports error and does not proceed with repair
