## ADDED Requirements

### Requirement: Execution result write to JSON
The system SHALL write execution results to JSON file at `.agent/execution-results/<task_id>.json`.

#### Scenario: Write successful execution result
- **WHEN** execution command completes successfully
- **THEN** system writes JSON file with task_id, resolved_worktree, resolved_session, executor, and timestamp

#### Scenario: JSON file format validation
- **WHEN** system writes execution result
- **THEN** JSON file MUST be valid JSON with required fields and correct types

### Requirement: Execution result schema
The execution result JSON SHALL include specific fields with defined types.

#### Scenario: Required fields present
- **WHEN** execution result is written
- **THEN** JSON MUST include:
  - `task_id` (string): unique task identifier
  - `resolved_worktree` (string): worktree path or name
  - `resolved_session` (string): tmux session name
  - `executor` (enum): "human" or "openclaw"
  - `timestamp` (ISO 8601 string): execution time

#### Scenario: Reject invalid executor value
- **WHEN** execution result includes executor value other than "human" or "openclaw"
- **THEN** system rejects write and reports validation error

### Requirement: Executor mode detection
The system SHALL detect execution mode (human vs openclaw) based on environment variable.

#### Scenario: Detect human executor
- **WHEN** EXECUTOR environment variable is not set or set to "human"
- **THEN** system writes executor="human" to execution result

#### Scenario: Detect openclaw executor
- **WHEN** EXECUTOR environment variable is set to "openclaw"
- **THEN** system writes executor="openclaw" to execution result

### Requirement: Execution result query API
The system SHALL provide API to query execution results by task_id, worktree, or session.

#### Scenario: Query by task_id
- **WHEN** control plane queries execution result for task_id "abc123"
- **THEN** system returns JSON content from `.agent/execution-results/abc123.json`

#### Scenario: Query by worktree
- **WHEN** control plane queries execution result for worktree "wt-claude-add-user-auth"
- **THEN** system searches all JSON files and returns matching result

#### Scenario: Query by session
- **WHEN** control plane queries execution result for session "claude-add-user-auth"
- **THEN** system searches all JSON files and returns matching result

#### Scenario: Query not found
- **WHEN** control plane queries execution result that doesn't exist
- **THEN** system returns null or empty result with appropriate error code

### Requirement: Execution result update
The system SHALL allow updating execution results when worktree or session changes.

#### Scenario: Update worktree path
- **WHEN** worktree path changes after creation
- **THEN** system updates `resolved_worktree` field in execution result JSON

#### Scenario: Update session name
- **WHEN** session is renamed
- **THEN** system updates `resolved_session` field in execution result JSON

### Requirement: Execution result cleanup
The system SHALL provide ability to clean up execution results for archived tasks.

#### Scenario: Clean up archived task results
- **WHEN** user runs cleanup command for archived tasks
- **THEN** system removes JSON files for tasks with status "archived"

#### Scenario: Preserve active task results
- **WHEN** user runs cleanup command
- **THEN** system MUST NOT remove JSON files for tasks with status other than "archived"

### Requirement: Execution result backup
The system SHALL backup execution results before cleanup for recovery purposes.

#### Scenario: Backup before cleanup
- **WHEN** user runs cleanup command
- **THEN** system creates backup at `.agent/execution-results-backup/<timestamp>/` before deletion

### Requirement: Cross-worktree accessibility
Execution results SHALL be accessible from all worktrees for cross-worktree coordination.

#### Scenario: Access from different worktree
- **WHEN** user in worktree "wt-claude-task-a" queries execution result for task "abc123"
- **THEN** system successfully reads `.agent/execution-results/abc123.json`

#### Scenario: Shared storage location
- **WHEN** execution result is written from any worktree
- **THEN** file is stored in shared location `.agent/execution-results/` relative to main repository
