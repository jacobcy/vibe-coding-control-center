---
description: Gather graphify/mem-search/ADR/spec/exa context before specify (ephemeral evidence, not a handoff artifact)
---

# explore (before specify)

Gather context for the feature about to be specified. The feature description
is the user's `/speckit-specify` argument (available in session context).

**Output is ephemeral evidence** for spec writing — NOT a handoff artifact.
No `explore_ref` is written; the handoff starting point remains `@spec`.

## Gather (five sources, degrade gracefully)

For each source: if the tool is unavailable or returns nothing useful, emit a
one-line limitation note and continue. Do NOT fail the hook — specify must
still proceed even when every tool is absent.

### 1. Code background (graphify)

- `graphify query "<feature description>"` — BFS over the code knowledge graph;
  returns relevant modules, community structure, god nodes.
- For a specific module of interest: `graphify explain "<NodeName>"` — the
  node's calls/uses/methods (more precise than `query` for understanding one
  component).
- Note: `graphify path "<A>" "<B>"` requires exact node names and is unreliable
  for ad-hoc concepts; prefer `query` + `explain`.
- Skip with a note if `graphify-out/` is absent or graphify CLI unavailable.

### 2. Development history (mem-search, 3-layer progressive disclosure)

Use the claude-mem `mem-search` skill: `/claude-mem:mem-search` in Claude Code
or `$claude-mem:mem-search` in Codex. There is NO `claude-memory` CLI — the
skill wraps the MCP search tools. Follow
the 3-layer workflow to keep token cost low:

1. `search` with the feature description → compact index (IDs + titles,
   ~50-100 tokens/result)
2. Review the index; pick 2-3 relevant IDs; optionally `timeline(anchor=<ID>)`
   for surrounding context
3. `get_observations([IDs])` — fetch full details ONLY for the filtered IDs

Surface prior decisions, related past work, and pitfalls. Skip with a note if
mem-search / claude-mem is unavailable.

### 3. Decision context (ADR)

- Scan `docs/decisions/` for accepted ADRs whose frontmatter `scope` glob
  plausibly matches the feature's touch points; surface each match's
  `decides` summary.
- Lightweight frontmatter scan — reference the `vibe-adr-recall` skill's
  approach, do not reimplement its full reconciliation logic.

### 4. Prior art / dedup (existing specs)

- Scan `.specify/specs/*/spec.md` for related features (avoid duplicating an
  in-progress or already-specified feature).

### 5. External prior art (exa, optional)

- When the problem domain is unfamiliar or the feature resembles a known
  external pattern, use the Exa MCP web search capability for how others
  solved similar problems (best practices, prior art). In Codex the tool is
  `mcp__exa_search__web_search_exa`; use the tool name exposed by the current
  host rather than assuming a Claude command name.
- Skip if exa is unavailable, or when sources 1-4 already give enough context.

## Output (in-session, ephemeral)

Emit a single structured block for the specify agent to consume when writing
`spec.md`. Keep it concise — this is evidence, not a spec draft:

```markdown
## Explore Findings (ephemeral evidence)

### Code background
<graphify query/explain summary: key modules / communities / connections, or "skipped: ...">

### Development history
<mem-search hits: prior decisions / pitfalls (3-layer filtered), or "skipped: ...">

### Decision context (ADRs)
<relevant accepted ADRs + their `decides`, or "none matched">

### Prior specs
<related existing specs, or "none">

### External prior art
<exa findings: external best practices / prior art, or "skipped: ...">

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
- Aligns with constitution II (SSOT — reference graphify/mem-search/ADR, do not
  reimplement) and IV (Bridge — reuse existing tools, Skill-First).
