# Vibe Coding Control Center - Command Structure

## Overview

The Vibe Coding Control Center has been restructured to provide a cleaner architecture with better separation of concerns and improved command handling.

## Command Mapping

The system now uses a Git-style command structure where the main `vibe` command delegates to specific `vibe-*` subcommands located in the `bin/` directory.

### Main Command: `vibe`

The main `vibe` command serves as a dispatcher and interactive control center:

- **Interactive mode**: Running `vibe` without arguments launches the interactive menu
- **Command mode**: `vibe [command] [options]` executes specific commands

### Available Commands

| Command | Purpose | Location |
|---------|---------|----------|
| `vibe` | Interactive menu mode | Dispatcher (`bin/vibe` -> `scripts/vibecoding.sh`) |
| `vibe chat` | 快速启动 AI 工具（交互或快速问答） | `bin/vibe-chat` |
| `vibe config` | Manage Vibe Coding configuration | `bin/vibe-config` |
| `vibe equip` | Install/update AI tools | `bin/vibe-equip` |
| `vibe env` | Environment and key management | `bin/vibe-env` |
| `vibe init` | Initialize new project | `bin/vibe-init` |
| `vibe doctor` | System health check (includes diagnostics) | `bin/vibe-doctor` |
| `vibe flow` | Feature development workflow | `bin/vibe-flow` |
| `vibe help` | Show help information | Built into dispatcher (`bin/vibe`) |
| `vibe -h`, `vibe --help` | Show help information | Built into dispatcher (`bin/vibe`) |

## Directory Structure

```
vibe-coding-control-center/
├── bin/                        # Command dispatchers
│   ├── vibe                  # Main dispatcher (Git-style command handling)
│   ├── vibe-chat             # AI chat command
│   ├── vibe-config           # Configuration management command
│   ├── vibe-equip            # Tool installation/update command
│   ├── vibe-env              # Environment management command
│   ├── vibe-init             # Project initialization command
│   ├── vibe-doctor           # System health check command
│   ├── vibe-flow             # Feature workflow command
│   └── vibe-help             # Help command
├── scripts/                   # Implementation scripts
│   ├── vibecoding.sh        # Main control center (now modular)
│   ├── env-manager.sh       # Environment management
│   ├── tdd-init.sh          # TDD initialization
│   └── backup-project.sh    # Backup utilities
├── lib/                      # Shared libraries
│   ├── utils.sh             # Core utilities
│   ├── config.sh            # Configuration management
│   ├── core_commands.sh     # Shared command functions
│   ├── i18n.sh             # Internationalization
│   ├── cache.sh            # Caching mechanisms
│   ├── error_handling.sh   # Error management
│   ├── agents.sh           # Agent management
│   └── init_project.sh     # Project initialization
└── install/                 # Installation scripts
    ├── install-claude.sh    # Claude CLI installation
    ├── install-opencode.sh  # OpenCode CLI installation
    └── init-project.sh      # Project scaffolding
```

## Benefits of This Architecture

1. **Modular Design**: Commands are now self-contained, making maintenance easier
2. **Consistent Interface**: All commands provide help via `-h/--help`
3. **Better Separation**: Each command handles its own logic independently
4. **Scalability**: Easy to add new commands by creating new `vibe-*` scripts
5. **Reduced Coupling**: The main script is less burdened with individual command logic
6. **Improved Testing**: Individual commands can be tested separately

## Command Implementation Details

### Main Dispatcher (`bin/vibe`)

- Handles command routing
- Implements `vibe help` and `vibe -h/--help`
- Maintains backward compatibility with interactive mode
- Follows Git-style subcommand pattern

### Subcommand Scripts

Each subcommand script in `bin/vibe-*`:

- Loads required utility libraries from `lib/`
- Implements specific functionality
- Provides its own help via `-h/--help`
- Can be run independently if needed

### Library Modules

New modular approach with:

- `lib/core_commands.sh` - Shared functions extracted from main script
- Proper dependency loading in each module
- Clear separation between utilities, business logic and UI

## Usage Examples

```bash
# Interactive mode (traditional)
vibe

# New command-based usage
vibe equip              # Install/update tools
vibe chat               # Start AI chat (interactive)
vibe chat "question"    # Quick Q&A (non-interactive)
vibe config             # Manage configuration
vibe init               # Initialize project
vibe env                # Check environment
vibe doctor             # Run system health check (includes diagnostics)
vibe flow start feature # Start feature workflow
vibe flow test          # Initialize TDD test

# Help
vibe help               # General help
vibe help equip         # Help for specific command
vibe -h                 # Alternative help
vibe equip -h           # Help for specific command
```

## Migration Notes

- Existing `vibe` interactive functionality remains unchanged
- All previous command-line options continue to work
- New command-based interface provides additional flexibility
- Subcommands are now more maintainable and testable

## Command Resolution & Fallback

The `vibe` command is a shell function (defined in `config/aliases.sh`) that intelligently resolves which executable to run. This ensures that you always use the most appropriate version of Vibe for your current context.

### Resolution Order
1. **Local Installation** (`./bin/vibe`): Prioritized to support development on specific branches or local overrides.
2. **Git Root Installation** (`<git-root>/bin/vibe`): Prioritized if you are in a subdirectory of a Vibe-enabled project.
3. **Global Installation** (`$VIBE_ROOT/bin/vibe`): The stable, globally installed version.

### Fallback Mechanism
If a command is executed using the Local or Git Root installation but fails with an "Unknown subcommand" error (e.g., when running a new command like `vibe flow rotate` inside an old branch that lacks it), the system automatically falls back to the Global Installation.

This ensures that new global features are available even when working in older branches that haven't been updated yet.
