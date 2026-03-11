# Task Registry Audit Specification

## ADDED Requirements

### Requirement: Multi-source task registration audit
The system SHALL provide a comprehensive audit of task registration completeness across multiple sources including branches, PRs, and OpenSpec changes.

#### Scenario: Audit with data quality issues
- **WHEN** user runs `vibe task audit` with worktrees containing null branch fields
- **THEN** system detects all data quality issues and reports them before proceeding to task audit

#### Scenario: Audit across all sources
- **WHEN** user runs `vibe task audit`
- **THEN** system performs three-phase audit:
  1. Data quality check (null branch fields)
  2. Deterministic audit (branch → task, OpenSpec → registry)
  3. Heuristic audit (PR → task, optional)

### Requirement: Data quality validation
The system SHALL validate data quality in worktrees.json before performing task registration checks.

#### Scenario: Detect null branch fields
- **WHEN** audit discovers worktrees with `branch: null`
- **THEN** system reports each affected worktree with its worktree_name and suggests repair

#### Scenario: Automatic branch detection
- **WHEN** user runs `vibe task audit --fix-branches`
- **THEN** system queries git for actual branch of each worktree and updates worktrees.json

### Requirement: Branch-to-task registration check
The system SHALL verify that all active branches have corresponding tasks registered in registry.json.

#### Scenario: Detect unregistered branch tasks
- **WHEN** audit finds a branch matching task naming pattern (YYYY-MM-DD-slug) but no task in registry
- **THEN** system reports the branch name and suggests registering the task

#### Scenario: Match branch names to task IDs
- **WHEN** branch name contains a task ID or slug
- **THEN** system attempts to match it to existing tasks in registry

### Requirement: OpenSpec changes synchronization check
The system SHALL verify that all OpenSpec changes have corresponding tasks in registry.json.

#### Scenario: Detect unsynced OpenSpec changes
- **WHEN** audit finds OpenSpec changes not present in registry
- **THEN** system reports each change name and suggests running `vibe task sync`

#### Scenario: Compare change names to task IDs
- **WHEN** OpenSpec change exists at `openspec/changes/<change-name>/`
- **THEN** system checks if registry contains task with matching ID or slug

### Requirement: PR-to-task association detection
The system SHALL identify tasks that may have been completed by merged PRs but not registered.

#### Scenario: Detect PR with unregistered tasks
- **WHEN** audit analyzes a merged PR and finds task references in:
  - Branch name
  - Commit messages
  - PR description
- **THEN** system reports the PR number and detected task IDs with confidence level

#### Scenario: Confidence-based filtering
- **WHEN** PR task detection returns results
- **THEN** system classifies each detection as:
  - High confidence (>0.8): Exact task ID match
  - Medium confidence (0.5-0.8): Partial match or slug match
  - Low confidence (<0.5): Fuzzy match, excluded from results

### Requirement: Audit result summary
The system SHALL provide a comprehensive summary of all audit findings.

#### Scenario: Display audit report
- **WHEN** audit completes
- **THEN** system displays categorized results:
  - Data quality issues
  - Unregistered branch tasks
  - Unsynced OpenSpec changes
  - PR-detected tasks (if enabled)

#### Scenario: Suggest repair actions
- **WHEN** audit finds issues
- **THEN** system provides actionable repair commands for each category

### Requirement: Selective audit modes
The system SHALL support running specific audit phases independently.

#### Scenario: Run only data quality check
- **WHEN** user runs `vibe task audit --check-branches`
- **THEN** system only validates branch data quality without checking task registration

#### Scenario: Run only OpenSpec check
- **WHEN** user runs `vibe task audit --check-openspec`
- **THEN** system only checks OpenSpec synchronization without other audit phases

#### Scenario: Run PR detection
- **WHEN** user runs `vibe task audit --check-prs`
- **THEN** system analyzes recent merged PRs for unregistered tasks

### Requirement: Graceful degradation
The system SHALL continue audit even when some data sources are unavailable.

#### Scenario: gh CLI unavailable
- **WHEN** audit runs but gh CLI is not available
- **THEN** system skips PR detection phase and continues with other checks

#### Scenario: No OpenSpec directory
- **WHEN** openspec/changes/ directory does not exist
- **THEN** system skips OpenSpec check and continues with other phases
