#!/usr/bin/env zsh
# Skill wrappers for OpenClaw automated execution
# These wrappers set EXECUTOR=openclaw and call the underlying commands

# Resolve VIBE_ROOT for sourcing (works when sourced or executed)
if [[ -n "$VIBE_ROOT" ]]; then
  _wrappers_root="$VIBE_ROOT"
else
  # When this file is sourced, use BASH_SOURCE or ZSH script context
  _wrappers_root="$(cd "$(dirname "${BASH_SOURCE[0]:-${(%):-%x}}")/../.." 2>/dev/null && pwd)" || {
    # Fallback: assume we're in skills/execution-plane/
    _wrappers_root="${0:a:h:h:h}"
  }
fi

# Worktree operations wrapper
skill_wtnew() {
  local task_slug="$1" agent="${2:-openclaw}" base="${3:-}"
  [[ -z "$task_slug" ]] && { echo "Usage: skill_wtnew <task-slug> [agent] [base]"; return 1; }

  export EXECUTOR=openclaw
  echo "🤖 OpenClaw Mode: Creating worktree..."

  source "$_wrappers_root/config/aliases/worktree.sh"
  wtnew "$task_slug" "$agent" "$base"
}

skill_wtlist() {
  local filter_owner="$1" filter_task="$2"

  export EXECUTOR=openclaw
  source "$_wrappers_root/config/aliases/worktree.sh"
  wtlist "$filter_owner" "$filter_task"
}

skill_wtvalidate() {
  local wt_name="$1"

  export EXECUTOR=openclaw
  source "$_wrappers_root/config/aliases/worktree.sh"
  wtvalidate "$wt_name"
}

skill_wtrm() {
  local wt_name="$1"

  export EXECUTOR=openclaw
  source "$_wrappers_root/config/aliases/worktree.sh"
  wtrm "$wt_name" --force
}

# Tmux operations wrapper
skill_tmnew() {
  local task_slug="$1" agent="${2:-openclaw}"
  [[ -z "$task_slug" ]] && { echo "Usage: skill_tmnew <task-slug> [agent]"; return 1; }

  export EXECUTOR=openclaw
  echo "🤖 OpenClaw Mode: Creating tmux session..."

  source "$_wrappers_root/config/aliases/tmux.sh"
  tmnew "$task_slug" "$agent"
}

skill_tmattach() {
  local session="$1"

  export EXECUTOR=openclaw
  source "$_wrappers_root/config/aliases/tmux.sh"
  tmattach "$session"
}

skill_tmlist() {
  export EXECUTOR=openclaw
  source "$_wrappers_root/config/aliases/tmux.sh"
  tmlist
}

skill_tmswitch() {
  local session="$1"

  export EXECUTOR=openclaw
  source "$_wrappers_root/config/aliases/tmux.sh"
  tmswitch "$session"
}

skill_tmkill() {
  local session="$1"

  export EXECUTOR=openclaw
  source "$_wrappers_root/config/aliases/tmux.sh"
  tmkill "$session" --force
}

skill_tmrename() {
  local old_name="$1" new_name="$2"

  export EXECUTOR=openclaw
  source "$_wrappers_root/config/aliases/tmux.sh"
  tmrename "$old_name" "$new_name"
}

# Session recovery wrapper
skill_wtrecover() {
  local mode="$1" target="$2"

  export EXECUTOR=openclaw
  echo "🤖 OpenClaw Mode: Recovering session..."

  source "$_wrappers_root/config/aliases/session-recovery.sh"
  case "$mode" in
    task-id)
      wtrecover --task-id "$target"
      ;;
    worktree)
      wtrecover --worktree "$target"
      ;;
    session)
      wtrecover --session "$target"
      ;;
    *)
      echo "Usage: skill_wtrecover <task-id|worktree|session> <target>"
      return 1
      ;;
  esac
}

# Execution contract operations
skill_query_task() {
  local task_id="$1"

  export EXECUTOR=openclaw
  source "$_wrappers_root/config/aliases/execution-contract.sh"
  query_by_task_id "$task_id"
}

skill_query_worktree() {
  local worktree="$1"

  export EXECUTOR=openclaw
  source "$_wrappers_root/config/aliases/execution-contract.sh"
  query_by_worktree "$worktree"
}

skill_query_session() {
  local session="$1"

  export EXECUTOR=openclaw
  source "$_wrappers_root/config/aliases/execution-contract.sh"
  query_by_session "$session"
}

# High-level orchestration commands
skill_prepare_environment() {
  local task_slug="$1" agent="${2:-openclaw}" base="${3:-}"
  [[ -z "$task_slug" ]] && { echo "Usage: skill_prepare_environment <task-slug> [agent] [base]"; return 1; }

  echo "🤖 OpenClaw Mode: Preparing complete development environment..."

  skill_wtnew "$task_slug" "$agent" "$base" || return 1
  skill_tmnew "$task_slug" "$agent" || return 1

  source "$_wrappers_root/config/aliases/execution-contract.sh"
  write_execution_result "$task_slug" "wt-${agent}-${task_slug}" "${agent}-${task_slug}"

  echo "✅ Environment ready for task: $task_slug"
}

skill_cleanup_environment() {
  local task_slug="$1" agent="${2:-openclaw}"
  [[ -z "$task_slug" ]] && { echo "Usage: skill_cleanup_environment <task-slug> [agent]"; return 1; }

  echo "🤖 OpenClaw Mode: Cleaning up development environment..."

  local worktree="wt-${agent}-${task_slug}"
  local session="${agent}-${task_slug}"

  skill_tmkill "$session" || true
  skill_wtrm "$worktree" || true

  echo "✅ Environment cleaned up for task: $task_slug"
}

echo "✓ Skill wrappers loaded"
