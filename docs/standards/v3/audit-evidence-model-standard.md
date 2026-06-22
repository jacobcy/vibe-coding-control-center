---
document_type: standard
title: Audit Evidence Model Standard
status: proposed
scope: prompt-policy-skill-audit
authority:
  - audit-evidence-schema
  - prompt-policy-skill-audit-boundary
  - source-trust-classification
  - observation-input-contract
author: Codex
created: 2026-06-17
last_updated: 2026-06-17
related_docs:
  - docs/decisions/0005-prompt-policy-skill-audit-evidence-model.md
  - docs/standards/v3/database-schema-standard.md
  - docs/standards/v3/event-driven-standard.md
  - docs/standards/v3/skill-standard.md
  - docs/standards/v3/skill-trigger-standard.md
  - docs/standards/v3/skill-execution-trace-standard.md
  - supervisor/roadmap-common.md
issues:
  - 2947
---

# Audit Evidence Model Standard

This standard defines the reusable evidence model for Prompt/Policy/Skill audit
work. It is the schema-level output for issue #2947.

The model exists to keep audit agents from repeatedly reading unbounded raw
materials such as issue comments, flow timelines, PR bodies, git commits,
rendered prompts, and skill documents. Raw materials must first be captured as
bounded evidence bundles, then distilled into observations, then aggregated into
suggestions, and only then considered for decisions.

## 1. Scope

This standard covers:

- evidence bundle identity and required metadata
- source reference shape for GitHub, flow, handoff, git, prompt, skill, and
  claude-mem inputs
- trust classification and staleness rules
- allowed use of evidence in observation, suggestion, and decision stages
- minimum requirements for future persistent schema

This standard does not define:

- the final SQLite DDL for `audit_observations` or `audit_suggestions`
- the implementation of Observation Collector or Prompt/Governance Auditor
- PR review policy, code audit policy, or prompt rewrite policy

Those details belong to follow-up implementation issues and future schema
standards.

## 2. Audit Pipeline

The audit chain has four semantic stages:

```yaml
raw_evidence:
  produced_by: github | flow_store | git | prompt_renderer | skill_runtime | claude_mem
  consumed_by: observation_collector

observation:
  produced_by: observation_collector
  consumed_by: prompt_governance_auditor

suggestion:
  produced_by: prompt_governance_auditor
  consumed_by: human_or_roadmap_decider

decision:
  produced_by: human_or_roadmap_decider
  consumed_by: supervisor_apply_or_followup_issue
```

Rules:

- A single raw source or single flow may produce observations, not direct prompt
  or policy changes.
- A suggestion must cite observation ids, not only raw evidence refs.
- A decision must cite suggestion ids and observation ids.
- claude-mem evidence may corroborate recurrence, but it is never a standalone
  decision source.

## 3. Evidence Bundle Schema

An evidence bundle is the bounded input object produced before observation. It
must be small enough for audit agents to inspect without reading every linked
raw artifact.

```yaml
evidence_bundle:
  id: string
  schema_version: 1
  created_at: iso8601
  created_by: string
  repo:
    owner: string
    name: string
    local_root: string | null
  collection_context:
    mode: issue | flow | pr | time_window | manual
    source_machine: string | null
    source_db: string | null
    source_commit: string | null
    time_window:
      start: iso8601 | null
      end: iso8601 | null
  primary_subject:
    issue_number: integer | null
    branch: string | null
    pr_number: integer | null
  source_refs:
    github: list[github_ref]
    flow: list[flow_ref]
    handoff: list[handoff_ref]
    git: list[git_ref]
    prompt: list[prompt_ref]
    skill: list[skill_ref]
    memory: list[memory_ref]
  summary:
    symptom: string
    evidence_text: string
    candidate_failure_patterns: list[string]
  trust:
    source_class: authoritative | derived | auxiliary
    freshness: fresh | stale | unknown
    confidence: strong | medium | weak | inconclusive
    limitations: list[string]
```

## 4. Source Reference Shapes

### 4.1 GitHub Reference

```yaml
github_ref:
  kind: issue | issue_comment | pr | pr_comment | review | label
  number: integer
  url: string
  author: string | null
  created_at: iso8601 | null
  marker: string | null
```

Allowed markers include:

- `[governance suggest][roadmap-intake]`
- `[governance suggest][assignee-pool]`
- `[governance decide][assignee-pool]`
- `[roadmap decision]`
- `[decision]`

### 4.2 Flow Reference

