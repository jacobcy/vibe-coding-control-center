#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
RUNTIME_FILE="$SKILL_DIR/runtime/agents.sh"

# 推导仓库根路径（支持 skills/ 和 .claude/skills/ 两种入口点）
# 向上查找直到找到 .git 目录或 CLAUDE.md 文件
REPO_ROOT="$(cd "$SKILL_DIR" && while [[ "$(pwd)" != "/" ]]; do
  if [[ -f "CLAUDE.md" || -d ".git" ]]; then
    pwd
    break
  fi
  cd ..
done)"

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
  printf '%s/.claude/agents/%s.md\n' "$REPO_ROOT" "$agent_type"
}

print_agent_table_header() {
  printf '%-22s %-28s %-10s %-10s %-10s %-15s %s\n' \
    "agent" "type" "def" "inbox" "pane" "alive" "suggestion"
}

check_pane_exists() {
  local agent_name="$1"
  local agent_type

  if ! agent_type="$(agent_type_for "$agent_name")"; then
    # Agent not defined in AGENTS array
    return 1
  fi

  # Search all tmux sessions for one matching the agent pattern.
  # Session naming convention: vibe3-{agent_type}-* or vibe3-{agent_name}-*
  local session
  while IFS= read -r session; do
    if [[ "$session" == vibe3-"${agent_type}"-* ]] || [[ "$session" == vibe3-"${agent_name}"-* ]]; then
      # Session found — verify it's alive (has at least one pane with a running command)
      if tmux list-panes -t "$session" -F '#{pane_current_command}' 2>/dev/null | grep -q .; then
        return 0
      fi
    fi
  done < <(tmux list-sessions -F '#{session_name}' 2>/dev/null)

  return 1
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

  # 使用 UTC 时区获取当前时间（epoch）
  now=$(TZ=UTC date +%s)

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
  # 例如：2026-05-13T04:52:11.068Z -> 2026-05-13T04:52:11
  local ts_clean="${last_timestamp%%.*}"
  # 使用 UTC 时区解析时间戳
  last_epoch=$(TZ=UTC date -j -f "%Y-%m-%dT%H:%M:%S" "$ts_clean" +%s 2>/dev/null || echo "0")

  if [[ "$last_epoch" -eq 0 ]]; then
    echo "never"
    return
  fi

  age=$((now - last_epoch))

  # 判断状态并输出
  if [[ $age -lt 10 ]]; then
    echo "active (${age}s)  # estimate only; check tmux pane content to verify"
  elif [[ $age -lt 180 ]]; then
    echo "idle (${age}s)    # estimate only; check tmux pane content to verify"
  elif [[ $age -lt 600 ]]; then
    echo "stale (${age}s)   # estimate only; capture tmux pane output before handshake"
  else
    echo "inactive (${age}s) # estimate only; capture tmux pane output before handshake"
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
    echo "send handshake to verify"
    return
  fi

  # pane 存在，检查 alive 状态
  if [[ "$alive" == never ]]; then
    echo "send handshake to verify"
  elif [[ "$alive" =~ inactive ]]; then
    echo "send handshake to verify"
  elif [[ "$alive" =~ stale ]]; then
    echo "send handshake to verify"
  elif [[ "$alive" =~ idle ]]; then
    echo "available for task"
  elif [[ "$alive" =~ active ]]; then
    echo "working on task"
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
