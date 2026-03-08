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

make_worktree_dashboard() {
  local current_dir="${1:-$TEST_DIR/wt-claude-refactor}"
  mkdir -p "$TEST_DIR/repo/.git/vibe" "$current_dir"
  cat > "$TEST_DIR/repo/.git/vibe/worktrees.json" <<EOF
{"schema_version":"v1","worktrees":[{"worktree_name":"$(basename "$current_dir")","worktree_path":"$current_dir","branch":"claude/refactor","current_task":"task-1","tasks":["task-1"],"status":"active","dirty":false,"last_updated":"2026-03-08T10:00:00+08:00"}]}
EOF
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
      "rev-parse --git-common-dir") printf '%s\n' "$TEST_DIR/repo/.git"; exit 0 ;;
      "status --porcelain") printf '?? draft.txt\n'; exit 0 ;;
      "stash push -u -m Rotate to feature-safe: saved WIP") exit 0 ;;
      "branch --show-current") printf 'feature-old\n'; exit 0 ;;
      "check-ref-format --branch feature-safe") exit 0 ;;
      "checkout -b feature-safe") exit 0 ;;
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
      "checkout --detach HEAD --quiet") exit 0 ;;
      "checkout -b bad branch") exit 1 ;;
      *) exit 0 ;;
    esac
    ;;
  generic_target)
    case "$*" in
      "rev-parse --is-inside-work-tree") exit 0 ;;
      "check-ref-format --branch refactor") exit 0 ;;
      "branch --show-current") printf 'bug-fix\n'; exit 0 ;;
      "status --porcelain") printf '?? draft.txt\n'; exit 0 ;;
      "stash push -u -m Rotate to refactor: saved WIP") exit 0 ;;
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
  protected_branch)
    case "$*" in
      "rev-parse --is-inside-work-tree") exit 0 ;;
      "check-ref-format --branch feature-safe") exit 0 ;;
      "branch --show-current") printf 'main\n'; exit 0 ;;
      "status --porcelain") printf '?? draft.txt\n'; exit 0 ;;
      "stash push -u -m Rotate to feature-safe: saved WIP") exit 0 ;;
      *) exit 1 ;;
    esac
    ;;
  update_dashboard)
    case "$*" in
      "rev-parse --is-inside-work-tree") exit 0 ;;
      "rev-parse --git-common-dir") printf '%s\n' "$TEST_DIR/repo/.git"; exit 0 ;;
      "check-ref-format --branch feature-safe") exit 0 ;;
      "branch --show-current") printf 'claude/refactor\n'; exit 0 ;;
      "status --porcelain") printf '?? draft.txt\n'; exit 0 ;;
      "stash push -u -m Rotate to feature-safe: saved WIP") exit 0 ;;
      "checkout -b feature-safe") exit 0 ;;
      "stash pop") exit 0 ;;
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
  grep -q "checkout -b feature-safe" "$LOG_FILE"
  ! grep -q "branch -D feature-old" "$LOG_FILE"
  ! grep -q "push origin --delete feature-old" "$LOG_FILE"
  ! grep -q "fetch origin main --quiet" "$LOG_FILE"
}

@test "rotate rejects invalid branch names before deleting current branch" {
  write_mock_git
  run env PATH="$TEST_DIR/bin:/usr/bin:/bin" LOG_FILE="$LOG_FILE" MOCK_MODE=invalid_branch "$TEST_DIR/rotate.sh" "bad branch"

  [ "$status" -eq 1 ]
  [[ "$output" =~ "Invalid branch name" ]]
  ! grep -q "checkout --detach HEAD --quiet" "$LOG_FILE"
  ! grep -q "branch -D feature-old" "$LOG_FILE"
}

@test "rotate rejects generic target workflow names before stashing" {
  write_mock_git
  run env PATH="$TEST_DIR/bin:/usr/bin:/bin" LOG_FILE="$LOG_FILE" MOCK_MODE=generic_target "$TEST_DIR/rotate.sh" refactor

  [ "$status" -eq 1 ]
  [[ "$output" =~ "generic workflow name" ]]
  ! grep -q "stash push -u -m Rotate to refactor: saved WIP" "$LOG_FILE"
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

@test "rotate rejects protected branches before stashing" {
  write_mock_git
  run env PATH="$TEST_DIR/bin:/usr/bin:/bin" LOG_FILE="$LOG_FILE" MOCK_MODE=protected_branch "$TEST_DIR/rotate.sh" feature-safe

  [ "$status" -eq 1 ]
  [[ "$output" =~ "Refusing to rotate protected branch: main" ]]
  ! grep -q "stash push -u -m Rotate to feature-safe: saved WIP" "$LOG_FILE"
}

@test "rotate updates worktrees dashboard branch for current worktree" {
  write_mock_git
  make_worktree_dashboard

  run env PATH="$TEST_DIR/bin:/usr/bin:/bin" LOG_FILE="$LOG_FILE" TEST_DIR="$TEST_DIR" MOCK_MODE=update_dashboard "$TEST_DIR/rotate.sh" feature-safe

  [ "$status" -eq 0 ]
  [ "$(jq -r '.worktrees[0].branch' "$TEST_DIR/repo/.git/vibe/worktrees.json")" = "feature-safe" ]
}
