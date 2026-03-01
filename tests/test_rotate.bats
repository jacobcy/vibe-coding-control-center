#!/usr/bin/env bats

setup() {
  export REPO_ROOT="$BATS_TEST_DIRNAME/.."
  export TEST_DIR="$BATS_TEST_TMPDIR/rotate"
  mkdir -p "$TEST_DIR/bin"
  cp "$REPO_ROOT/scripts/rotate.sh" "$TEST_DIR/rotate.sh"
  chmod +x "$TEST_DIR/rotate.sh"
  export LOG_FILE="$TEST_DIR/git.log"
  : > "$LOG_FILE"
}

write_mock_git() {
  cat > "$TEST_DIR/bin/git" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

printf '%s\n' "$*" >> "$LOG_FILE"

case "${MOCK_MODE:-}" in
  stash_requires_u)
    case "$*" in
      "rev-parse --is-inside-work-tree") exit 0 ;;
      "status --porcelain") printf '?? draft.txt\n'; exit 0 ;;
      "stash push -u -m Rotate to feature-safe: saved WIP") exit 0 ;;
      "branch --show-current") printf 'feature-old\n'; exit 0 ;;
      "check-ref-format --branch feature-safe") exit 0 ;;
      "fetch origin main --quiet") exit 0 ;;
      "show-ref --verify --quiet refs/remotes/origin/main") exit 0 ;;
      "checkout --detach HEAD --quiet") exit 0 ;;
      "branch -D feature-old") exit 0 ;;
      "checkout -b feature-safe origin/main") exit 0 ;;
      "stash pop") exit 0 ;;
      *) exit 1 ;;
    esac
    ;;
  invalid_branch)
    case "$*" in
      "rev-parse --is-inside-work-tree") exit 0 ;;
      "status --porcelain") exit 0 ;;
      "branch --show-current") printf 'feature-old\n'; exit 0 ;;
      "check-ref-format --branch bad branch") exit 1 ;;
      "fetch origin main --quiet") exit 0 ;;
      "show-ref --verify --quiet refs/remotes/origin/main") exit 0 ;;
      "checkout --detach HEAD --quiet") exit 0 ;;
      "branch -D feature-old") exit 0 ;;
      "checkout -b bad branch origin/main") exit 1 ;;
      *) exit 0 ;;
    esac
    ;;
  missing_origin_main)
    case "$*" in
      "rev-parse --is-inside-work-tree") exit 0 ;;
      "status --porcelain") exit 0 ;;
      "branch --show-current") printf 'feature-old\n'; exit 0 ;;
      "check-ref-format --branch feature-safe") exit 0 ;;
      "fetch origin main --quiet") exit 0 ;;
      "show-ref --verify --quiet refs/remotes/origin/main") exit 1 ;;
      "checkout --detach HEAD --quiet") exit 0 ;;
      "branch -D feature-old") exit 0 ;;
      *) exit 0 ;;
    esac
    ;;
  detached_head)
    case "$*" in
      "rev-parse --is-inside-work-tree") exit 0 ;;
      "check-ref-format --branch feature-safe") exit 0 ;;
      "branch --show-current") exit 0 ;;
      "status --porcelain") printf '?? draft.txt\n'; exit 0 ;;
      "stash push -u -m Rotate to feature-safe: saved WIP") exit 0 ;;
      *) exit 1 ;;
    esac
    ;;
  same_branch_name)
    case "$*" in
      "rev-parse --is-inside-work-tree") exit 0 ;;
      "check-ref-format --branch feature-old") exit 0 ;;
      "branch --show-current") printf 'feature-old\n'; exit 0 ;;
      "status --porcelain") printf '?? draft.txt\n'; exit 0 ;;
      "stash push -u -m Rotate to feature-old: saved WIP") exit 0 ;;
      *) exit 1 ;;
    esac
    ;;
  *)
    exit 1
    ;;
esac
EOF

  chmod +x "$TEST_DIR/bin/git"
}

@test "rotate stashes untracked files with -u" {
  write_mock_git
  run env PATH="$TEST_DIR/bin:/usr/bin:/bin" LOG_FILE="$LOG_FILE" MOCK_MODE=stash_requires_u "$TEST_DIR/rotate.sh" feature-safe

  [ "$status" -eq 0 ]
  grep -q "stash push -u -m Rotate to feature-safe: saved WIP" "$LOG_FILE"
}

@test "rotate rejects invalid branch names before deleting current branch" {
  write_mock_git
  run env PATH="$TEST_DIR/bin:/usr/bin:/bin" LOG_FILE="$LOG_FILE" MOCK_MODE=invalid_branch "$TEST_DIR/rotate.sh" "bad branch"

  [ "$status" -eq 1 ]
  [[ "$output" =~ "Invalid branch name" ]]
  ! grep -q "checkout --detach HEAD --quiet" "$LOG_FILE"
  ! grep -q "branch -D feature-old" "$LOG_FILE"
}

@test "rotate verifies origin/main exists before deleting current branch" {
  write_mock_git
  run env PATH="$TEST_DIR/bin:/usr/bin:/bin" LOG_FILE="$LOG_FILE" MOCK_MODE=missing_origin_main "$TEST_DIR/rotate.sh" feature-safe

  [ "$status" -eq 1 ]
  [[ "$output" =~ "origin/main" ]]
  ! grep -q "checkout --detach HEAD --quiet" "$LOG_FILE"
  ! grep -q "branch -D feature-old" "$LOG_FILE"
}

@test "rotate does not stash before rejecting detached HEAD" {
  write_mock_git
  run env PATH="$TEST_DIR/bin:/usr/bin:/bin" LOG_FILE="$LOG_FILE" MOCK_MODE=detached_head "$TEST_DIR/rotate.sh" feature-safe

  [ "$status" -eq 1 ]
  [[ "$output" =~ "Not on a branch" ]]
  ! grep -q "stash push -u -m Rotate to feature-safe: saved WIP" "$LOG_FILE"
}

@test "rotate does not stash before rejecting same branch name" {
  write_mock_git
  run env PATH="$TEST_DIR/bin:/usr/bin:/bin" LOG_FILE="$LOG_FILE" MOCK_MODE=same_branch_name "$TEST_DIR/rotate.sh" feature-old

  [ "$status" -eq 1 ]
  [[ "$output" =~ "New branch name matches current branch" ]]
  ! grep -q "stash push -u -m Rotate to feature-old: saved WIP" "$LOG_FILE"
}
