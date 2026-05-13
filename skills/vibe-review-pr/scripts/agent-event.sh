#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/lib.sh"

show_usage() {
  cat <<'EOF'
Usage:
  agent-event.sh
  agent-event.sh <agent_name>
  agent-event.sh <agent_name> --group <name>

Behavior:
  - Without agent_name: list all agents with latest event status.
  - With agent_name: list all events from that agent (event_type, timestamp, title).
  - Reads team-lead inbox only.
  - Supports both Chinese brackets 【】 and English brackets [].
EOF
  usage_common
}

GROUP_NAME="$DEFAULT_TEAM_GROUP"
AGENT_NAME=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --group)
      GROUP_NAME="${2:?missing group name}"
      shift 2
      ;;
    -h|--help)
      show_usage
      exit 0
      ;;
    -*)
      echo "unknown option: $1" >&2
      show_usage >&2
      exit 2
      ;;
    *)
      if [[ -n "$AGENT_NAME" ]]; then
        echo "unexpected extra argument: $1" >&2
        show_usage >&2
        exit 2
      fi
      AGENT_NAME="$1"
      shift
      ;;
  esac
done

# 列表模式：显示所有 agent 的最新事件状态
if [[ -z "$AGENT_NAME" ]]; then
  LEAD_INBOX="$(lead_inbox_path "$GROUP_NAME")"
  if [[ ! -f "$LEAD_INBOX" ]]; then
    echo "lead inbox not found: $LEAD_INBOX" >&2
    exit 1
  fi

  echo "# Event Status Overview"
  echo "# Use: agent-event.sh <agent_name> to list all events"
  echo "#"
  echo "group=$GROUP_NAME"
  echo "team_inbox_dir=$(team_inbox_dir "$GROUP_NAME")"
  printf '%-22s %-10s %-20s\n' "agent" "events" "latest_event"

  while IFS= read -r agent_name; do
    latest="$(
      jq -r \
        --arg agent "$agent_name" '
        def is_idle:
          startswith("{\"type\":\"idle_notification\"");
        def extract_event_type:
          if test("^(【|\\[)agent_[a-z_]+(】|\\])") then
            capture("^(【|\\[)(?<type>agent_[a-z_]+)(】|\\])") | .type
          elif test("^## PR #") or test("^# PR #") or contains("审查报告") or contains("背景报告") then
            "agent_report"
          else
            "message"
          end;
        map(select(.from == $agent))
        | map(select((.text | is_idle) | not))
        | sort_by(.timestamp)
        | if length == 0 then
            "-"
          else
            .[-1].text | split("\n")[0]
          end
      ' "$LEAD_INBOX"
    )"

    if [[ "$latest" == "-" ]]; then
      events="none"
      event_type="-"
    else
      events="ok"
      event_type="$latest"
    fi

    printf '%-22s %-10s %-20s\n' "$agent_name" "$events" "$event_type"
  done < <(defined_agent_names)
  exit 0
fi

# 详细模式：列出单个 agent 的所有事件
assert_defined_agent "$AGENT_NAME"

LEAD_INBOX="$(lead_inbox_path "$GROUP_NAME")"
if [[ ! -f "$LEAD_INBOX" ]]; then
  echo "lead inbox not found: $LEAD_INBOX" >&2
  exit 1
fi

echo "# Events from $AGENT_NAME"
echo "# Use: cat $LEAD_INBOX | jq to see full content"
echo "#"
printf '%-20s %-30s %s\n' "event_type" "timestamp" "title"

jq -r \
  --arg agent "$AGENT_NAME" '
  def is_idle:
    startswith("{\"type\":\"idle_notification\"");
  def extract_event_type:
    # 尝试提取【agent_xxx】或[agent_xxx]
    if test("^(【|\\[)agent_[a-z_]+(】|\\])") then
      capture("^(【|\\[)(?<type>agent_[a-z_]+)(】|\\])") | .type
    elif test("^## PR #") or test("^# PR #") or contains("审查报告") or contains("背景报告") then
      "agent_report"
    else
      "message"
    end;
  map(select(.from == $agent))
  | map(select((.text | is_idle) | not))
  | sort_by(.timestamp)
  | .[]
  | [
      (.text | extract_event_type),
      .timestamp,
      (.text | split("\n")[0])
    ]
  | @tsv
' "$LEAD_INBOX" | while IFS=$'\t' read -r event_type timestamp title; do
  printf '%-20s %-30s %s\n' "$event_type" "$timestamp" "$title"
done
