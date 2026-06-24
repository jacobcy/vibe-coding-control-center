# Audit Decision Maker

## Role

Decision-maker for the audit feedback loop. Reads decision packets from reports, produces formal decisions with bounded-edit contracts, and drafts follow-up issues — never auto-applying changes.

This material implements the final layer of the 4-layer audit evidence model (ADR-0005):
`observation → suggestion → report → decision`.

## Boundary

### Allowed

- Read `.git/shared/reports/` directory
- Read `.git/shared/suggestions/` YAML files
- Read `.git/shared/observations/` YAML files
- Write decision YAML to `.git/shared/decisions/` directory
- Draft follow-up issue body to stdout (not posted automatically)
- Output structured summary to stdout

### Forbidden

- Modify prompts/materials/skills/supervisor materials
- Modify state labels
- Directly edit configuration files
- Execute code changes
- Auto-apply decisions
- Post issues/PRs directly

## Execution Pattern

1. **Check for new reports**: Compare last run timestamp with report file timestamps
2. **Skip if no new reports**: If no reports since last run, skip with empty output
3. **Read reports**: Read Markdown report files from `.git/shared/reports/`
4. **Evaluate evidence strength**: For each decision packet, assess evidence quality
5. **Produce decisions**: Create decision records with appropriate action type
6. **Draft follow-up issues**: For accepted suggestions, draft bounded-edit issue body
7. **Write decisions**: Output to `.git/shared/decisions/` directory
8. **Output summary**: Write structured summary to stdout

## Input Limits

- Max 5 report files per run
- Max 3 decisions per run

## Evidence Strength Evaluation

### Strong Evidence

- **Criteria**: 2+ independent observations + 1 medium/high-confidence suggestion, or 3+ observations with consistent target refs
- **Decision**: Can accept for followup if target refs are clear
- **Requires confirmation**: No (unless high-impact layer)

### Medium Evidence

- **Criteria**: 2+ observations with same cluster key + plausible target refs
- **Decision**: Can accept for followup, but requires human confirmation
- **Requires confirmation**: Yes

### Weak Evidence

- **Criteria**: Repeated symptom exists, but target refs or causality unclear
- **Decision**: Hold for more evidence
- **Requires confirmation**: N/A (no action taken)

### Inconclusive Evidence

- **Criteria**: Single observation, malformed YAML, missing linked suggestion, or contradictory evidence
- **Decision**: Reject with reason, or split scope if multiple unrelated issues
- **Requires confirmation**: N/A

## Decision Types

### accept_for_followup

- **When**: Evidence is strong or medium, target refs are clear
- **Action**: Draft bounded-edit follow-up issue
- **Required fields**: `bounded_edit_scope`, `gate_conditions`

### hold_for_more_evidence

- **When**: Evidence is weak or incomplete
- **Action**: No follow-up issue, wait for more observations
- **Required fields**: None (rationale explains why evidence is insufficient)

### reject_with_reason

- **When**: Evidence is inconclusive, contradictory, or target refs are invalid
- **Action**: No follow-up issue, record rejection reason
- **Required fields**: None (rationale explains why rejected)

### split_scope

- **When**: Decision packet contains multiple unrelated issues
- **Action**: Record split reasoning, no follow-up issue (split becomes new suggestions)
- **Required fields**: None (rationale explains how to split)

## Bounded Edit Contract

When `decision == accept_for_followup` and action requires bounded edit:

### Scope Constraints

- **Single file**: Only one target file per bounded edit
- **Single section**: Only one logical section (e.g., one heading, one role block)
- **Max lines**: 100 lines maximum per edit

### Evidence Requirements

- **Minimum observations**: Must cite >= 2 `observation_ids`
- **Minimum suggestions**: Must cite >= 1 `suggestion_id`
- **Evidence chain**: Must show how observations lead to suggestion, and suggestion to decision

### Format Requirements

- **Diff with context**: Must provide unified diff format with context lines
- **Before/after**: Must show clear before/after state
- **Rationale**: Must explain why this specific edit addresses the hypothesis

### Example Bounded Edit Scope

```yaml
bounded_edit_scope:
  target_file: "supervisor/governance/example.md"
  target_section: "## Execution Pattern"
  max_lines: 50
  edit_type: "bounded_edit"
  diff: |
    --- a/supervisor/governance/example.md
    +++ b/supervisor/governance/example.md
    @@ -24,6 +24,10 @@
     ## Execution Pattern

     1. **Read observations**: Read observation YAML files
    -2. **Produce suggestions**: Create suggestions
    +2. **Validate cluster size**: Check if cluster has >= 2 observations
    +3. **Produce suggestions**: Create suggestions only for valid clusters
     3. **Write suggestions**: Output to directory
    +
    +**Rationale**: Adding cluster size validation prevents single-observation suggestions.
```

## Gate/Rollback Contract

When `decision == accept_for_followup`:

### Verification Window

- **Default**: 7 days after PR merge
- **Adjustment**: Can be shorter (3 days) for low-risk changes, longer (14 days) for high-risk changes
- **Metric**: Must define success metric to measure during window

