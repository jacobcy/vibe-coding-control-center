# Config Directory Structure

This directory contains all configuration files for the Vibe Coding Control Center project, organized by governance layer.

## Directory Structure

```
config/
├── shell/              # V2 shell compatibility layer
│   ├── aliases.sh      # Shell aliases
│   ├── loader.sh       # Shell initialization
│   └── keys.template.env # API key template
├── prompts/            # V3 prompt templates
│   └── prompts.yaml    # Prompt templates for agents
├── v3/                 # V3 runtime configuration
│   ├── settings.yaml       # Main configuration file
│   ├── registry.yaml       # Configuration governance registry
│   ├── loc_limits.yaml     # LOC limits configuration
│   ├── models.json         # Agent preset mappings
│   ├── skills.json         # Skills configuration
│   ├── prompt-recipes.yaml # Prompt recipes
│   └── dependencies.toml   # Shell dependencies
├── aliases.sh          # [DEPRECATED] Use config/shell/aliases.sh
├── loader.sh           # [DEPRECATED] Use config/shell/loader.sh
├── keys.template.env   # [DEPRECATED] Use config/shell/keys.template.env
├── prompts.yaml        # [DEPRECATED] Use config/prompts/prompts.yaml
├── settings.yaml       # [DEPRECATED] Use config/v3/settings.yaml
├── loc_limits.yaml     # [DEPRECATED] Use config/v3/loc_limits.yaml
└── ...
```

## Governance Layers

### 1. Shell Layer (`config/shell/`)

Files for V2 shell compatibility:
- **aliases.sh**: Shell aliases for common tasks
- **loader.sh**: Shell initialization script
- **keys.template.env**: Template for API keys

### 2. Prompts Layer (`config/prompts/`)

Prompt templates for V3 agents:
- **prompts.yaml**: Defines prompt templates for plan, run, review, and orchestra agents

### 3. V3 Runtime Layer (`config/v3/`)

Core runtime configuration:
- **settings.yaml**: Main configuration file (flow, AI, review, plan, run, orchestra)
- **registry.yaml**: Configuration governance registry (tracks schema, consumers, tests)
- **loc_limits.yaml**: LOC limits for code and documentation
- **models.json**: Agent preset to backend/model mappings
- **skills.json**: Skills configuration
- **prompt-recipes.yaml**: Prompt recipe definitions
- **dependencies.toml**: Shell dependency declarations

## Configuration Registry

The `config/v3/registry.yaml` file tracks:
- **Source files**: Where each config block is defined
- **Schema**: Python class that validates the config
- **Consumers**: Code that depends on this config
- **Tests**: Test files that verify this config
- **Status**: active, deprecated, or dead

## Migration Status

**Current Phase**: Migration with backward compatibility

Old paths still work but are deprecated:
- `config/settings.yaml` → `config/v3/settings.yaml`
- `config/prompts.yaml` → `config/prompts/prompts.yaml`
- `config/loc_limits.yaml` → `config/v3/loc_limits.yaml`
- `config/aliases.sh` → `config/shell/aliases.sh`
- `config/loader.sh` → `config/shell/loader.sh`
- `config/keys.template.env` → `config/shell/keys.template.env`

Loaders will try new paths first and fall back to old paths with deprecation warnings.

## Configuration Loading

Configuration is loaded in this order:
1. `.vibe/config.yaml` (project-specific override)
2. `config/v3/settings.yaml` (new default)
3. `config/settings.yaml` (deprecated fallback)
4. `~/.vibe/config.yaml` (global config)

See `src/vibe3/config/loader.py` for implementation details.