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
  printf '%-22s %-28s %-10s %-10s %-10s\n' \
    "agent" "type" "definition" "inbox" "pane"
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

print_agent_row() {
  local agent_name="$1"
  local group_name="$2"
  local agent_type definition_path inbox_path definition_status inbox_status pane_status

  agent_type="$(agent_type_for "$agent_name")"
  definition_path="$(agent_definition_path "$agent_name")"
  inbox_path="$(agent_inbox_path "$group_name" "$agent_name")"

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

  printf '%-22s %-28s %-10s %-10s %-10s\n' \
    "$agent_name" "$agent_type" "$definition_status" "$inbox_status" "$pane_status"
}
