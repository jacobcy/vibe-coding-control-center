#!/usr/bin/env bats

setup() {
  export VIBE_ROOT="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
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

@test "wtrm --help exits without hanging" {
  run_zsh_with_timeout "source \"$VIBE_ROOT/lib/utils.sh\"; source \"$VIBE_ROOT/alias/worktree.sh\"; wtrm --help"

  [ "$status" -eq 0 ]
  [[ "$output" =~ "usage: wtrm [--yes] [--delete-remote]" ]]
}

@test "wtrm rejects extra positional args without hanging" {
  run_zsh_with_timeout "source \"$VIBE_ROOT/lib/utils.sh\"; source \"$VIBE_ROOT/alias/worktree.sh\"; wtrm one two"

  [ "$status" -eq 1 ]
  [[ "$output" =~ "Unexpected argument: two" ]]
}
