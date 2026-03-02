#!/usr/bin/env bats
# Tests for naming conflict handling with parallel sessions

load test_utils

setup() {
  source config/aliases/worktree.sh
  source config/aliases/tmux.sh
}

@test "Conflict: Auto-suffix generation uniqueness" {
  # Generate 100 suffixes
  local -a suffixes=()
  for i in {1..100}; do
    suffix=$(_generate_conflict_suffix)
    suffixes+=("$suffix")
  done

  # Check all are 4 chars
  for suffix in "${suffixes[@]}"; do
    [ ${#suffix} -eq 4 ]
  done

  # Check uniqueness (should be > 95% unique for 100 samples)
  local unique_count
  unique_count=$(printf '%s\n' "${suffixes[@]}" | sort -u | wc -l)
  [ "$unique_count" -ge 95 ]
}

@test "Conflict: Parallel worktree creation" {
  # Simulate 5 parallel creations
  local -a pids=()
  for i in {1..5}; do
    wtnew "parallel-test-$i" claude main &
    pids+=($!)
  done

  # Wait for all
  for pid in "${pids[@]}"; do
    wait "$pid" || true
  done

  # All should succeed (some with auto-suffix)
  local count
  count=$(wtlist claude | grep -c "parallel-test" || echo 0)
  [ "$count" -ge 5 ]

  # Cleanup
  for i in {1..5}; do
    wtrm "wt-claude-parallel-test-$i*" --force 2>/dev/null || true
  done
}

@test "Conflict: Suffix doesn't break naming convention" {
  # Create worktree with suffix
  local suffix
  suffix=$(_generate_conflict_suffix)
  local wt_name="wt-claude-test-${suffix}"

  # Should still validate
  run _validate_worktree_name "$wt_name"
  [ "$status" -eq 0 ]
}

@test "Conflict: Session name conflict handling" {
  # Create session
  tmnew conflict-session claude || true

  # Try to create duplicate
  run tmnew conflict-session claude
  [ "$status" -eq 0 ]
  [[ "$output" == *"exists"* ]]

  # Cleanup
  tmkill claude-conflict-session --force || true
}
