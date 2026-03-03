#!/usr/bin/env bats
# tests/test_v3_core.bats - Unit tests for v3 core layer
# TEMPORARILY SKIPPED: These tests require Zsh-specific features

# NOTE: v3 core layer uses Zsh-specific features (typeset -A, associative arrays)
# Bats runs tests with Bash, which doesn't support these features.
# TODO: Migrate to Zsh-native testing framework or refactor for Bash compatibility

@test "SKIP: v3 core tests (requires Zsh)" {
  skip "v3 tests require Zsh-specific features not supported in Bash"
}
