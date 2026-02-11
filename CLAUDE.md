# Project Context: Vibe Coding Control Center

## Project Overview
Vibe Coding Control Center is a collection of scripts designed to manage and configure AI development tools (Claude Code, OpenCode, etc.) with an emphasis on developer productivity and ease of use. The project provides a unified interface for initializing projects, managing AI tools, and configuring development environments.

## Constitution & Principles
This project operates under the **Vibe Coding Constitution** defined in [SOUL.md](SOUL.md). All development activities, including AI-assisted coding, follows the principles outlined in that document.

## Build & Test Commands
- Build: `./scripts/vibecoding.sh` (starts the main control center)
- Dev Setup: `./install/install-claude.sh` (sets up Claude Code environment)
- Initialize Project: `./install/init-project.sh [project-name]`
- Diagnostics: `./scripts/vibecoding.sh` → Diagnostics option
- Quick Start: `./scripts/vibecoding.sh` → Equip → Install/Update Tools

## Tech Stack
- **Primary Language**: Zsh scripting
- **Environment**: Unix/Linux/macOS
- **Configuration**: Environment variables and shell aliasing
- **Patterns**: Modular scripts with shared utilities, menu-driven interfaces
- **Standards**: Secure coding practices, input validation, error handling

## Project Structure
- `scripts/vibecoding.sh`: Main control center with menu interface (entry point)
- `install/init-project.sh`: Project initialization script with Cursor rules and CLAUDE.md template
- `install/install-claude.sh`: Claude Code installation and setup
- `install/install-opencode.sh`: OpenCode installation and setup
- `docs/usage_advice.md`: Usage guidelines and best practices
- `SOUL.md`: Core principles and constitutional rules (referenced by all contributors)
- `rules.md`: Behavior rules (Behavioral laws)
- `MEMORY.md`: Cumulative record of key decisions and context
- `TASK.md`: High-level project tasks and history
- `WORKFLOW.md`: Documentation of project-level workflows
- `AGENT.md`: Agent persona and role definitions
- `lib/`: Library directory
  - `utils.sh`: Enhanced shared utility functions (security, validation, logging)
- `config/`: Configuration directory
  - `aliases.sh`: Command aliases for quick access (with dynamic path resolution)
  - `keys.env`: Environment variables and API keys (local, not tracked)
  - `keys.template.env`: Template for API keys (tracked)
- `tests/`: Test scripts
  - `test_new_features.sh`: Test version detection and update features
  - `test_status_display.sh`: Test status display functionality

## Security Features
- **Input validation**: All user inputs are validated to prevent injection attacks
- **Path validation**: Protection against directory traversal attacks
- **Secure file operations**: Functions for safe file copying and writing
- **Environment validation**: Checks for command availability and directory permissions
- **Safe user interaction**: Secure prompting and confirmation functions
- **Error handling**: Comprehensive error handling with secure logging

## Coding Standards
Adherence to the principles outlined in [SOUL.md](SOUL.md) is mandatory. Specific technical standards include:
- Use modular, well-commented zsh scripts with portable shell practices where possible
- Follow consistent color scheme for user feedback (defined in utils.sh)
- **Language Protocol**:
  - Think in English.
  - **Always respond to the user and generate reports in Chinese.**
- **File Protocol**:
  - Root directory uppercase files (e.g., `SOUL.md`, `TASK.md`) are for AI context.
  - `docs/` directory is for human-readable documentation.
  - Audit status is tracked in `docs/audits/`.
- Implement error handling with `set -e` for fail-fast behavior
- Separate common functions to `lib/utils.sh` for reusability
- Use clear variable naming with descriptive function names
- Include detailed comments explaining complex operations
- Implement security validations for all user inputs and file operations
- Use readonly variables for constants and security parameters
- **Temporary files**: Always place in `temp/` directory (already ignored by git)

## Key Features
- Menu-driven interface for ease of use (vibecoding.sh)
- Automatic configuration of AI tools with MCP support
- Diagnostic capabilities for environment troubleshooting
- Secure handling of API keys through templated config
- Project initialization with best practices and Cursor rules
- Unified command aliases for quick access (`c`, `ca`, `cp`, `cr`, `o`, `oa`, `vibe`)
- MCP (Model Context Protocol) integration for web search and GitHub access
- Enhanced security with input validation and secure file operations

## Security Notes
- API keys are stored in `config/keys.env` (not tracked by git) and referenced via MCP config
- Template file `keys.template.env` is tracked but contains placeholder values
- Keys file is excluded from git via .gitignore
- Template provided for easy setup without exposing credentials
- All user inputs are validated to prevent injection attacks
- Path traversal protection prevents unauthorized directory access
- Secure file operations validate paths and permissions before operations

## Development Guidelines
Following the principles in [SOUL.md](SOUL.md) is essential. Specific guidelines:
- Always source `lib/utils.sh` for shared functions (logging, validation, security helpers)
- Follow consistent color coding pattern (defined in utils.sh)
- Use the logging functions: `log_info`, `log_warn`, `log_error`, `log_step`, `log_success`, `log_critical`
- Validate all user inputs using `validate_input`, `validate_path`, `validate_filename`
- Use secure file operations: `secure_copy`, `secure_write_file`, `secure_append_file`
- Implement error handling with proper cleanup using `handle_error` trap
- Maintain backward compatibility when modifying core functions
- Update `usage_advice.md` when introducing new features
- Use `set -e` at the beginning of scripts for fail-fast behavior
- Follow modular design principles: separate concerns into different files
- Always use `validate_path` before performing file operations
- Use `prompt_user` and `confirm_action` for secure user interactions
- **Temporary files**: Always place in `temp/` directory (already in `.gitignore`).

## Common Tasks & Commands
- Add new MCP server: Modify MCP configuration in install script
- Update aliases: Modify `config/aliases.sh` and re-source your shell
- Add new utility function: Add to `lib/utils.sh` and source from other scripts
- Initialize new project: Use `./install/init-project.sh [project-name]` or `ignition` alias
- Install/update tools: Use `./scripts/vibecoding.sh` → Equip option or `vibe` alias
 - Run diagnostics: Use `./scripts/vibecoding.sh` → Doctor option
- Validate security: Use the validation functions from utils.sh
- Run tests: `./tests/test_new_features.sh` or `./tests/test_status_display.sh`

## Important Variables
## Linked Docs
- [SOUL.md](SOUL.md)
- [MEMORY.md](MEMORY.md)
- [TASK.md](TASK.md)
- [WORKFLOW.md](WORKFLOW.md)
- [AGENT.md](AGENT.md)
- [RULES.md](RULES.md) (Wait, I should check if it's RULES.md or rules.md in the code)
- `SHELL_RC`: Points to the zsh configuration file (`.zshrc`)
- Constants in `lib/utils.sh` for security parameters (MAX_PATH_LENGTH, MAX_INPUT_LENGTH, etc.)

## Troubleshooting
- If aliases aren't working: Run `source ~/.zshrc` (or appropriate shell config)
- If API keys aren't loading: Check that `keys.env` is properly filled out and sourced
- If MCP services aren't working: Verify that API keys in config are valid
- For script-specific errors: Use `zsh -x scriptname.sh` for detailed execution trace
- For security validation errors: Check the input validation functions in `lib/utils.sh`
- If security functions fail: Verify that `lib/utils.sh` is properly sourced in your scripts
