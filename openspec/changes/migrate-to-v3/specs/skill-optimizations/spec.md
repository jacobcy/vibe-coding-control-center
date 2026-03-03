# skill-optimizations Delta Specification

## MODIFIED Requirements

### Requirement: Anti-Pollution Truncation
The system SHALL NOT output large unsanitized command outputs (like `git diff`) directly to the model context. Subagent delegation or truncation commands like `head` or `tail` MUST be used to extract summaries AND the system SHALL enforce context budget limits.

#### Scenario: Summarizing large diffs
- **WHEN** user requests a `vibe-commit` command which requires changes context.
- **THEN** system MUST process `git diff` through a truncation strategy or summary rather than raw dumping.

#### Scenario: Context budget enforcement
- **WHEN** command output exceeds configured context budget (default 10KB)
- **THEN** system applies progressive summarization or rejects output with guidance

#### Scenario: Budget-aware routing
- **WHEN** output size approaches budget limit
- **THEN** system routes to subagent for preprocessing before including in context

### Requirement: Skill Usage Examples
Critical proprietary skills (vibe-commit, vibe-audit, vibe-orchestrator) SHALL contain properly formulated `input_examples` within their metadata YAML frontmatter AND demonstrate context-efficient usage patterns.

#### Scenario: Agent routing capability
- **WHEN** routing requests to `vibe-audit` or `vibe-orchestrator`.
- **THEN** agent SHALL use the defined `input_examples` to ensure parameters are correctly parsed according to context limits.

#### Scenario: Context-efficient examples
- **WHEN** skill examples reference large outputs
- **THEN** examples demonstrate truncation or summarization techniques

## ADDED Requirements

### Requirement: 智能摘要
The system SHALL provide intelligent summarization for large command outputs using configurable strategies.

#### Scenario: Diff summarization
- **WHEN** git diff output is large (>100 lines)
- **THEN** system generates summary showing file changes, insertion/deletion counts, and key modifications

#### Scenario: Log summarization
- **WHEN** log output is verbose
- **THEN** system extracts errors, warnings, and key events

#### Scenario: Configurable summarization level
- **WHEN** user sets VIBE_SUMMARY_LEVEL to "detailed"
- **THEN** system provides more verbose summaries than default "concise" mode

### Requirement: 上下文预算管理
The system SHALL track and enforce context budgets to prevent context window pollution.

#### Scenario: Budget tracking
- **WHEN** command outputs are added to context
- **THEN** system tracks cumulative size against budget

#### Scenario: Budget warning
- **WHEN** context usage reaches 80% of budget
- **THEN** system logs warning suggesting summarization

#### Scenario: Budget enforcement
- **WHEN** context usage would exceed budget
- **THEN** system refuses output and suggests alternatives (subagent, file output)
