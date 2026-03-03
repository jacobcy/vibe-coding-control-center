#!/usr/bin/env bats
# Tests for V3 Execution Plane - Session Recovery

load test_utils

setup() {
  setup_test_env
  source "$VIBE_ROOT/config/aliases/session-recovery.sh"
  source "$VIBE_ROOT/config/aliases/execution-contract.sh"
}

@test "log recovery - creates entry" {
  local log_file=".agent/recovery-history.log"
  touch "$log_file"

  _log_recovery "test-123" "wt-claude-test" "claude-test" "SUCCESS" ""

  grep -q "test-123" "$log_file"
  [ $? -eq 0 ]
}

@test "log recovery - includes all fields" {
  local log_file=".agent/recovery-history.log"
  : > "$log_file"

  _log_recovery "test-456" "wt-claude-example" "claude-example" "PARTIAL" "Session recreated"

  local line
  line=$(grep "test-456" "$log_file")

  [[ "$line" == *"test-456"* ]]
  [[ "$line" == *"wt-claude-example"* ]]
  [[ "$line" == *"claude-example"* ]]
  [[ "$line" == *"PARTIAL"* ]]
  [[ "$line" == *"Session recreated"* ]]
}

@test "recovery history - show all" {
  local log_file=".agent/recovery-history.log"
  echo "2026-03-03T06:00:00Z | test-1 | wt-a | sess-a | SUCCESS |" > "$log_file"

  run wtrecover-history
  [ "$status" -eq 0 ]
  [[ "$output" == *"test-1"* ]]
}

@test "recovery history - filter by task_id" {
  local log_file=".agent/recovery-history.log"
  cat > "$log_file" << EOF
2026-03-03T06:00:00Z | task-a | wt-a | sess-a | SUCCESS |
2026-03-03T06:01:00Z | task-b | wt-b | sess-b | SUCCESS |
2026-03-03T06:02:00Z | task-a | wt-a | sess-a | PARTIAL | Session recreated
EOF

  run wtrecover-history "task-a"
  [ "$status" -eq 0 ]
  [[ "$output" == *"task-a"* ]]
  [[ "$output" != *"task-b"* ]]
}
