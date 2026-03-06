## ADDED Requirements

### Requirement: vibe-check-four-phase-workflow
The `vibe check` command SHALL execute a four-phase checking workflow.

#### Scenario: Execute all phases
- **WHEN** user runs `vibe check`
- **THEN** system SHALL execute:
  1. Phase 1: Static checks (existing)
  2. Phase 2: Git status checks (new)
  3. Phase 3: Intelligent analysis (new)
  4. Phase 4: User confirmation and execution (new)

#### Scenario: Phase 1 static checks
- **WHEN** Phase 1 executes
- **THEN** system SHALL perform existing checks: Registry sync, archive completed tasks, detect ghost branches, detect scattered docs

#### Scenario: Phase 2 git status checks
- **WHEN** Phase 2 executes
- **THEN** system SHALL:
  - Query all `in_progress` tasks
  - For each task with a branch, check if PR exists and is merged
  - Collect tasks with merged PRs for Phase 3 analysis

#### Scenario: Phase 3 intelligent analysis
- **WHEN** Phase 3 executes with uncertain tasks
- **THEN** system SHALL:
  - Call Subagent to analyze PR content
  - Calculate confidence scores for each task
  - Classify tasks by confidence level (high/medium/low)

#### Scenario: Phase 4 user confirmation
- **WHEN** Phase 4 executes with completion suggestions
- **THEN** system SHALL:
  - Display suggestions with confidence levels and reasons
  - Prompt user for confirmation
  - Execute status updates upon confirmation

### Requirement: vibe-check-graceful-degradation
The `vibe check` command SHALL gracefully degrade when dependencies are unavailable.

#### Scenario: gh not available
- **WHEN** `gh` command is not found
- **THEN** system SHALL:
  - Display warning message
  - Skip Phase 2 and Phase 3
  - Continue with Phase 1 static checks
  - Exit with success status

#### Scenario: Network error during PR query
- **WHEN** PR query fails due to network error
- **THEN** system SHALL:
  - Display error message
  - Continue with other checks
  - Not fail the entire check

### Requirement: vibe-check-user-choice-for-medium-confidence
The `vibe check` command SHALL allow user to choose handling method for medium-confidence tasks.

#### Scenario: User chooses deep analysis
- **WHEN** system displays medium-confidence tasks and user selects "Deep code analysis"
- **THEN** system SHALL:
  - Call Subagent with code diff analysis
  - Return completion assessment
  - Add to final suggestions

#### Scenario: User chooses manual selection
- **WHEN** user selects "Manual selection"
- **THEN** system SHALL:
  - Display task list with checkboxes
  - Allow user to select which tasks are completed
  - Add selected tasks to final suggestions

#### Scenario: User chooses skip
- **WHEN** user selects "Skip these tasks"
- **THEN** system SHALL:
  - Not include these tasks in final suggestions
  - Continue to Phase 4
