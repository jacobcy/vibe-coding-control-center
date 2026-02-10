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
assert_contains_regex "api\\.bghunt\\.cn" "$ROOT_DIR/docs/tech-spec-agent-dev.md" "A1: tech spec declares bghunt default endpoint"
assert_contains_regex "^ANTHROPIC_BASE_URL=" "$ROOT_DIR/config/keys.template.env" "A1: keys template defines ANTHROPIC_BASE_URL"
assert_contains_regex "config/keys\\.env" "$ROOT_DIR/install/install-claude.sh" "A3: install-claude references keys.env"
assert_contains_regex "export ANTHROPIC_BASE_URL" "$ROOT_DIR/install/install-claude.sh" "A2/A3: install-claude exports ANTHROPIC_BASE_URL"

# B1/B2/B3: 工具优先级（文档 + alias 对应）
assert_contains_regex "Claude" "$ROOT_DIR/docs/tech-spec-agent-dev.md" "B1: tech spec mentions Claude"
assert_contains_regex "OpenCode" "$ROOT_DIR/docs/tech-spec-agent-dev.md" "B2: tech spec mentions OpenCode"
assert_contains_regex "Codex" "$ROOT_DIR/docs/tech-spec-agent-dev.md" "B3: tech spec mentions Codex"
assert_contains_regex "alias c='claude'" "$ROOT_DIR/config/aliases.sh" "B1: alias for Claude exists"
assert_contains_regex "alias oa='opencode'" "$ROOT_DIR/config/aliases.sh" "B2: alias for OpenCode exists"
# Codex alias removed in refactor
# assert_contains_regex "alias x='codex'" "$ROOT_DIR/config/aliases.sh" "B3: alias for Codex exists"
assert_line_order "# 1\\. OpenCode" "# 2\\. Claude" "$ROOT_DIR/scripts/vibecoding.sh" "B1/B2: OpenCode status checked before Claude"

# C1/C2/C3: Worktree 身份隔离（当前仅检查工作流入口）
assert_contains_regex "wtnew" "$ROOT_DIR/config/aliases.sh" "C1-C3: worktree creation function exists"
assert_contains_regex "local prefix=.*wt-" "$ROOT_DIR/config/aliases.sh" "C1-C3: worktree prefix defaults to wt-"

if command -v rg >/dev/null 2>&1; then
  if rg -n "user\\.name|user\\.email|git config" -S "$ROOT_DIR/config" "$ROOT_DIR/lib" "$ROOT_DIR/scripts" >/dev/null 2>&1; then
    assert_contains_regex "user\\.name" "$ROOT_DIR/docs/tech-spec-agent-dev.md" "C1-C3: tech spec mentions identity isolation"
  else
    skip_test "C1-C3: no git identity isolation implementation found yet"
  fi
else
  skip_test "C1-C3: ripgrep unavailable; skipping identity implementation scan"
fi

# D1/D2/D3: 依赖与会话稳定
assert_contains_regex "vibe_require tmux git" "$ROOT_DIR/config/aliases.sh" "D1: vup requires tmux and git"
assert_contains_regex "tmux has-session" "$ROOT_DIR/config/aliases.sh" "D2: tmux session check exists"
assert_contains_regex "tmux new-session" "$ROOT_DIR/config/aliases.sh" "D2: tmux session creation exists"
assert_contains_regex "vibe_tmux_ensure" "$ROOT_DIR/config/aliases.sh" "D2: tmux ensure helper exists"
assert_contains_regex "vibe_tmux_attach" "$ROOT_DIR/config/aliases.sh" "D2: tmux attach helper exists"
assert_contains_regex "lazygit" "$ROOT_DIR/config/aliases.sh" "D3: lazygit is referenced in tmux workspace"

finish_test_suite
