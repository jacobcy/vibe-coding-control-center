---
document_type: standard
title: Skill Execution Trace Standard
status: proposed
scope: skill-execution-traceability
authority:
  - skill-durable-marker-requirement
  - skill-marker-type-selection
  - skill-output-contract
author: Claude Opus 4.6
created: 2026-06-23
related_docs:
  - docs/standards/v3/skill-standard.md
  - docs/standards/v3/skill-trigger-standard.md
  - docs/standards/v3/audit-evidence-model-standard.md
issues:
  - 2950
---

# Skill Execution Trace Standard

This standard defines minimum traceability requirements for repo-local Vibe skills.
It specifies the required durable marker types, fields, and output contracts for
each skill execution, ensuring that skill decisions and outputs can be audited
and traced.

This standard references the `skill_ref` evidence model defined in
[audit-evidence-model-standard.md](audit-evidence-model-standard.md) §4.6.

## 1. Scope

This standard covers:

- Minimum durable marker requirements for skill executions
- Marker type selection by skill category
- Required fields for each execution marker
- Output contracts for skill execution summaries
- Anti-patterns to avoid in skill execution trace

This standard does not define:

- Skill routing or trigger conditions (see `skill-trigger-standard.md`)
- Skill source structure or runtime linking (see `skill-standard.md`)
- Evidence bundle schema for audits (see `audit-evidence-model-standard.md`)

## 2. Minimum Durable Marker Requirement

**Hard Requirement**: Each skill execution must produce at least one durable marker.

A durable marker is one of:

1. **Flow timeline event**: Recorded via flow state transitions
2. **Handoff artifact**: Written via `vibe3 handoff append`
3. **GitHub issue/PR comment**: Posted via `gh issue comment` or `gh pr comment`

**Rationale**: Skills make decisions and produce outputs that affect downstream
flows. Without durable markers, these decisions cannot be traced, audited, or
recovered after session termination.

**Finding Classification**: An execution without any durable marker is itself a
traceability finding. Auditors should flag such executions as potential
governance gaps.

**Exception**: Purely informational queries (e.g., `vibe-skills-manager` listing
installed skills) may produce only stdout output. However, if the query leads
to a state change or decision, a marker must be recorded.

## 3. Marker Type Decision Table

The appropriate marker type depends on the skill category and execution outcome:

| Skill Category | Examples | Primary Marker | Secondary Marker | When to Use |
|---|---|---|---|---|
| **Orchestration** | `vibe-orchestra`, `vibe-roadmap` | Issue comment with `[governance]` marker | Handoff artifact (`--kind note`) | Decisions affecting issue assignment, prioritization, or state transitions |
| **On-site Changes** | `vibe-new`, `vibe-commit`, `vibe-done` | Handoff ref (`--kind milestone` or `--kind note`) | Flow timeline event | Creating branches, commits, PRs, or closing flows |
| **Diagnostic/Review** | `vibe-check`, `vibe-task`, `vibe-skill-audit` | Handoff ref (`--kind audit`) | Issue comment (if findings exist) | Audits, diagnostics, or reviews with actionable findings |
| **Session Handoff** | `vibe-save` | Handoff ref (`--kind note`) | None | Saving session context or recording next steps |

### 3.1 Orchestration Skills

Skills producing orchestration decisions must:

1. Post an issue comment with `[governance]` or `[roadmap decision]` marker
2. Include a structured summary with:
   - Decision made
   - Rationale (brief)
   - Reference to any artifacts (plan_ref, report_ref)
3. Optionally append a handoff artifact for detailed context

**Example**: `vibe-orchestra` decides to prioritize issue #123:
```
[governance] Issue #123 prioritized for current version

- Decision: Move to In-Progress
- Rationale: Dependencies resolved, high priority
- Assigned to: @agent-name
```

### 3.2 On-site Change Skills

Skills producing on-site changes must:

1. Append a handoff ref with appropriate kind (`milestone` for completions, `note` for progress)
2. Record the output artifact ref (e.g., branch name, PR number, commit SHA)
3. Trigger a flow timeline event if applicable

**Example**: `vibe-new` creates a flow:
```bash
vibe3 handoff append "Flow created: branch=task/issue-456, flow=issue-456" --kind milestone
```

### 3.3 Diagnostic/Review Skills

Skills performing audits or diagnostics must:

1. Append a handoff ref with `--kind audit`
2. Post an issue comment if findings require human attention
3. Record all findings with clear severity (MAJOR, MINOR, INFO)

**Example**: `vibe-check` finds stale bindings:
```
[run] Audit complete: 2 findings

- MAJOR: Flow issue-789 has stale worktree binding
- MINOR: Orphaned branch detected

See audit artifact: @audit
```

## 4. Required Fields

Each execution marker must record minimum fields aligned with the `skill_ref`
schema defined in [audit-evidence-model-standard.md](audit-evidence-model-standard.md) §4.6:

