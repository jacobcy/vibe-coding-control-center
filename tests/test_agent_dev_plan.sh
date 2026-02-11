#!/usr/bin/env zsh
# Tests for agent-dev plan expectations (static + light behavioral checks)

set +o xtrace
set +o verbose

ROOT_DIR="$(cd "$(dirname "${(%):-%x}")/.." && pwd)"

source "$ROOT_DIR/lib/utils.sh"
source "$ROOT_DIR/lib/testing.sh"

file_contains_regex() {
  local pattern="$1"
  local path="$2"
  local line

  [[ -f "$path" ]] || return 1

  while IFS= read -r line; do
    if [[ "$line" =~ $pattern ]]; then
      return 0
    fi
  done < "$path"

  return 1
}

line_number_for_pattern() {
  local pattern="$1"
  local path="$2"
  local line
  local line_no=0

  [[ -f "$path" ]] || return 1

  while IFS= read -r line; do
    ((line_no++))
    if [[ "$line" =~ $pattern ]]; then
      echo "$line_no"
      return 0
    fi
  done < "$path"

  return 1
}

assert_contains_regex() {
  local pattern="$1"
  local path="$2"
  local message="$3"
  assert_true "file_contains_regex \"$pattern\" \"$path\"" "$message"
}

assert_line_order() {
  local pattern_a="$1"
  local pattern_b="$2"
  local path="$3"
  local message="$4"

  local line_a line_b
  line_a=$(line_number_for_pattern "$pattern_a" "$path" || true)
  line_b=$(line_number_for_pattern "$pattern_b" "$path" || true)

  if [[ -z "$line_a" || -z "$line_b" ]]; then
    assert_true "false" "$message (pattern missing)"
    return
  fi

  assert_true "[[ $line_a -lt $line_b ]]" "$message"
}

skip_test() {
  local message="$1"
  ((++TEST_TOTAL))
  log_warn "↷ SKIP: $message"
}

start_test_suite "Agent Dev Plan"

# A1/A2/A3: 环境变量与端点切换（静态验证）
assert_contains_regex "^ANTHROPIC_BASE_URL=" "$ROOT_DIR/config/keys.template.env" "A1: keys template defines ANTHROPIC_BASE_URL"

# B1/B2/B3: 工具优先级（文档 + alias 对应）
assert_contains_regex "alias c='claude'" "$ROOT_DIR/config/aliases.sh" "B1: alias for Claude exists"
assert_contains_regex "alias oa='opencode'" "$ROOT_DIR/config/aliases.sh" "B2: alias for OpenCode exists"
# Codex alias removed in refactor
# assert_contains_regex "alias x='codex'" "$ROOT_DIR/config/aliases.sh" "B3: alias for Codex exists"
assert_line_order "1\\. Install/Update OpenCode" "2\\. Install/Update Claude Code" "$ROOT_DIR/bin/vibe-equip" "B1/B2: OpenCode listed before Claude in equip menu"

# C1/C2/C3: Worktree 身份隔离（当前仅检查工作流入口）
assert_contains_regex "wtnew" "$ROOT_DIR/config/aliases.sh" "C1-C3: worktree creation function exists"
assert_contains_regex "local prefix=.*wt-" "$ROOT_DIR/config/aliases.sh" "C1-C3: worktree prefix defaults to wt-"

# D1/D2/D3: 依赖与会话稳定
assert_contains_regex "vibe_require tmux git" "$ROOT_DIR/config/aliases.sh" "D1: vup requires tmux and git"
assert_contains_regex "tmux has-session" "$ROOT_DIR/config/aliases.sh" "D2: tmux session check exists"
assert_contains_regex "tmux new-session" "$ROOT_DIR/config/aliases.sh" "D2: tmux session creation exists"
assert_contains_regex "vibe_tmux_ensure" "$ROOT_DIR/config/aliases.sh" "D2: tmux ensure helper exists"
assert_contains_regex "vibe_tmux_attach" "$ROOT_DIR/config/aliases.sh" "D2: tmux attach helper exists"
assert_contains_regex "lazygit" "$ROOT_DIR/config/aliases.sh" "D3: lazygit is referenced in tmux workspace"

finish_test_suite
