# Prompt Config Unification Design

## Goal

Unify prompt configuration so that prompt material sources live in prompt
configuration rather than runtime settings, while preserving the current
behavior of manager, governance, and supervisor handoff with minimal breakage.

## Problem

The current system mixes three kinds of prompt decisions across YAML and
Python:

- `config/prompts/prompts.yaml` owns prompt text and template bodies.
- `config/prompts/prompt-recipes.yaml` owns section ordering for some roles.
- `config/v3/settings.yaml` still owns prompt material paths such as
  `assignee_dispatch.supervisor_file`, `governance.supervisor_file(s)`, and
  `supervisor_handoff.supervisor_file`.

That split causes several structural issues:

1. Prompt structure is not fully declarative.
2. Python contains role-specific glue that manually binds section names to
   settings fields.
3. Similar orchestration roles follow different rendering patterns.
4. Settings remain partially responsible for prompt output, which keeps the
   system vulnerable to new dual-source drift.

## Current State

### Manager

- `manager.default` in `config/prompts/prompt-recipes.yaml` chooses sections.
- `src/vibe3/roles/manager.py` manually binds
  `manager.supervisor_content -> config.assignee_dispatch.supervisor_file`.

### Governance

- `src/vibe3/roles/governance.py` builds a `PromptRecipe` in Python.
- `config.governance.supervisor_file(s)` still define the material path.
- `config/prompts/prompts.yaml` decides whether `{supervisor_content}` is
  actually rendered.

### Supervisor handoff

- `src/vibe3/roles/supervisor.py` reuses governance rendering by overriding a
  temporary governance config object.
- `config.supervisor_handoff.supervisor_file` defines the material path.

## Design Principles

1. Prompt text lives only in `config/prompts/prompts.yaml`.
2. Prompt composition and prompt material sources live only in
   `config/prompts/prompt-recipes.yaml`.
3. `config/v3/settings.yaml` keeps runtime behavior only:
   enablement, intervals, agent/backend/model, worktree strategy, labels,
   dry-run flags, and capacity settings.
4. Python should provide generic prompt rendering infrastructure, not
   role-specific prompt wiring.
5. Prefer incremental migration over a large rewrite.

## Proposed Architecture

Use two explicit recipe kinds under the same prompt configuration file.

### Line 1: section recipes

Used by `manager`, `run`, `plan`, and `review`.

Responsibilities:

- Select variant and section order.
- Optionally attach section-level material sources.
- Reuse existing section text stored in `prompts.yaml`.

Example shape:

```yaml
recipes:
  manager.default:
    kind: section_recipe
    variants:
      first.bootstrap:
        sections:
          - key: manager.supervisor_content
            source:
              kind: file
              path: supervisor/manager.md
          - key: manager.target
          - key: manager.quick_commands
      retry.resume:
        sections:
          - key: manager.retry_task
```

### Line 2: template recipes

Used by `governance` and `supervisor_handoff`.

Responsibilities:

- Pick one prompt template from `prompts.yaml`.
- Declare variable sources in configuration.
- Let Python inject runtime providers only for live state values.

Example shape:

```yaml
recipes:
  governance.scan:
    kind: template_recipe
    template_key: orchestra.governance.plan
    variables:
      supervisor_name:
        kind: literal
        value: supervisor/governance/assignee-pool.md
      supervisor_content:
        kind: file
        path: supervisor/governance/assignee-pool.md
      server_status:
        kind: provider
        provider: governance.server_status
```

The two lines share one conceptual rule:

- prompt config declares static material sources
- Python supplies runtime state providers

## Why Two Lines Instead Of One

Manager/run/plan/review already rely on section assembly and should not be
forced into a single-template model. Governance and supervisor handoff already
behave like template rendering with variable binding and should not be forced
through fake section wrappers.

Keeping two recipe kinds gives us:

- one configuration home
- one ownership model
- less Python glue
- minimal behavior churn

without rewriting stable prompt flows.

## Configuration Ownership After Migration

### `config/prompts/prompts.yaml`

Owns:

- prompt bodies
- section text
- template bodies

Does not own:

- file paths for prompt materials
- role variant choice

### `config/prompts/prompt-recipes.yaml`

Owns:

- section order
- template recipe definitions
- static material paths such as supervisor markdown files
- static literals and provider bindings needed for prompt assembly

### `config/v3/settings.yaml`

Owns:

- role execution behavior
- orchestration timing and labels
- backend and model resolution
- worktree and async strategy
- dry-run and enablement flags

Does not own:

- supervisor prompt material paths
- section membership
- prompt variable material sources

## Code Changes

### 1. Extend prompt recipe schema

Update `src/vibe3/prompts/manifest.py` to support:

- `kind: section_recipe | template_recipe`
- section entries that may optionally carry a `source`
- template recipe variable declarations

Compatibility requirement:

- existing `run/plan/review` recipe entries must continue to load unchanged

### 2. Introduce generic prompt source resolution

Add one generic source-binding path in the prompt layer so Python can resolve:

- `file`
- `literal`
- `provider`
- future selector kinds if needed

Goal:

- remove role-specific `manager.supervisor_content` binding code
- avoid config-to-prompt wiring in role modules

### 3. Migrate manager first

Move `assignee_dispatch.supervisor_file` into `manager.default` recipe config.

After migration:

- `src/vibe3/roles/manager.py` should only choose variant and render
- `config/v3/settings.yaml` should no longer contain
  `orchestra.assignee_dispatch.supervisor_file`

### 4. Migrate supervisor handoff second

Give supervisor handoff its own template recipe instead of overriding
governance config in Python.

After migration:

- `src/vibe3/roles/supervisor.py` should render its own recipe directly
- `config/v3/settings.yaml` should no longer contain
  `orchestra.supervisor_handoff.supervisor_file`

### 5. Migrate governance third

Move `governance.supervisor_file(s)` into prompt recipe configuration.

Recommended split:

- prompt recipe owns the material catalog
- Python still owns tick-based selection and runtime snapshot data

This keeps the round-robin behavior without retaining prompt material paths in
runtime settings.

## Migration Strategy

### Phase 1

Schema expansion with backward compatibility. No behavior change.

### Phase 2

Manager migration. This removes the clearest remaining settings-to-prompt
binding and validates the new schema with low blast radius.

### Phase 3

Supervisor handoff migration. This simplifies the most awkward code path by
removing governance config override logic.

### Phase 4

Governance migration. This finishes prompt-source ownership cleanup while
preserving tick-based material rotation in Python.

### Phase 5

Delete deprecated settings fields and legacy compatibility branches after all
consumers and tests are updated.

## Risk Control

To minimize disruption:

- keep current template keys unchanged where possible
- preserve current rendered prompt text during migration
- migrate one role family at a time
- keep old recipe schema readable during the transition
- add explicit tests for prompt provenance and rendered output

Main risk areas:

- recipe schema parser complexity
- accidental prompt text drift
- governance material rotation regressions

## Test Strategy

Add or update tests for:

- manifest parsing of both recipe kinds
- manager bootstrap vs retry prompt output
- supervisor handoff rendering without governance override
- governance material selection across tick counts
- failure modes when recipe sources are missing
- config regression tests proving prompt material paths are no longer in
  `config/v3/settings.yaml`

## Recommendation

Adopt the two-line unified configuration model:

- one prompt configuration home
- two recipe kinds
- zero prompt material path ownership in runtime settings

This gives the codebase a consistent direction toward pure configuration,
removes the most confusing Python glue, and avoids a large destructive rewrite.
