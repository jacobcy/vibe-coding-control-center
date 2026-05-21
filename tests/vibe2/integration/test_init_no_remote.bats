#!/usr/bin/env bats
# Tests for vibe init no-remote / SKIP_LABELS path (Issue #1152)

setup() {
  export REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../../.." && pwd)"
  export VIBE_ROOT="$REPO_ROOT"
  export VIBE_LIB="$REPO_ROOT/lib"
}

@test "vibe init warns and skips labels when no GitHub remote exists" {
  local fixture
  fixture="$(mktemp -d)"
  git -C "$fixture" init >/dev/null 2>&1

  run zsh -c "
    export VIBE_ROOT='$REPO_ROOT'
    export VIBE_LIB='$REPO_ROOT/lib'
    export GREEN='' RED='' YELLOW='' CYAN='' BOLD='' NC=''
    source '$REPO_ROOT/lib/profiles.sh'
    source '$REPO_ROOT/lib/init.sh'
    cd '$fixture'
    vibe_init --profile github-flow --yes 2>&1
  "

  [ "$status" -eq 0 ]
  [[ "$output" =~ "No GitHub remote found" ]]
  [[ "$output" =~ "GitHub labels creation will be skipped" ]]
  [[ "$output" =~ "git remote add origin" ]]
  [[ ! "$output" =~ "Created label:" ]]
}

@test "gh is not invoked in no-remote path" {
  local fixture
  fixture="$(mktemp -d)"
  git -C "$fixture" init >/dev/null 2>&1

  # Create mock gh that logs when called
  local mock_bin
  mock_bin="$(mktemp -d)"
  cat > "$mock_bin/gh" <<'SCRIPT'
#!/bin/bash
echo "gh was called with: $@" >> "$GHCALL_LOG"
exit 0
SCRIPT
  chmod +x "$mock_bin/gh"

  local ghcall_log
  ghcall_log="$(mktemp)"

  run zsh -c "
    export PATH='$mock_bin:'\"\$PATH\"
    export GHCALL_LOG='$ghcall_log'
    export VIBE_ROOT='$REPO_ROOT'
    export VIBE_LIB='$REPO_ROOT/lib'
    export GREEN='' RED='' YELLOW='' CYAN='' BOLD='' NC=''
    source '$REPO_ROOT/lib/profiles.sh'
    source '$REPO_ROOT/lib/init.sh'
    cd '$fixture'
    vibe_init --profile github-flow --yes 2>&1
  "

  [ "$status" -eq 0 ]
  [[ "$output" =~ "No GitHub remote found" ]]
  # The log file should NOT exist (gh was never called)
  [ ! -s "$ghcall_log" ]
}

@test "vibe init fails gracefully in non-git directory" {
  local fixture
  fixture="$(mktemp -d)"
  # No git init here

  run zsh -c "
    export VIBE_ROOT='$REPO_ROOT'
    export VIBE_LIB='$REPO_ROOT/lib'
    export GREEN='' RED='' YELLOW='' CYAN='' BOLD='' NC=''
    source '$REPO_ROOT/lib/profiles.sh'
    source '$REPO_ROOT/lib/init.sh'
    cd '$fixture'
    vibe_init --profile github-flow --yes 2>&1
  "

  [ "$status" -eq 1 ]
  [[ "$output" =~ "Not in a git repository" ]]
  [[ "$output" =~ "Please run this command in a git repository" ]]
}
