# Tech Debt Audit Report - 20260210-1804

## Architectural Patterns
- **Dispatch System**: Git-style dispatcher (`bin/vibe`) is well-implemented and provides a clean CLI experience.
- **Config Management**: Centralized in `lib/config.sh` using an associative array.
- **Security**: Robust input validation in `lib/utils.sh`. Use of `eval` is largely avoided in primary scripts.

## Identified Technical Debt
1. **Legacy References**: `lib/config.sh` still looks for `~/.codex/config.toml`. This should be migrated to `~/.vibe/config.toml`.
2. **Duplicated Logic**:
   - Help text is duplicated in `bin/vibe` (bash) and `docs/vibe-help.txt`.
   - Versions and status checks are duplicated between `install.sh` and `vibe-diagnostics`.
3. **Hardcoded Defaults**:
   - `ANTHROPIC_BASE_URL` and `ANTHROPIC_MODEL` are hardcoded in `lib/config.sh`.
4. **Zsh Dependency**: Heavy use of Zsh specific features (associative arrays, modifiers). While intentional, it limits portability to bash/dash environments.
5. **Test Incompleteness**:
   - `test_integrity.sh` only checks a subset of files.
   - `test_cli_alignment.sh` misses several subcommands (sync, equip, init).

## Security Gaps
- **Input Sanitization**: Most inputs are validated, but `validate_input` in `lib/utils.sh` might be too restrictive for certain AI prompts (e.g., blocking `;` or `>` in prompt text).
- **Hardcoded Endpoints**: Defaulting to `api.bghunt.cn` is a good "out-of-the-box" experience for some users but should be more explicitly configurable.

## Action Items
1. Update `lib/config.sh` to prefer `~/.vibe/config.toml`.
2. Consolidate help logic into `docs/vibe-help.txt` only.
3. Parameterize default models/endpoints.
4. Expand `test_integrity.sh` to cover all `bin/` and `scripts/`.
