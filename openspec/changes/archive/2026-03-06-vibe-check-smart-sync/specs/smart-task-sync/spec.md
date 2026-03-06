## ADDED Requirements

### Requirement: PR merged detection
System SHALL detect when a PR associated with a task has been merged.

#### Scenario: Single task with merged PR
- **WHEN** a task in "in_progress" status has an associated branch with a merged PR
- **THEN** system SHALL suggest marking the task as "completed"

#### Scenario: Multi-task worktree with merged PR
- **WHEN** a worktree contains multiple tasks and its branch has a merged PR
- **THEN** system SHALL analyze PR content to determine which tasks are completed

#### Scenario: Task without PR
- **WHEN** a task in "in_progress" status has no associated PR
- **THEN** system SHALL skip PR-based completion check

### Requirement: Intelligent task completion analysis
System SHALL use AI (Subagent) to analyze PR content and determine task completion.

#### Scenario: High confidence completion
- **WHEN** Subagent analysis returns confidence score > 0.8
- **THEN** system SHALL automatically suggest marking task as completed

#### Scenario: Medium confidence completion
- **WHEN** Subagent analysis returns confidence score between 0.5 and 0.8
- **THEN** system SHALL prompt user to choose: deep code analysis, manual selection, or skip

#### Scenario: Low confidence completion
- **WHEN** Subagent analysis returns confidence score < 0.5
- **THEN** system SHALL skip the task without suggestion

### Requirement: User confirmation before status update
System SHALL require user confirmation before updating task status.

#### Scenario: User confirms completion
- **WHEN** system displays completion suggestions and user confirms
- **THEN** system SHALL execute `vibe task update <task-id> --status completed`

#### Scenario: User rejects completion
- **WHEN** system displays completion suggestions and user rejects
- **THEN** system SHALL NOT update task status

### Requirement: Graceful degradation without gh
System SHALL continue operation when `gh` CLI is unavailable.

#### Scenario: gh not installed
- **WHEN** `gh` command is not found
- **THEN** system SHALL skip PR-based checks and continue with static checks

#### Scenario: gh not authenticated
- **WHEN** `gh` is installed but not authenticated
- **THEN** system SHALL display warning and skip PR-based checks

### Requirement: Real-time PR data query
System SHALL query PR data in real-time using `gh` command.

#### Scenario: Fetch merged PR list
- **WHEN** system needs to check for merged PRs
- **THEN** system SHALL execute `gh pr list --state merged --limit 10 --json number,headRefName,title,mergedAt`

#### Scenario: Fetch PR details
- **WHEN** system needs detailed PR information
- **THEN** system SHALL execute `gh pr view <branch> --json number,title,body,comments,commits`
