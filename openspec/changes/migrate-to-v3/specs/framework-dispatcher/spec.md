# framework-dispatcher Delta Specification

## MODIFIED Requirements

### Requirement: 智能需求分析
The system SHALL analyze user requests to determine request characteristics for framework matching AND integrate with the control plane for unified routing.

#### Scenario: Analyze request complexity
- **WHEN** user submits a request like "帮我修个 bug" or "设计一个新系统"
- **THEN** system analyzes complexity (simple/medium/complex), type (feature/bug/refactor), scope (single/cross-module)

#### Scenario: Detect uncertainty level
- **WHEN** user request is vague like "帮我做点东西"
- **THEN** system detects high uncertainty and prepares clarification questions

#### Scenario: Route through control plane
- **WHEN** framework is selected
- **THEN** system uses control plane's capability registry to invoke the selected framework

### Requirement: 历史 Pattern 匹配
The system SHALL match current request against historical patterns in task.md AND utilize the capability registry for pattern storage.

#### Scenario: High confidence match
- **WHEN** current request has similar characteristics to a completed task in task.md
- **THEN** system returns high confidence with recommended framework

#### Scenario: No historical match
- **WHEN** no similar task exists in task.md
- **THEN** system returns low confidence and falls back to default recommendation

#### Scenario: Store pattern in registry
- **WHEN** framework selection is recorded
- **THEN** system stores the pattern in capability registry for future reference

### Requirement: 置信度驱动决策
The system SHALL make routing decisions based on confidence level AND report decisions to the control plane.

#### Scenario: Auto-select (high confidence)
- **WHEN** confidence is high (>80%)
- **THEN** system automatically selects framework without user interaction

#### Scenario: Confirm recommendation (medium confidence)
- **WHEN** confidence is medium (50-80%)
- **THEN** system recommends framework and asks for confirmation

#### Scenario: Ask user (low confidence)
- **WHEN** confidence is low (<50%)
- **THEN** system presents options and asks user to choose

#### Scenario: Report to control plane
- **WHEN** framework selection is made
- **THEN** system notifies control plane of the selection for lifecycle management

### Requirement: 无感自动选择
The system SHALL provide seamless framework selection when confidence is high AND integrate with lifecycle hooks.

#### Scenario: Seamless entry to Superpower
- **WHEN** request is simple bug fix with historical pattern matching Superpower
- **THEN** system enters Superpower workflow without prompting user

#### Scenario: Seamless entry to OpenSpec
- **WHEN** request is complex feature with historical pattern matching OpenSpec
- **THEN** system enters OpenSpec workflow without prompting user

#### Scenario: Execute lifecycle hooks
- **WHEN** framework is selected
- **THEN** system executes before_framework hooks, framework logic, and after_framework hooks

### Requirement: 记忆更新
The system SHALL record framework selection to task.md AND sync with capability registry.

#### Scenario: Record new selection
- **WHEN** framework is selected (auto or manual)
- **THEN** system writes `framework: <name>` to task.md under the feature entry

#### Scenario: Update existing selection
- **WHEN** framework selection changes for an existing feature
- **THEN** system updates the framework field in task.md

#### Scenario: Sync with registry
- **WHEN** framework selection is recorded
- **THEN** system updates capability registry with the selection pattern
