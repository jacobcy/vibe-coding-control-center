#!/usr/bin/env bats

setup() {
  export PATH="$BATS_TEST_DIRNAME/../bin:$PATH"
  export VIBE_ROOT="$BATS_TEST_DIRNAME/.."
  # Source needed libraries for unit tests
  source "$VIBE_ROOT/lib/config.sh"
  source "$VIBE_ROOT/lib/utils.sh"
  source "$VIBE_ROOT/lib/flow.sh"
}

@test "1. vibe flow help outputs subcommands" {
  run vibe flow help
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Usage: vibe flow <command>" ]]
  [[ "$output" =~ "start" ]]
  [[ "$output" =~ "review" ]]
  [[ "$output" =~ "pr" ]]
  [[ "$output" =~ "done" ]]
}

@test "2. vibe flow start without args returns error" {
  run vibe flow start
  [ "$status" -eq 1 ]
  [[ "$output" =~ "Usage: vibe flow start" ]]
}

@test "3. vibe flow status in non-worktree returns error" {
  # Run in a directory that is definitely not a worktree
  cd /tmp
  run vibe flow status
  [ "$status" -eq 1 ]
  [[ "$output" =~ "Not in a worktree" ]]
}

@test "4. _detect_feature extracts feature from dir name" {
  # Create a fake worktree dir and extract feature
  mkdir -p /tmp/wt-claude-myfeature
  cd /tmp/wt-claude-myfeature
  run zsh -c "source $VIBE_ROOT/lib/config.sh && source $VIBE_ROOT/lib/utils.sh && source $VIBE_ROOT/lib/flow.sh && _detect_feature"
  [ "$status" -eq 0 ]
  [ "$output" = "myfeature" ]
  rm -rf /tmp/wt-claude-myfeature
}

@test "5. _detect_agent extracts agent from dir name" {
  # Create a fake worktree dir and extract agent
  mkdir -p /tmp/wt-opencode-myfeature
  cd /tmp/wt-opencode-myfeature
  run zsh -c "source $VIBE_ROOT/lib/config.sh && source $VIBE_ROOT/lib/utils.sh && source $VIBE_ROOT/lib/flow.sh && _detect_agent"
  [ "$status" -eq 0 ]
  [ "$output" = "opencode" ]
  rm -rf /tmp/wt-opencode-myfeature
}
