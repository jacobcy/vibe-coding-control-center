# vibe-explore

Project-owned spec-kit extension that gathers context **before** specify,
feeding the interactive spec-writing phase (#3327).

## What it does

Registers a mandatory `before_specify` hook that gathers five context sources
as **ephemeral evidence** for spec writing:

| Source              | Tool                                  | Provides                       |
|---------------------|---------------------------------------|--------------------------------|
| Code background     | `graphify query` / `graphify explain` | Modules, communities, connections |
| Development history | `/mem-search` (3-layer)               | Prior decisions, pitfalls      |
| Decision context    | `docs/decisions/` ADR frontmatter scan| Accepted decisions, scope      |
| Prior specs         | `.specify/specs/*/spec.md` scan       | Related features, dedup        |
| External prior art  | `exa web_search` (optional)           | External best practices        |

Each source degrades gracefully — a missing tool yields a one-line limitation
note, never a hook failure.

## Why

Constitution convention **Explore Before Spec**: non-trivial features benefit
from relevant code background and development history before specification.
The interactive specify agent gathers context via tools (per the automation
directive — automation does not pre-inject context; agents gather it
themselves via graphify/mem-search/exa).

## Non-goal

- Output is NOT a handoff artifact. No `explore_ref`. The handoff starting
  point remains `@spec`.
- Does not create the spec directory (`specify` core owns that).

## Files

- `extension.yml` — manifest + mandatory `before_specify` hook.
- `commands/explore.md` — the gather command (skill markdown, agent-executed;
  no bash adapter needed — the agent calls graphify/mem-search/exa directly).

## Relationship to other extensions

- **Additive** to `superspec` and `vibe-spec-bridge`: it is the only
  `before_specify` hook; the other extensions declare `after_*` / `before_implement`.
- Complementary to `vibe-spec-bridge`: explore gathers context upstream,
  `vibe-spec-bridge` publishes the resulting `spec.md` downstream.

## Tests

`tests/vibe3/extensions/test_vibe_explore.py` validates extension metadata,
hook registration (mandatory + additive), the no-handoff invariant, and the
graceful-degradation contract.
