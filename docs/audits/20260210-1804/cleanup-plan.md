# Cleanup Plan - 20260210-1804

## Priority 1: Documentation Cleanup (Low Risk)
- **Goal**: declutter the root directory and organize technical specs.
- [ ] Create `docs/tech/`, `docs/archive/`, `docs/specs/`.
- [ ] Move `COMMAND_STRUCTURE.md` to `docs/tech/`.
- [ ] Move `UPGRADE_FEATURES.md` to `docs/archive/`.
- [ ] Move PRDs and Test Plans from `docs/` to `docs/specs/`.
- [ ] Update `README.md` and `CLAUDE.md` links.

## Priority 2: Configuration & Path Alignment (Medium Risk)
- **Goal**: Consistent branding and path usage.
- [ ] Update `lib/config.sh` to prefer `~/.vibe/config.toml` over `~/.codex/config.toml`.
- [ ] Ensure all `bin/vibe-*` shims use `VIBE_HOME` consistently.

## Priority 3: Code De-duplication (Medium Risk)
- **Goal**: Reduce maintenance overhead.
- [ ] Modify `bin/vibe` to source help text exclusively from `docs/vibe-help.txt`.

## Priority 4: Test Suite Expansion (Low Risk)
- **Goal**: Increase coverage.
- [ ] Update `tests/test_integrity.sh` to include all shims in `bin/`.
- [ ] Fix any failing tests discovered during cleanup.

## Priority 5: Workspace Hygiene
- [ ] Run `scripts/cleanup.sh` to remove legacy artifacts (`tmpvibe-*`, `varfolder*`).
