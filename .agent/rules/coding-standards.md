# Coding Standards

## Shell Scripting (Zsh)
- **Shebang**: Always use `#!/bin/zsh` or `#!/usr/bin/env zsh`.
- **Safety**: Always use `set -e` (e from error) at the start of scripts.
- **Variables**: Use `${VAR}` syntax for variable expansion.
- **Functions**: Use `function_name() { ... }` syntax.
- **Conditionals**: Use `[[ ... ]]` for tests.
- **Indentation**: 2 spaces.

## Naming Conventions
- **Variables**: `UPPER_CASE` for globals/constants, `lower_case` for locals.
- **Functions**: `snake_case` (e.g., `install_package`).
- **Files**: `snake_case.sh` for scripts.

## Error Handling
- **Trap**: Use `trap` to catch errors and cleanup.
- **Output**: Print clear error messages to stderr: `echo "Error: ..." >&2`.

## Documentation
- All functions must have a header comment explaining purpose, inputs, and outputs.
- Complex logic must be commented.

## Static Analysis (Quality Assurance)
- **Tool**: [ShellCheck](https://github.com/koalaman/shellcheck)
- **Requirement**: All scripts must pass `shellcheck` before submission.
- **Usage**:
  ```bash
  # Check all scripts
  find . -name "*.sh" -not -path "./lib/shunit2/*" -exec shellcheck {} +
  ```
- **Directives**: Use `# shellcheck disable=SCxxxx` only when necessary and with a comment explaining why.
