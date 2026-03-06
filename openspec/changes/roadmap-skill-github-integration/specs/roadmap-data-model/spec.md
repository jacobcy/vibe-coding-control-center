## ADDED Requirements

### Requirement: Roadmap item has bucket field
Each roadmap item SHALL have a `bucket` field with values: now, next, later, blocked, exploration.

#### Scenario: Default bucket
- **WHEN** new item is created without explicit bucket
- **THEN** system defaults bucket to "next"

### Requirement: Roadmap item has source metadata
Each roadmap item SHALL track its origin source.

#### Scenario: GitHub source
- **WHEN** item is created from GitHub issue
- **THEN** system stores provider (github), repo, issue_number, issue_node_id

#### Scenario: Linear source
- **WHEN** item is created from Linear issue
- **THEN** system stores provider (linear), workspace, issue_id

#### Scenario: Local JSON source
- **WHEN** item is created from local JSON
- **THEN** system stores provider (json), file_path

### Requirement: Roadmap item can reference task
Items in "Now" bucket SHALL optionally reference an executed local task.

#### Scenario: Bind task to roadmap item
- **WHEN** user binds a task to roadmap item in Now bucket
- **THEN** system stores task_id in task_ref field

### Requirement: Roadmap item has priority scoring
Each roadmap item SHALL have a priority_score for sorting.

#### Scenario: Calculate priority
- **WHEN** item is added with impact, urgency, cost, dependencies
- **THEN** system calculates priority_score using weighted formula
