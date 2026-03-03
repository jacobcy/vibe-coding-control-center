#!/usr/bin/env zsh
# Session Recovery Commands
# Part of V3 Execution Plane

# Recovery command: wtrecover [--task-id <id>|--worktree <path>|--session <name>]
wtrecover() {
  local mode="" target=""

  # Parse arguments
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --task-id)
        mode="task_id"
        target="$2"
        shift 2
        ;;
      --worktree)
        mode="worktree"
        target="$2"
        shift 2
        ;;
      --session)
        mode="session"
        target="$2"
        shift 2
        ;;
      *)
        echo "Usage: wtrecover [--task-id <id>|--worktree <path>|--session <name>]"
        return 1
        ;;
    esac
  done

  [[ -z "$mode" ]] && {
    echo "Error: Must specify recovery mode"
    echo "Usage: wtrecover [--task-id <id>|--worktree <path>|--session <name>]"
    return 1
  }

  # Source execution contract (loaded by parent worktree.sh or tmux.sh)
  if ! type query_by_task_id >/dev/null 2>&1; then
    echo "Error: execution-contract.sh not loaded (must be sourced before session-recovery.sh)"
    return 1
  fi

  local start_time; start_time=$(date +%s)
  local result worktree session task_id

  # Query execution result based on mode
  case "$mode" in
    task_id)
      result=$(query_by_task_id "$target" 2>/dev/null) || {
        echo "❌ No execution result found for task_id: $target"
        return 1
      }
      ;;
    worktree)
      result=$(query_by_worktree "$target" 2>/dev/null) || {
        echo "❌ No execution result found for worktree: $target"
        return 1
      }
      ;;
    session)
      result=$(query_by_session "$target" 2>/dev/null) || {
        echo "❌ No execution result found for session: $target"
        return 1
      }
      ;;
  esac

  # Extract fields from result
  task_id=$(echo "$result" | jq -r '.task_id' 2>/dev/null)
  worktree=$(echo "$result" | jq -r '.resolved_worktree' 2>/dev/null)
  session=$(echo "$result" | jq -r '.resolved_session' 2>/dev/null)

  echo "🔍 Recovering session..."
  echo "  Task ID: $task_id"
  echo "  Worktree: $worktree"
  echo "  Session: $session"

  # Check worktree exists
  local wt_path
  local git_cmd; git_cmd="$(vibe_find_cmd git)" || { echo "git not found"; return 1; }
  local main_dir; main_dir="$($git_cmd rev-parse --show-toplevel 2>/dev/null)"

  if [[ "$worktree" == /* ]]; then
    wt_path="$worktree"
  else
    wt_path="${main_dir:h}/$worktree"
  fi

  if [[ ! -d "$wt_path" ]]; then
    echo "❌ Worktree not found: $wt_path"
    echo "   Recovery failed - worktree missing"
    _log_recovery "$task_id" "$worktree" "$session" "FAILED" "Worktree missing"
    return 1
  fi

  # Switch to worktree
  echo "✓ Switching to worktree: $worktree"
  cd "$wt_path" || return 1

  # Check session exists
  if ! tmux has-session -t "$session" 2>/dev/null; then
    echo "⚠️  Session lost: $session"
    echo "   Recreating session..."

    # Recreate session
    tmux new-session -d -s "$session" -c "$wt_path" -n "main"
    echo "✓ Session recreated: $session"
    _log_recovery "$task_id" "$worktree" "$session" "PARTIAL" "Session recreated"
  else
    echo "✓ Session found: $session"
    _log_recovery "$task_id" "$worktree" "$session" "SUCCESS" ""
  fi

  # Attach to session
  echo "✓ Attaching to session..."
  tmux attach -t "$session"

  local end_time; end_time=$(date +%s)
  local duration=$((end_time - start_time))
  echo ""
  echo "✅ Recovery complete (${duration}s)"
}

# Log recovery to history
_log_recovery() {
  local task_id="$1" worktree="$2" session="$3" status="$4" details="$5"
  local timestamp; timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

  local log_file="${RECOVERY_HISTORY_LOG:-.agent/recovery-history.log}"
  [[ -f "$log_file" ]] || return

  echo "$timestamp | $task_id | $worktree | $session | $status | $details" >> "$log_file"
}

# Query recovery history
wtrecover-history() {
  local task_id="$1"
  local log_file="${RECOVERY_HISTORY_LOG:-.agent/recovery-history.log}"

  [[ ! -f "$log_file" ]] && {
    echo "No recovery history found"
    return 1
  }

  echo "📋 Recovery History:"
  echo "--------------------"

  if [[ -n "$task_id" ]]; then
    grep "| $task_id |" "$log_file" | tail -20
  else
    tail -20 "$log_file"
  fi
}

echo "✓ Session recovery module loaded"
