#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/lib.sh"

show_usage() {
  cat <<'EOF'
Usage:
  agent-report.sh
  agent-report.sh <agent_name>
  agent-report.sh <agent_name> --group <name>

Behavior:
  - Without agent_name: list all agents with report status.
  - With agent_name: extract the latest report-like message from that agent.
  - Reads team-lead inbox only.
  - Prefer messages starting with 【agent_report】.
  - Fallback to report-shaped messages such as "## PR #" / "# PR #" / messages containing "报告".
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

# 列表模式：显示所有 agent 的报告状态
if [[ -z "$AGENT_NAME" ]]; then
  LEAD_INBOX="$(lead_inbox_path "$GROUP_NAME")"
  if [[ ! -f "$LEAD_INBOX" ]]; then
    echo "lead inbox not found: $LEAD_INBOX" >&2
    exit 1
  fi

  echo "# Report Status Overview"
  echo "# Use: agent-report.sh <agent_name> to extract full report"
  echo "#"
  echo "group=$GROUP_NAME"
  echo "team_inbox_dir=$(team_inbox_dir "$GROUP_NAME")"
  printf '%-22s %-10s %-30s\n' "agent" "report" "timestamp"

  while IFS= read -r agent_name; do
    timestamp="$(
      jq -r \
        --arg agent "$agent_name" '
        def is_idle:
          startswith("{\"type\":\"idle_notification\"");
        def is_ready:
          test("^【agent_ready】") or test("^\\[agent_ready\\]");
        def is_report_like:
          test("^【agent_report】") or test("^\\[agent_report\\]")
          or test("^## PR #") or test("^# PR #")
          or contains("审查报告") or contains("背景报告");
        map(select(.from == $agent))
        | map(select((.text | is_idle) | not))
        | map(select((.text | is_ready) | not))
        | map(select(.text | is_report_like))
        | sort_by(.timestamp)
        | if length == 0 then
            "-"
          else
            .[-1].timestamp
          end
      ' "$LEAD_INBOX"
    )"

    if [[ "$timestamp" == "-" ]]; then
      status="missing"
    else
      status="ok"
    fi

    printf '%-22s %-10s %-30s\n' "$agent_name" "$status" "$timestamp"
  done < <(defined_agent_names)
  exit 0
fi

# 提取模式：提取单个 agent 的报告
assert_defined_agent "$AGENT_NAME"

LEAD_INBOX="$(lead_inbox_path "$GROUP_NAME")"
if [[ ! -f "$LEAD_INBOX" ]]; then
  echo "lead inbox not found: $LEAD_INBOX" >&2
  exit 1
fi

OUTPUT="$(
  jq -r \
    --arg agent "$AGENT_NAME" '
    def is_idle:
      startswith("{\"type\":\"idle_notification\"");
    def is_ready:
      test("^【agent_ready】") or test("^\\[agent_ready\\]");
    def is_report_like:
      test("^【agent_report】") or test("^\\[agent_report\\]")
      or test("^## PR #") or test("^# PR #")
      or contains("审查报告") or contains("背景报告");
    map(select(.from == $agent))
    | map(select((.text | is_idle) | not))
    | map(select((.text | is_ready) | not))
    | map(select(.text | is_report_like))
    | sort_by(.timestamp)
    | if length == 0 then
        empty
      else
        .[-1] as $msg
        | [
            ("agent=" + $msg.from),
            ("timestamp=" + $msg.timestamp),
            "body_start",
            $msg.text
          ]
        | join("\n")
      end
  ' "$LEAD_INBOX"
)"

if [[ -z "$OUTPUT" ]]; then
  echo "report_event=missing" >&2
  echo "No report yet. Agent may still be working. Check agent-exist.sh to verify status." >&2
  echo "If stale/inactive, capture tmux pane content before retrying handshake." >&2
  exit 3
fi

printf '%s\n' "$OUTPUT"
