#!/usr/bin/env bash
# Test utilities for bats tests
# This file is loaded by tests that use 'load test_utils'

# Setup environment for tests
setup_test_env() {
  export VIBE_ROOT="${BATS_TEST_DIRNAME}/.."
  export VIBE_MAIN="$VIBE_ROOT"
  export VIBE_SESSION="test-session"

  # Source core libraries (required for alias functions)
  source "$VIBE_ROOT/lib/config.sh"
  source "$VIBE_ROOT/lib/utils.sh"
}

# Create a temporary git repository for testing
create_test_repo() {
  local dir="$1"
  mkdir -p "$dir"
  cd "$dir" || return 1
  git init
  git config user.email "test@test.com"
  git config user.name "Test User"
  echo "# Test" > README.md
  git add README.md
  git commit -m "Initial commit"
}

# Cleanup test repository
cleanup_test_repo() {
  local dir="$1"
  cd "$VIBE_ROOT" || true
  [[ -d "$dir" ]] && rm -rf "$dir"
}

# Skip test if command not available
skip_if_missing() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    skip "$cmd not available"
  fi
}

# Assert file exists
assert_file_exists() {
  local file="$1"
  [[ -f "$file" ]] || { echo "Expected file to exist: $file"; return 1; }
}

# Assert directory exists
assert_dir_exists() {
  local dir="$1"
  [[ -d "$dir" ]] || { echo "Expected directory to exist: $dir"; return 1; }
}

# Assert file contains
assert_file_contains() {
  local file="$1" pattern="$2"
  [[ -f "$file" ]] || { echo "File not found: $file"; return 1; }
  grep -q "$pattern" "$file" || { echo "Expected '$pattern' in $file"; return 1; }
}
