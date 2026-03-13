#!/usr/bin/env bats

# Reason: Lock agent execution patterns and auto-confirmation conventions
# Entry Criterion: §4.1.2 - High-risk commitment text (agent behavior constraints)
# Alternative Considered: Behavior tests for pattern execution, but text
#                         defines the contract agents must follow

setup() {
  export REPO_ROOT="$BATS_TEST_DIRNAME/../.."
}

@test "doc-text: patterns.md locks auto confirmation without validation bypass" {
  run rg -n \
    "Auto Confirmation Convention|auto|--yes|过程确认|不得跳过验证|fail-fast|高风险决策" \
    "$REPO_ROOT/.agent/rules/patterns.md"

  [ "$status" -eq 0 ]
  [[ "$output" =~ "Auto Confirmation Convention" ]]
  [[ "$output" =~ "不得跳过验证" ]]
}
