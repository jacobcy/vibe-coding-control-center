#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
RUNTIME_FILE="$SKILL_DIR/runtime/agents.sh"

if [[ ! -f "$RUNTIME_FILE" ]]; then
  echo "missing runtime file: $RUNTIME_FILE" >&2
  exit 1
fi

# shellcheck source=/dev/null
source "$RUNTIME_FILE"

DEFAULT_TEAM_GROUP="${TEAM_GROUP:-pr-review-team}"
DEFAULT_LEAD_NAME="team-lead"

usage_common() {
  cat <<'EOF'
Common options:
  --group <name>   Override team group from runtime/agents.sh
EOF
}

defined_agent_names() {
  local row
  for row in "${AGENTS[@]}"; do
    printf '%s\n' "${row%% *}"
  done
}

agent_type_for() {
  local wanted="$1"
  local row name agent_type
  for row in "${AGENTS[@]}"; do
    name="${row%% *}"
    agent_type="${row#* }"
    if [[ "$name" == "$wanted" ]]; then
      printf '%s\n' "$agent_type"
      return 0
    fi
  done
  return 1
}

assert_defined_agent() {
  local agent_name="$1"
  if ! agent_type_for "$agent_name" >/dev/null; then
    echo "undefined agent: $agent_name" >&2
    echo "defined agents:" >&2
    defined_agent_names | sed 's/^/  - /' >&2
    exit 2
  fi
}

team_inbox_dir() {
  local group_name="${1:-$DEFAULT_TEAM_GROUP}"
  printf '%s/.claude/teams/%s/inboxes\n' "$HOME" "$group_name"
}

agent_inbox_path() {
  local group_name="${1:-$DEFAULT_TEAM_GROUP}"
  local agent_name="$2"
  printf '%s/%s.json\n' "$(team_inbox_dir "$group_name")" "$agent_name"
}

lead_inbox_path() {
  local group_name="${1:-$DEFAULT_TEAM_GROUP}"
  printf '%s/%s.json\n' "$(team_inbox_dir "$group_name")" "$DEFAULT_LEAD_NAME"
}

agent_definition_path() {
  local agent_name="$1"
  local agent_type
  agent_type="$(agent_type_for "$agent_name")"
  printf '%s/.claude/agents/%s.md\n' "$(cd "$SKILL_DIR/../.." && pwd)" "$agent_type"
}

print_agent_table_header() {
  printf '%-22s %-28s %-10s %-10s %-10s %-15s %s\n' \
    "agent" "type" "def" "inbox" "pane" "alive" "suggestion"
}

check_pane_exists() {
  local agent_name="$1"
  local agent_type current_session
  agent_type="$(agent_type_for "$agent_name")"

  # 获取当前 tmux session（如果不在 tmux 中，返回失败）
  if ! current_session=$(tmux display-message -p "#{session_name}" 2>/dev/null); then
    return 1
  fi

  # 只在当前 session 中检查 tmux pane 标题是否包含 agent_type 或 agent_name
  if tmux list-panes -t "$current_session" -F "#{pane_title} #{pane_current_command}" 2>/dev/null | \
     grep -qE "(^|✳ |⠐ |⠂ )${agent_type}.*claude"; then
    return 0
  elif tmux list-panes -t "$current_session" -F "#{pane_title} #{pane_current_command}" 2>/dev/null | \
       grep -qE "(^|✳ |⠐ |⠂ )${agent_name}.*claude"; then
    return 0
  else
    return 1
  fi
}

check_last_alive() {
  local agent_name="$1"
  local lead_inbox="$2"
  local now last_timestamp last_epoch age

  # 如果 lead_inbox 不存在，返回 never
  if [[ ! -f "$lead_inbox" ]]; then
    echo "never"
    return
  fi

  now=$(date +%s)

  # 提取最新消息时间戳
  last_timestamp=$(jq -r --arg agent "$agent_name" '
    map(select(.from == $agent))
    | .[-1]
    | .timestamp // empty
  ' "$lead_inbox" 2>/dev/null)

  if [[ -z "$last_timestamp" ]]; then
    echo "never"
    return
  fi

  # 解析 ISO 8601 时间戳（去掉毫秒和 Z）
  # 例如：2026-05-13T04:35:33.664Z -> 2026-05-13T04:35:33
  local ts_clean="${last_timestamp%%.*}Z"
  last_epoch=$(date -j -f "%Y-%m-%dT%H:%M:%SZ" "$ts_clean" +%s 2>/dev/null || echo "0")

  if [[ "$last_epoch" -eq 0 ]]; then
    echo "never"
    return
  fi

  age=$((now - last_epoch))

  # 判断状态并输出
  if [[ $age -lt 10 ]]; then
    echo "active (${age}s)"
  elif [[ $age -lt 60 ]]; then
    echo "idle (${age}s)"
  elif [[ $age -lt 300 ]]; then
    echo "stale (${age}s)"
  else
    echo "inactive (${age}s)"
  fi
}

get_status_suggestion() {
  local definition="$1"
  local inbox="$2"
  local pane="$3"
  local alive="$4"

  # 层级检查：definition 必须先存在
  if [[ "$definition" == "missing" ]]; then
    echo "fix definition file first"
    return
  fi

  # inbox 缺失：未启动
  if [[ "$inbox" == "missing" ]]; then
    echo "spawn agent"
    return
  fi

  # pane 缺失但 inbox 存在：历史启动过但当前不在运行
  if [[ "$pane" == "missing" ]]; then
    echo "check if agent crashed, respawn if needed"
    return
  fi

  # pane 存在，检查 alive 状态
  if [[ "$alive" == never ]]; then
    echo "agent spawned but never sent messages, check logs"
  elif [[ "$alive" =~ inactive ]]; then
    # 从 inactive 中提取时间
    local age="${alive#inactive (}"
    age="${age%s)}"
    if [[ "$age" -gt 3600 ]]; then
      echo "agent inactive for long time (${age}s), may need restart"
    else
      echo "agent inactive (${age}s), send handshake to verify"
    fi
  elif [[ "$alive" =~ stale ]]; then
    echo "agent stale, may be stuck"
  elif [[ "$alive" =~ idle ]]; then
    echo "agent idle, available for task"
  elif [[ "$alive" =~ active ]]; then
    echo "agent active, working on task"
  else
    echo "unknown status"
  fi
}

print_agent_row() {
  local agent_name="$1"
  local group_name="$2"
  local agent_type definition_path inbox_path lead_inbox_path
  local definition_status inbox_status pane_status alive_status suggestion

  agent_type="$(agent_type_for "$agent_name")"
  definition_path="$(agent_definition_path "$agent_name")"
  inbox_path="$(agent_inbox_path "$group_name" "$agent_name")"
  lead_inbox_path="$(lead_inbox_path "$group_name")"

  if [[ -f "$definition_path" ]]; then
    definition_status="ok"
  else
    definition_status="missing"
  fi

  if [[ -f "$inbox_path" ]]; then
    inbox_status="ok"
  else
    inbox_status="missing"
  fi

  if check_pane_exists "$agent_name"; then
    pane_status="ok"
  else
    pane_status="missing"
  fi

  alive_status=$(check_last_alive "$agent_name" "$lead_inbox_path")
  suggestion=$(get_status_suggestion "$definition_status" "$inbox_status" "$pane_status" "$alive_status")

  printf '%-22s %-28s %-10s %-10s %-10s %-15s %s\n' \
    "$agent_name" "$agent_type" "$definition_status" "$inbox_status" "$pane_status" "$alive_status" "$suggestion"
}
