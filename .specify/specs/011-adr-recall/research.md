# Research: Low-Code ADR Recall

## Decision 1 - Use a canonical project skill, not a runtime command

**Decision**: implement `skills/vibe-adr-recall/SKILL.md` and expose it through the existing `vibe-*` skill installation path.

**Why**: relevance and constraint interpretation are agent reasoning tasks at the current ADR scale. A Python command would either duplicate that reasoning poorly or become a thin wrapper around Markdown scanning.

**Rejected**:

- `vibe3 adr recall`: premature runtime/API surface.
- an integration-specific `.claude/skills/adr-recall`: not canonical across supported agents and not matched by the current project skill linker.
- a mandatory spec-kit extension package: larger lifecycle/registration surface than the plan template and workflow gate require.

## Decision 2 - Integrate directly with spec-kit plan artifacts

**Decision**: put the artifact schema in `.specify/templates/plan-template.md` and strengthen the existing `review-plan` gate message.

**Why**: the user needs ADR consideration visible during planning. A template field is durable, reviewable, and generated at the right point.

## Decision 3 - Use planned paths at plan time and actual paths at review time

**Decision**: planner records intended paths from the issue/spec/plan; reviewer uses merge-base diff evidence.

**Why**: before implementation, `inspect base` can only show existing branch differences and cannot prove future files. Conflating the two creates false certainty.

## Decision 4 - Candidate relevance is semantic OR scope

**Decision**: either signal includes a candidate; metadata weakness also includes conservatively.

**Why**: an intersection misses new files, renamed modules, cross-cutting policy changes, and stale scopes. The agent resolves ambiguity after reading candidate bodies.

## Decision 5 - Frontmatter is truth; INDEX is discovery

**Decision**: store `decides` and `scope` in ADR frontmatter only. Do not duplicate `decides` into `INDEX.md`.

**Why**: duplicated summaries drift. A bounded `rg` scan over ADR frontmatter is cheap at current scale.

## Decision 6 - Bounded dismissal audit

**Decision**: explain dismissal only for candidates, not every accepted ADR.

**Why**: metadata scanning is linear regardless; exhaustive negative prose adds O(N) plan noise without improving review. Zero-candidate plans record signals and metadata flags instead.

## Decision 7 - Review uses existing verdict and no-op behavior

**Decision**: reviewer records findings/verdict and advances state only when allowed. Existing post-execution no-op enforcement handles unchanged state.

**Why**: FailedGate is driven by error-log severity thresholds and is unrelated to ADR compliance. Adding another runtime gate violates the low-code boundary.

## Decision 8 - Supersede by disposition, not scope superset

**Decision**: a successor declares predecessor scopes as carried, replaced, or retired.

**Why**: valid decisions may narrow or retire scope. A strict superset rule would reject legitimate architecture simplification.

## Decision 9 - Explicit code threshold

**Decision**: code retrieval is reconsidered only when accepted ADR count exceeds 20 or at least 10 reviewed plans show measured recall errors.

**Why**: this makes “future scale” auditable and prevents an implementation from appearing merely because code feels more systematic.
