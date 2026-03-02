## ADDED Requirements

### Requirement: Anti-Pollution Truncation
The system SHALL NOT output large unsanitized command outputs (like `git diff`) directly to the model context. Subagent delegation or truncation commands like `head` or `tail` MUST be used to extract summaries.

#### Scenario: Summarizing large diffs
- **WHEN** user requests a `vibe-commit` command which requires changes context.
- **THEN** system MUST process `git diff` through a truncation strategy or summary rather than raw dumping.

### Requirement: Skill Usage Examples
Critical proprietary skills (vibe-commit, vibe-audit, vibe-orchestrator) SHALL contain properly formulated `input_examples` within their metadata YAML frontmatter.

#### Scenario: Agent routing capability
- **WHEN** routing requests to `vibe-audit` or `vibe-orchestrator`.
- **THEN** agent SHALL use the defined `input_examples` to ensure parameters are correctly parsed according to context limits.

## REMOVED Requirements

### Requirement: Raw diff propagation
**Reason**: Replaced by summary extraction
**Migration**: Use truncation strategies or pipeline summaries inside `vibe-commit` logic avoiding naked `git diff` calls directly injected into Agent prompts.