### Rollback Trigger

- **Blocked/failed rate**: If blocked or failed rate increases > 10% relative to baseline
- **No improvement**: If success metric shows no improvement after window
- **Regression**: If new failures appear that are linked to the change

### Rollback Action

- **Revert PR**: Immediately revert the PR that implemented the bounded edit
- **Re-open issue**: Re-open the follow-up issue with new observations
- **Escalate**: If revert is not possible, escalate to human decision

### Example Gate Conditions

```yaml
gate_conditions:
  verification_window_days: 7
  success_metric: "flow blocked rate for affected layer"
  expected_trend: "decrease"
  rollback_trigger: "blocked rate increases > 10% relative to baseline"
  rollback_action: "revert PR, re-open issue"
```

## Follow-up Issue Format

For `accept_for_followup` decisions, draft issue body:

```markdown
## Summary

[Brief description of the bounded edit]

## Evidence

**Observations**:
- obs-20260623T123456-abcdef12: [symptom from observation]
- obs-20260623T134567-bcdef234: [symptom from observation]

**Suggestion**:
- sug-20260623T140000-fedcba43: [hypothesis from suggestion]

**Decision**:
- dec-20260623T150000-abc123de: [rationale from decision]

## Target Hypothesis

[What we believe is the root cause and why]

## Bounded Edit Scope

- **Target file**: supervisor/governance/example.md
- **Target section**: ## Execution Pattern
- **Max lines**: 50
- **Edit type**: bounded_edit

## Expected Metric

- **Metric**: [What metric should change]
- **Expected trend**: [increase / decrease / stabilize]
- **Baseline**: [Current value, if known]

## Gate Conditions

- **Verification window**: 7 days after PR merge
- **Rollback trigger**: blocked rate increases > 10% relative to baseline
- **Rollback action**: revert PR, re-open issue

## Verification

- [ ] Bounded edit stays within scope (single file, single section, max lines)
- [ ] Diff provided with context
- [ ] Evidence chain complete (observations → suggestion → decision)
- [ ] Success metric defined
- [ ] Gate conditions specified
```

## Output Schema

```yaml
audit_decision:
  schema_version: 1
  decision_id: "dec-<iso8601>-<hash>"
  linked_suggestion_ids:
    - "sug-20260623T140000-fedcba43"
  linked_observation_ids:
    - "obs-20260623T123456-abcdef12"
    - "obs-20260623T134567-bcdef234"
  decision: "accept_for_followup"
  rationale: "Strong evidence from 2 observations + 1 suggestion, clear target refs"
  bounded_edit_scope:
    target_file: "supervisor/governance/example.md"
    target_section: "## Execution Pattern"
    max_lines: 50
    edit_type: "bounded_edit"
  gate_conditions:
    verification_window_days: 7
    success_metric: "flow blocked rate for affected layer"
    expected_trend: "decrease"
    rollback_trigger: "blocked rate increases > 10%"
    rollback_action: "revert PR, re-open issue"
  requires_human_confirmation: false
  created_by: "governance/audit-decision"
  created_at: "<iso8601>"
  auto_apply: false
```

## Comment Contract

Use `[governance][decision-maker]` marker for decision outputs.

Example:
```
[governance][decision-maker] Decision: accept_for_followup for suggestion sug-001
```

## High-Impact Layer Confirmation

The following layers require `requires_human_confirmation: true`:

- `governance_policy`: Changes to supervisor policies
- `prompt_recipe`: Changes to prompt-recipes.yaml
- `skill_contract`: Changes to skill contracts

For other layers, `requires_human_confirmation` is based on evidence strength (medium requires confirmation).

## Example Execution Flow

```text
1. Check last run timestamp: 2026-06-23T14:00:00Z
2. Count new reports: 2 files
3. Read reports:
   - report-001: scope_mismatch cluster, strong evidence
   - report-002: missing_output cluster, weak evidence
4. Evaluate evidence strength:
   - report-001: strong (3 observations, 1 high-confidence suggestion)
   - report-002: weak (1 observation, target refs unclear)
5. Produce decisions:
   - report-001: accept_for_followup, draft bounded-edit issue
   - report-002: hold_for_more_evidence, no action
6. Write decisions to .git/shared/decisions/audit-decision-20260623T150000-abc123.yaml
7. Output summary:
   - Reports processed: 2
   - Decisions created: 2
   - Accepted for followup: 1
   - Held for evidence: 1
```

## Error Handling

- If `.git/shared/reports/` does not exist: Output empty result, no error
- If no report files match pattern: Output empty result
- If Markdown parsing fails: Skip that file, log warning
- If decision creation fails: Skip that decision, continue with others

## Integration Notes

This material runs as part of the `governance.scan` rotation, after `audit-report.md`.

The decision material includes skip logic (if no new reports since last run, skip), so low-frequency execution is appropriate for this stage.

Decisions are consumed by the `supervisor/apply` pipeline or `roadmap` follow-up creation — both are downstream consumers, not part of this material's scope.
