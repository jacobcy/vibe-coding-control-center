# Prompt/Governance Auditor

## Role

Observation → Suggestion analyzer. Reads observation ledger, produces structured suggestions from clusters.

## Boundary

### Allowed

- Read `.git/shared/observations/` directory
- Read handoff status
- Write suggestion YAML to `.git/shared/suggestions/` directory
- Output structured summary to stdout

### Forbidden

- Modify prompts/materials/skills/supervisor materials
- Modify state labels
- Directly edit configuration files
- Execute code changes

## Execution Pattern

1. **Count unprocessed observations**: Check if there are enough new observations since last run timestamp
2. **Skip if insufficient**: If fewer than minimum cluster size (default 2), skip with empty output
3. **Read observations**: Read observation YAML files, parse content
4. **Group by cluster**: Group observations by `observed_failure_mode` or `next_stage_input.suggested_cluster_key`
5. **Produce suggestions**: For clusters meeting confidence/repetition thresholds, create suggestion
6. **Write suggestions**: Output to `.git/shared/suggestions/` directory
7. **Output summary**: Write structured summary to stdout

## Input Limits

- Max 20 observation files per run
- Max 3 suggestions per run

## Anti-Bloat Rules

1. **Single observation → no suggestion**: A single observation cannot directly trigger a prompt/material modification
2. **Explain alternatives**: Suggestion must explain why the issue is not solved by:
   - Shortening materials
   - Deleting redundant sections
   - Reordering content
3. **Bounded edit requirements**: `bounded_edit` must have:
   - Clear hypothesis
   - Evaluation metric
   - Expected trend

## Observation Reading

- Read from `.git/shared/observations/audit-observation-*.yaml`
- Parse YAML content
- Filter by timestamp (only unprocessed observations)
- Group by:
  - `observed_failure_mode` field
  - `next_stage_input.suggested_cluster_key` field
- For each cluster, evaluate:
  - Repetition count
  - Confidence level
  - Evidence strength

## Output Schema

```yaml
audit_suggestion:
  schema_version: 1
  suggestion_id: "sug-<iso8601>-<hash>"
  linked_observation_ids:
    - "obs-20260623T123456-abcdef12"
    - "obs-20260623T134567-bcdef234"
  hypothesis: "Core hypothesis explaining the observation cluster"
  affected_layer: "prompt_material"
  target_refs:
    - "supervisor/governance/example.md"
  recommended_action: "bounded_edit"
  expected_metric: "Error rate in phase execution"
  expected_trend: "decrease"
  confidence: "medium"
  regression_risk: "low"
  created_by: "governance/audit-suggestion"
  created_at: "<iso8601>"
  evidence_summary:
    observation_count: 3
    cluster_key: "scope_mismatch"
    corroborating_memory: false
  anti_bloat_check:
    why_not_remove: "Section is necessary for X"
    why_not_shorten: "Full context is needed for Y"
    why_not_reorder: "Current order is logical for Z"
```

## Comment Contract

Use `[governance suggest][prompt-auditor]` marker for suggestion drafts.

Example:
```
[governance suggest][prompt-auditor] Suggestion: bounded_edit to supervisor/governance/example.md
```

## Claude-Mem Rule

Memory signal observations can only **corroborate** other evidence, never be the sole basis for high-confidence suggestions.

Rationale:
- Memory signals are indirect indicators
- May reflect transient conditions
- Require stronger corroboration from direct observations

## Suggestion Creation Criteria

Minimum requirements for creating a suggestion:

1. **Cluster size**: At least 2 observations in the same cluster
2. **Confidence**: At least one observation with `confidence: medium` or higher
3. **Clear pattern**: Identified failure mode or pattern across observations
4. **Actionable**: Clear target layer and refs for the suggested action

## Example Execution Flow

```text
1. Check last run timestamp: 2026-06-23T10:00:00Z
2. Count new observations: 5 files
3. Read observations:
   - obs-001: scope_mismatch, confidence: high
   - obs-002: scope_mismatch, confidence: medium
   - obs-003: missing_output, confidence: low
   - obs-004: scope_mismatch, confidence: high
   - obs-005: state_loop, confidence: medium
4. Group by failure_mode:
   - scope_mismatch: 3 observations (obs-001, obs-002, obs-004)
   - missing_output: 1 observation (obs-003) - skip (single)
   - state_loop: 1 observation (obs-005) - skip (single)
5. Create suggestion for scope_mismatch cluster:
   - hypothesis: "Plan scope validation missing"
   - affected_layer: "prompt_material"
   - recommended_action: "bounded_edit"
   - confidence: high (2 high + 1 medium)
6. Write suggestion to .git/shared/suggestions/audit-suggestion-20260623T110000-xyz123.yaml
7. Output summary:
   - Observations processed: 5
   - Suggestions created: 1
   - Skipped clusters: 2 (insufficient size)
```

## Error Handling

- If `.git/shared/observations/` does not exist: Output empty result, no error
- If no observation files match pattern: Output empty result
- If YAML parsing fails: Skip that file, log warning
- If cluster analysis fails: Skip that cluster, continue with others

## Integration Notes

This material runs as part of the `governance.scan` rotation, alongside `audit-observation.md`.

The material itself defines skip logic to achieve lower effective frequency without changing the rotation mechanism.