```yaml
flow_ref:
  branch: string
  flow_slug: string | null
  event_id: integer | null
  event_type: string | null
  actor: string | null
  created_at: iso8601 | null
  watermark: string
```

The `watermark` must change when the observed flow receives new timeline events,
new refs, PR updates, or relevant prompt hash changes. Observation Collector
uses this value to avoid re-observing unchanged flows.

### 4.3 Handoff Reference

```yaml
handoff_ref:
  branch: string
  kind: plan | report | audit | indicate | verdict | current | other
  artifact_ref: string
  actor: string | null
  created_at: iso8601 | null
```

Handoff refs are audit artifacts, not independent truth sources. When a handoff
claim conflicts with GitHub, git, or flow store facts, the stronger source wins.

### 4.4 Git Reference

```yaml
git_ref:
  kind: commit | diff_range | branch | tag
  ref: string
  base_ref: string | null
  head_ref: string | null
  author: string | null
  committed_at: iso8601 | null
  files_changed: list[string]
```

For review-gap analysis, `base_ref` should identify the last known agent commit
or PR creation point, and `head_ref` should identify the later human-reviewed
or merged state.

### 4.5 Prompt Reference

```yaml
prompt_ref:
  recipe_key: string
  variant: string | null
  rendered_hash: string
  rendered_at: iso8601 | null
  sections:
    - key: string
      source_kind: literal | provider | file | material_catalog
      source_ref: string | null
      size_chars: integer | null
```

Prompt refs must come from dry-run/render provenance, not from static YAML
inspection alone. Static prompt files are source material; rendered prompts are
the audit input that affected an agent.

### 4.6 Skill Reference

```yaml
skill_ref:
  name: string
  path: string
  version_ref: string | null
  invoked_for:
    issue_number: integer | null
    branch: string | null
  output_refs: list[string]
```

Skill refs should point to durable execution evidence such as flow timeline
markers, issue comments, or handoff artifacts. A skill invocation without any
durable marker is itself an audit finding candidate.

### 4.7 Memory Reference

```yaml
memory_ref:
  provider: claude-mem
  query: string
  memory_ids: list[string]
  project: string | null
  platform: string | null
  observed_at: iso8601 | null
  staleness: fresh | stale | unknown
```

Memory refs are auxiliary. They may show recurrence or historical context, but
they do not override repository, GitHub, flow store, or git facts.

## 5. Source Trust Classes

Evidence consumers must classify each bundle:

| Class | Meaning | Examples | Decision Use |
|---|---|---|---|
| authoritative | Direct state or durable source for the audited fact | GitHub issue/PR state, git commits, flow store rows, rendered prompt hash | May support decisions when corroborated |
| derived | Projection or summary derived from authoritative sources | flow timeline projection, handoff artifact, generated report | Useful for observations; verify before high-impact decisions |
| auxiliary | Contextual memory or non-authoritative recall | claude-mem observations, prior session summaries | Corroboration only |

If sources disagree, the bundle must record the disagreement in
`trust.limitations`.

## 6. Observation Input Contract

Observation Collector may consume evidence bundles when all of these are true:

- `schema_version` is recognized.
- `primary_subject` identifies at least one issue, branch, or PR.
- `source_refs` contains at least one authoritative or derived source.
- `summary.evidence_text` is bounded and does not embed entire raw artifacts.
- `trust.limitations` records missing source classes or stale sources.

Observation Collector must not:

- read all historical raw materials for every run
- re-observe an unchanged flow with the same watermark
- emit a suggestion or decision
- modify prompt, policy, skill, issue state, or PR state

## 7. Suggestion Input Contract

Prompt/Governance Auditor may consume observations created from these evidence
bundles. It may sample raw refs only when the observation is unclear.

The auditor must not promote a single-flow observation to a global prompt or
policy change without either:

- repeated observations across independent flows, or
- a strong deterministic contract violation, such as a missing required output
  ref or invalid rendered prompt provenance.

## 8. Completion Criteria For Issue 2947

Issue #2947 is satisfied when:

- this standard defines the reusable evidence bundle schema
- source refs cover GitHub, flow, handoff, git, prompt, skill, and memory inputs
- source trust and staleness rules are explicit
- the model distinguishes evidence used for failure attribution from evidence
  used only for human review or corroboration
- follow-up implementation issues can reuse this schema without re-reading the
  original RFC discussion

Implementation of ledger tables and agent roles is intentionally left to
follow-up issues.
