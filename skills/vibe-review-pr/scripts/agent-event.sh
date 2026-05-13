#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/lib.sh"

show_usage() {
  cat <<'EOF'
Usage:
  agent-event.sh <agent_name> <event_type> [--latest]
  agent-event.sh <agent_name> <event_type> [--group <name>] [--latest]

Behavior:
  - Reads team-lead inbox only.
  - Extracts messages with event prefix from the requested agent.
  - Supports both 【event_type】 and [event_type] formats.
  - By default prints all matching events sorted by timestamp.
  - Use --latest to print only the most recent event.

Event Types:
  - agent_ready: handshake ready notification
  - agent_report: task completion report
  - agent_progress: progress update (optional)
  - agent_blocked: task blocked notification (optional)
  - agent_handoff: task handoff notification (optional)

Examples:
  # Check if context-researcher completed handshake
  agent-event.sh context-researcher agent_ready --latest

  # Extract latest report from architect-reviewer
  agent-event.sh architect-reviewer agent_report --latest

  # List all progress updates from code-analyst
  agent-event.sh code-analyst agent_progress
EOF
  usage_common
}

GROUP_NAME="$DEFAULT_TEAM_GROUP"
AGENT_NAME=""
EVENT_TYPE=""
LATEST_ONLY="0"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --group)
      GROUP_NAME="${2:?missing group name}"
      shift 2
      ;;
    --latest)
      LATEST_ONLY="1"
      shift
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
      if [[ -z "$AGENT_NAME" ]]; then
        AGENT_NAME="$1"
      elif [[ -z "$EVENT_TYPE" ]]; then
        EVENT_TYPE="$1"
      else
        echo "unexpected extra argument: $1" >&2
        show_usage >&2
        exit 2
      fi
      shift
      ;;
  esac
done

if [[ -z "$AGENT_NAME" || -z "$EVENT_TYPE" ]]; then
  show_usage >&2
  exit 2
fi

VALID_EVENTS="agent_ready agent_report agent_progress agent_blocked agent_handoff"
case " $VALID_EVENTS " in
  *" $EVENT_TYPE "*) ;;
  *) echo "unknown event type: $EVENT_TYPE" >&2
     echo "valid types: agent_ready, agent_report, agent_progress, agent_blocked, agent_handoff" >&2
     exit 2 ;;
esac

assert_defined_agent "$AGENT_NAME"

LEAD_INBOX="$(lead_inbox_path "$GROUP_NAME")"
if [[ ! -f "$LEAD_INBOX" ]]; then
  echo "lead inbox not found: $LEAD_INBOX" >&2
  exit 1
fi

# 兼容中文和英文方括号
OUTPUT="$(
  jq -r \
    --arg agent "$AGENT_NAME" \
    --arg event "$EVENT_TYPE" \
    --arg latest "$LATEST_ONLY" '
  ("【" + $event + "】") as $event_cn
  | ("[" + $event + "]") as $event_en
  | def is_event:
      startswith($event_cn) or startswith($event_en);
  def is_idle:
      startswith("{\"type\":\"idle_notification\"");
  def split_text($text):
      ($text | split("\n")) as $lines
      | reduce $lines[] as $line (
          {head_lines: [], body_lines: [], in_body: false};
          if .in_body then
            .body_lines += [$line]
          elif $line == "" then
            .in_body = true
          else
            .head_lines += [$line]
          end
        )
      | {
          head: (.head_lines | join("\n")),
          body: (.body_lines | join("\n"))
        };
  map(select(.from == $agent))
  | map(. + split_text(.text))
  | map(select((.text | is_idle) | not))
  | map(select(.text | is_event))
  | sort_by(.timestamp)
  | if length == 0 then
      empty
    elif $latest == "1" then
      .[-1] as $msg
      | (if $msg.body == "" then $msg.text else $msg.body end) as $content
      | [
          ("event_type=" + $event),
          ("agent=" + $msg.from),
          ("timestamp=" + $msg.timestamp),
          "content_start",
          $content
        ]
      | join("\n")
    else
      map(
        . as $msg
        | (if $msg.body == "" then $msg.text else $msg.body end) as $content
        | [
            ("event_type=" + $event),
            ("agent=" + $msg.from),
            ("timestamp=" + $msg.timestamp),
            "content_start",
            $content
          ]
        | join("\n")
      )
      | join("\n---\n")
    end
' "$LEAD_INBOX"
)"

if [[ -z "$OUTPUT" ]]; then
  echo "event_type=$EVENT_TYPE" >&2
  echo "event_status=missing" >&2
  exit 3
fi

printf '%s\n' "$OUTPUT"
