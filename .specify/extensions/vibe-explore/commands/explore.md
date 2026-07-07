---
description: Gather graphify/claude-mem/ADR/spec context before specify (ephemeral evidence, not a handoff artifact)
---

# explore (before specify)

Gather context for the feature about to be specified. The feature description
is the user's `/speckit-specify` argument (available in session context).

**Output is ephemeral evidence** for spec writing — NOT a handoff artifact.
No `explore_ref` is written; the handoff starting point remains `@spec`.

## Gather (four sources, degrade gracefully)

For each source: if the tool is unavailable or returns nothing useful, emit a
one-line limitation note and continue. Do NOT fail the hook — specify must
still proceed even when every tool is absent.

### 1. Code background (graphify)

- `graphify query "<feature description>"` — relevant modules, community
  structure, god nodes.
- For likely cross-module impact: `graphify path "<entity A>" "<entity B>"`.
- Skip with a note if `graphify-out/` is absent or graphify CLI unavailable.

### 2. Development history (claude-mem)

- `claude-memory smart search "<feature description>"` — prior decisions,
  related past work, pitfalls.
- Skip with a note if claude-memory is unavailable.

### 3. Decision context (ADR)

- Scan `docs/decisions/` for accepted ADRs whose frontmatter `scope` glob
  plausibly matches the feature's touch points; surface each match's
  `decides` summary.
- This is a lightweight frontmatter scan — reference the `vibe-adr-recall`
  skill's approach, do not reimplement its full reconciliation logic.

### 4. Prior art / dedup (existing specs)

- Scan `.specify/specs/*/spec.md` for related features (avoid duplicating an
  in-progress or already-specified feature).

## Output (in-session, ephemeral)

Emit a single structured block for the specify agent to consume when writing
`spec.md`. Keep it concise — this is evidence, not a spec draft:

```markdown
## Explore Findings (ephemeral evidence)

### Code background
<graphify subgraph summary: key modules / communities / god nodes, or "skipped: ...">

### Development history
<claude-mem hits: prior decisions / pitfalls, or "skipped: ...">

### Decision context (ADRs)
<relevant accepted ADRs + their `decides`, or "none matched">

### Prior specs
<related existing specs, or "none">

### Suggested spec considerations
<2-3 bullets: constraints / risks / prior art the spec should account for>
```

## Contract

- MUST NOT write to handoff (no `explore_ref`). The handoff starting point is
  `@spec`; explore is upstream evidence only.
- MUST NOT create the spec directory or `spec.md` (the `specify` core command
  owns that in its step 3).
- MUST degrade gracefully if any tool is missing — emit a limitation note and
  continue; never fail the hook on tool absence.
- Output is conversation context only; the specify agent folds the relevant
  parts into `spec.md` and the explore block is not persisted.
- Aligns with constitution II (SSOT — reference graphify/memory/ADR, do not
  reimplement) and IV (Bridge — reuse existing tools, Skill-First).
