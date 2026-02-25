# Coding Standards (编码标准)

## Shell Scripts
- Language: Zsh (`#!/usr/bin/env zsh`)
- Use `set -e` in executable scripts for fail-fast
- Source `lib/utils.sh` for shared functions
- Quote all variables: `"$var"` not `$var`

## File Limits
- Single file: ≤ 200 lines
- `lib/` + `bin/` total: ≤ 1,200 lines
- `config/aliases/` total: ≤ 500 lines

## Functions
- Every function must have ≥1 caller (zero dead code)
- Use logging helpers: `log_info`, `log_warn`, `log_error`, `log_step`, `log_success`
- Use `vibe_die` for fatal errors, `vibe_require` for dependency checks
- Use `validate_path` before file operations

## Naming Conventions
- Functions: `snake_case` (e.g., `vibe_flow`, `_flow_start`)
- Internal/private functions: prefix with `_`
- Variables: `UPPER_CASE` for exports, `lower_case` for locals
- Worktrees: `wt-<agent>-<feature>`

## Output
- Think in English
- User-facing output and reports in Chinese
- Use color constants from `utils.sh` for feedback

## Commit Style
- Conventional commits: `feat:`, `fix:`, `refactor:`, `docs:`, `chore:`
- One logical change per commit
