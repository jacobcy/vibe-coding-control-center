# PR Task Detection Specification

## ADDED Requirements

### Requirement: PR content analysis for task identification
The system SHALL analyze PR content to identify tasks that may have been completed but not registered.

#### Scenario: Analyze merged PR for task references
- **WHEN** user runs PR task detection on a merged PR
- **THEN** system analyzes:
  - PR branch name
  - PR title and description
  - Commit messages
  - PR comments and reviews

#### Scenario: Extract task IDs from branch names
- **WHEN** PR branch name contains a task ID pattern (YYYY-MM-DD-slug)
- **THEN** system extracts the task ID and checks if it exists in registry

#### Scenario: Extract task IDs from commit messages
- **WHEN** commit message contains task reference (e.g., "feat: implement #2026-03-05-feature-a")
- **THEN** system extracts the task ID and adds to detected tasks list

#### Scenario: Parse PR description for task mentions
- **WHEN** PR description mentions completing tasks (e.g., "Completes #task-id" or "Implements task-name")
- **THEN** system extracts task references and adds to detected tasks list

### Requirement: Task matching with confidence scoring
The system SHALL assign confidence scores to detected task associations.

#### Scenario: High confidence exact match
- **WHEN** extracted task ID exactly matches an existing task in registry
- **THEN** system assigns confidence score of 0.9-1.0

#### Scenario: Medium confidence partial match
- **WHEN** branch name or commit contains task slug but not full ID
- **THEN** system assigns confidence score of 0.6-0.8 based on fuzzy matching

#### Scenario: Low confidence fuzzy match
- **WHEN** only keywords or descriptions match without explicit task reference
- **THEN** system assigns confidence score of 0.3-0.5

#### Scenario: Confidence-based filtering
- **WHEN** detection returns results
- **THEN** system excludes tasks with confidence < 0.5 from results

### Requirement: Multi-task PR detection
The system SHALL detect when a single PR completes multiple tasks.

#### Scenario: PR with multiple task references
- **WHEN** PR analysis finds references to multiple task IDs
- **THEN** system reports all detected tasks with individual confidence scores

#### Scenario: Aggregated multi-task report
- **WHEN** a PR completes multiple unregistered tasks
- **THEN** system displays:
  - PR number and title
  - List of detected tasks with confidence scores
  - Source of detection (branch/commit/description)

### Requirement: Batch PR analysis
The system SHALL support analyzing multiple PRs in a single run.

#### Scenario: Analyze recent merged PRs
- **WHEN** user runs `vibe task audit --check-prs`
- **THEN** system analyzes last N merged PRs (default: 50)

#### Scenario: Limit PR analysis scope
- **WHEN** user specifies `--limit 10`
- **THEN** system only analyzes the 10 most recent merged PRs

#### Scenario: Analyze specific PR
- **WHEN** user specifies `--pr 42`
- **THEN** system only analyzes PR #42

### Requirement: PR detection result formatting
The system SHALL present PR detection results in a structured format.

#### Scenario: Display detected tasks by PR
- **WHEN** PR detection completes
- **THEN** system displays results grouped by PR:
  ```
  PR #42: "feat: implement multi-feature"
    ✓ 2026-03-04-feature-a (confidence: 0.92, source: branch name)
    ⚠ 2026-03-04-feature-b (confidence: 0.68, source: commit message)
  ```

#### Scenario: Distinguish registered vs unregistered tasks
- **WHEN** detected task already exists in registry
- **THEN** system marks it as "already registered" and excludes from repair suggestions

#### Scenario: Suggest registration for unregistered tasks
- **WHEN** detected task has high confidence (> 0.8) and not in registry
- **THEN** system suggests registering the task

### Requirement: Integration with task audit
The system SHALL integrate PR detection as an optional phase of task audit.

#### Scenario: PR detection as Phase 3
- **WHEN** user runs `vibe task audit --all` or `--check-prs`
- **THEN** system executes PR detection after Phase 1 (data quality) and Phase 2 (deterministic audit)

#### Scenario: Skip PR detection by default
- **WHEN** user runs `vibe task audit` without PR-related flags
- **THEN** system skips PR detection phase to avoid unnecessary API calls

### Requirement: Graceful handling of PR access issues
The system SHALL handle PR access failures gracefully.

#### Scenario: gh CLI unavailable
- **WHEN** gh CLI is not available or not authenticated
- **THEN** system displays warning and skips PR detection phase

#### Scenario: PR not found
- **WHEN** specified PR number does not exist
- **THEN** system reports error and continues with other PRs (if batch mode)

#### Scenario: Rate limit handling
- **WHEN** GitHub API rate limit is reached
- **THEN** system reports error and suggests waiting before retrying
