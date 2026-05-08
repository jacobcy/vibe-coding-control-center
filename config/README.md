# Config Directory Structure

This directory contains all configuration files for the Vibe Coding Control Center project, organized by governance layer.

## Directory Structure

```
config/
├── shell/              # V2 shell compatibility layer
│   ├── aliases.sh      # Shell aliases
│   ├── loader.sh       # Shell initialization
├── prompts/            # V3 prompt templates
│   ├── prompts.yaml        # Prompt templates for agents
│   └── prompt-recipes.yaml # Prompt recipe definitions
├── v3/                 # V3 runtime configuration
│   ├── settings.yaml       # Main configuration file
│   ├── registry.yaml       # Configuration governance registry
│   ├── loc_limits.yaml     # LOC limits configuration
│   ├── models.json         # Agent preset mappings
│   ├── skills.json         # Skills configuration
│   └── dependencies.toml   # Shell dependencies
├── keys.template.env   # API key template
└── ...
```

## Governance Layers

### 1. Shell Layer (`config/shell/`)

Files for V2 shell compatibility:
- **aliases.sh**: Shell aliases for common tasks
- **loader.sh**: Shell initialization script

### 2. Prompts Layer (`config/prompts/`)

Prompt templates for V3 agents:
- **prompts.yaml**: Defines prompt templates for plan, run, review, and orchestra agents
- **prompt-recipes.yaml**: Prompt recipe definitions for run/plan/review section assembly

### 3. V3 Runtime Layer (`config/v3/`)

Core runtime configuration:
- **settings.yaml**: Main configuration file (flow, AI, review, plan, run, orchestra)
- **registry.yaml**: Configuration governance registry (tracks schema, consumers, tests)
- **loc_limits.yaml**: LOC limits for code and documentation
- **models.json**: Agent preset to backend/model mappings
- **skills.json**: Skills configuration
- **dependencies.toml**: Shell dependency declarations

## Prompt Configuration Boundaries

Prompt configuration has three separate sources of truth:

- `config/v3/settings.yaml`: runtime selectors and execution configuration.
  It owns agent presets, policy/common rule paths, and orchestra template keys
  such as `orchestra.governance.prompt_template`. It does NOT own supervisor
  material paths — those have migrated to `prompt-recipes.yaml`.
- `config/prompts/prompts.yaml`: prompt text and template bodies. It owns
  `agent_prompt.global_notice`, `run.*_task`, `plan.*_task`,
  `review.*_task`, `*.output_format`, manual role prompt strings, and whether
  template variables such as `{supervisor_content}` appear in governance output.
- `config/prompts/prompt-recipes.yaml`: role prompt section ordering and material
  sources. It owns which sections are assembled for each role variant, and where
  supervisor materials come from (`section_recipe` with source declarations or
  `template_recipe` with `material_catalog`).

Key changes after prompt config unification:
- **manager**: supervisor content from `manager.default.first.bootstrap.sections[].source`
- **supervisor_handoff**: supervisor content from `supervisor.handoff.variables.supervisor_content`
- **governance**: supervisor materials from `governance.scan.material_catalog` (round-robin tick selection)
- `settings.yaml` no longer has `assignee_dispatch.supervisor_file`, `supervisor_handoff.supervisor_file`,
  or `governance.supervisor_file(s)` fields.

Do not define prompt text fields in `config/v3/settings.yaml`; loaders fail fast
when those fields appear there to prevent dual sources of truth.

## Configuration Registry

The `config/v3/registry.yaml` file tracks:
- **Source files**: Where each config block is defined
- **Schema**: Python class that validates the config
- **Consumers**: Code that depends on this config
- **Tests**: Test files that verify this config
- **Status**: active, deprecated, or dead

## Migration Status

**Current Phase**: Migrated repository paths

The repository no longer keeps duplicate root-level copies for migrated config:
- `config/v3/settings.yaml`
- `config/prompts/prompts.yaml`
- `config/v3/loc_limits.yaml`
- `config/shell/aliases.sh`
- `config/shell/loader.sh`
- `config/v3/models.json`
- `config/v3/skills.json`
- `config/prompts/prompt-recipes.yaml`
- `config/v3/dependencies.toml`

Some loaders still retain legacy fallback logic for external installs or older
checkouts, but this repository should update only the migrated paths above.

## Configuration Loading

Configuration is loaded in this order:
1. `.vibe/config.yaml` (project-specific override)
2. `config/v3/settings.yaml` (new default)
3. `config/settings.yaml` (legacy fallback for older checkouts)
4. `~/.vibe/config.yaml` (global config)

See `src/vibe3/config/loader.py` for implementation details.