| Field | Description | Example |
|---|---|---|
| `skill_name` | Name of the skill | `vibe-new` |
| `skill_path` | File path to SKILL.md | `skills/vibe-new/SKILL.md` |
| `invoked_for` | Input issue/flow/branch | `issue: 456`, `branch: task/issue-456` |
| `output_refs` | Output artifact references | `plan_ref: docs/plans/issue-456-plan.md` |
| `verdict` | Decision status or outcome | `PASS`, `FAIL`, `BLOCKED`, `CLAIMED` |

### 4.1 Field Format

- `skill_name`: Must match the skill directory name under `skills/`
- `skill_path`: Must be a valid path relative to repository root
- `invoked_for`: Must include at least one of `issue_number`, `branch`, or `flow_slug`
- `output_refs`: Must be a list of artifact paths or references
- `verdict`: Must be one of the defined status values

### 4.2 Handoff Ref Format

When using `vibe3 handoff append`, the message should follow this template:

```
<skill_name>: <brief summary>

- invoked_for: <issue/branch>
- output_refs: <artifacts>
- verdict: <status>
```

**Example**:
```bash
vibe3 handoff append "vibe-commit: PR created

- invoked_for: branch=task/issue-456
- output_refs: pr=789
- verdict: DONE" --kind milestone
```

### 4.3 Issue Comment Format

When posting issue comments, the message must:

1. Start with appropriate marker (see §3)
2. Include structured summary with required fields
3. Keep total length under 500 characters for routine updates
4. Reference full artifact for detailed reports

## 5. Output Contract

Skill execution must produce a structured summary that can be:

1. Consumed by downstream agents without parsing unstructured text
2. Traced back to the invoking context (issue, branch, flow)
3. Audited for compliance with this standard

### 5.1 Structured Summary Template

```
<marker> <skill_name>: <one-line outcome>

- Input: <invoked_for>
- Output: <primary artifact>
- Status: <verdict>
- Details: <artifact_ref or brief explanation>
```

### 5.2 Prefer Artifact Refs Over Lengthy Comments

When output is substantial (e.g., audit findings, execution reports):

- Post a brief comment with summary and reference
- Store full output in handoff artifact or file
- Reference the artifact path in the comment

**Anti-pattern**: Posting a 50-line comment with full execution log.

**Preferred**:
```
[run] Execution complete

- Output: docs/reports/issue-456-execution-report.md
- Status: PASS
- Tests: 12 passed, 0 failed
```

## 6. Anti-Patterns

The following patterns violate this standard and must be avoided:

### 6.1 Cross-Worktree Read/Write

- **Violation**: Reading or writing handoff/flow data from a different worktree
- **Correct**: All handoff operations must be within the current worktree context
- **Rationale**: Worktrees represent isolated execution contexts; cross-worktree
  access breaks this isolation

### 6.2 Handoff as Truth Source

- **Violation**: Using handoff artifacts to override GitHub, git, or database facts
- **Correct**: Handoff is derived/auxiliary evidence, not authoritative source
- **Rationale**: GitHub issue state, git commits, and database records are
  authoritative; handoff is for communication and recovery

### 6.3 Noisy Comments

- **Violation**: Posting comments with only "done", "completed", or no actionable info
- **Correct**: Include structured summary with required fields (§4)
- **Rationale**: Comments without context waste reviewer time and provide no
  traceability value

### 6.4 Stdout as Durable Marker

- **Violation**: Relying solely on stdout output as execution trace
- **Correct**: Use handoff append or issue comment for durable markers
- **Rationale**: Stdout is ephemeral and lost after session termination

### 6.5 Missing Marker for State Changes

- **Violation**: Changing issue state, creating branch, or posting PR without marker
- **Correct**: Always record a marker for state-changing operations
- **Rationale**: State changes are key decision points that require traceability

## 7. Scope Coverage

This standard applies to:

- All repo-local skills under `skills/vibe-*/SKILL.md`
- Skill execution entry points (the primary execution flow defined in SKILL.md)
- Both user-invoked and automatically-triggered skill executions

This standard does not apply to:

- Third-party skills installed via `npx skills`
- Plugin-based capabilities (Claude Code plugins)
- OpenSpec `opsx-*` workflows

## 8. Change Checklist

When creating or modifying a skill, verify:

1. [ ] Does the skill produce at least one durable marker per execution?
2. [ ] Is the marker type appropriate for the skill category (see §3)?
3. [ ] Does the marker include all required fields (see §4)?
4. [ ] Is the output summary structured and consumable?
5. [ ] Are artifact refs used instead of lengthy comments for substantial output?
6. [ ] Does the skill avoid all anti-patterns listed in §6?
7. [ ] Does the SKILL.md `Execution Flow` section document the trace steps?

## 9. Compliance

Existing skills that do not comply with this standard:

- Are not required to immediately update
- Should be migrated through separate follow-up issues
- New skill executions should follow this standard

New skills or skill modifications:

- Must comply with this standard
- Will be audited against this checklist in review

## 10. Related Standards

- [skill-standard.md](skill-standard.md): Skill source and boundary definitions
- [skill-trigger-standard.md](skill-trigger-standard.md): Skill routing and triggers
- [audit-evidence-model-standard.md](audit-evidence-model-standard.md): Evidence bundle schema
