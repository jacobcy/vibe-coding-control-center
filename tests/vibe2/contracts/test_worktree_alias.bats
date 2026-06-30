#!/usr/bin/env bats

setup() {
  export VIBE_ROOT="$(cd "$BATS_TEST_DIRNAME/../../.." && pwd)"
}

run_zsh_with_timeout() {
  local script="$1"
  run python3 -c '
import subprocess
import sys

try:
    completed = subprocess.run(
        ["zsh", "-c", sys.argv[1]],
        capture_output=True,
        text=True,
        timeout=2,
    )
except subprocess.TimeoutExpired:
    print("timed out", file=sys.stderr)
    sys.exit(124)

sys.stdout.write(completed.stdout)
sys.stderr.write(completed.stderr)
sys.exit(completed.returncode)
' "$script"
}

# Helper to create a temporary bare repo and test commands from within it
run_wt_from_bare_repo() {
  local cmd="$1"
  local tmpdir
  tmpdir="$(mktemp -d)"
  cd "$tmpdir"

  # Create a normal repo first with initial commit, then clone to bare
  git init -b main normal-repo
  cd normal-repo
  echo "initial" > README.md
  git add README.md
  git commit -m "initial commit"
  cd ..
  git clone --bare normal-repo repo.git
  cd repo.git

  run_zsh_with_timeout "source \"$VIBE_ROOT/lib/utils.sh\"; source \"$VIBE_ROOT/lib/alias/worktree.sh\"; $cmd"
  local result_status=$?
  cd "$VIBE_ROOT"
  rm -rf "$tmpdir"
  return $result_status
}

@test "wtrm --help exits without hanging" {
  run_zsh_with_timeout "source \"$VIBE_ROOT/lib/utils.sh\"; source \"$VIBE_ROOT/lib/alias/worktree.sh\"; wtrm --help"

  [ "$status" -eq 0 ]
  [[ "$output" =~ "usage: wtrm [--yes] [--delete-remote]" ]]
}

@test "wtrm rejects extra positional args without hanging" {
  run_zsh_with_timeout "source \"$VIBE_ROOT/lib/utils.sh\"; source \"$VIBE_ROOT/lib/alias/worktree.sh\"; wtrm one two"

  [ "$status" -eq 1 ]
  [[ "$output" =~ "Unexpected argument: two" ]]
}

@test "wt/wtrm --help do not fatal from bare repo root" {
  # Test that wt (no args) works from bare repo root - lists worktrees without fatal
  run_wt_from_bare_repo "wt 2>&1"
  [ "$status" -eq 0 ]
  # Should list worktrees, not fatal with "this operation must be run in a work tree"
  [[ "$output" =~ "(bare)" ]] || [[ "$output" == "" ]]

  # Test that wtrm --help works from bare repo root
  run_wt_from_bare_repo "wtrm --help 2>&1"
  [ "$status" -eq 0 ]
  [[ "$output" =~ "usage: wtrm" ]]
}
