# Contract: ADR Recall Frontmatter

## Schema extension

```yaml
decides: "<one concise sentence naming the decision object and binding constraint>"
scope:
  - "<repository-relative exact path or glob>"
```

## `decides`

- Names the decision object.
- States the binding constraint with terms such as must, must not, only, or equivalent precise wording.
- Remains concise enough for metadata scanning.
- Does not copy the ADR rationale or implementation details.

Weak or missing wording is a conservative candidate flag; the agent reads the body rather than silently dismissing the ADR.

## `scope`

- Uses repository-relative paths/globs.
- Represents code, policy, prompt, or other repository material actually governed by the decision; it is not limited to Python.
- Is a relevance signal, not an authorization boundary.
- A zero-match pattern is a metadata-health warning, not proof that the decision is irrelevant.

## Supersede contract

A successor records how each affected predecessor scope is handled:

```yaml
scope_disposition:
  - scope: "src/vibe3/domain/**"
    action: carry | replace | retire
    reason: "<why>"
```

The successor does not need to contain a strict superset of predecessor scope. Narrowing and retirement are valid when explicit.

## Source-of-truth rule

ADR files own these fields. `INDEX.md` may link IDs/titles/status for discovery but does not duplicate `decides` or `scope`.
