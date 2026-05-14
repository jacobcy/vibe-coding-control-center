#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/lib.sh"

show_usage() {
  cat <<'EOF'
Usage:
  agent-exist.sh
  agent-exist.sh <agent_name>
  agent-exist.sh --group <name>

Behavior:
  - Without agent_name: list all agents with definition/inbox/pane status.
  - With agent_name: check existence of definition, inbox, and tmux pane for that agent.
  - Also searches team-lead inbox for the latest 【agent_ready】 event from that agent.

Checks (in order):
  1. definition: .claude/agents/<agent_type>.md exists
  2. inbox: ~/.claude/teams/<group>/inboxes/<agent_name>.json exists
  3. pane: tmux pane title contains agent_type and current command is "claude"
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

if [[ -z "$AGENT_NAME" ]]; then
  echo "group=$GROUP_NAME"
  echo "team_inbox_dir=$(team_inbox_dir "$GROUP_NAME")"
  print_agent_table_header
  while IFS= read -r agent_name; do
    print_agent_row "$agent_name" "$GROUP_NAME"
  done < <(defined_agent_names)
  exit 0
fi

assert_defined_agent "$AGENT_NAME"
print_agent_table_header
print_agent_row "$AGENT_NAME" "$GROUP_NAME"

# Output handshake state based on lead inbox status
#
# States:
#   waiting — Lead inbox does not exist, team not initialized
#   missing  — Lead inbox exists but agent has not sent 【agent_ready】
#   found    — Agent has sent 【agent_ready】 event
#
# Semantics:
#   waiting → team-lead should wait for team initialization
#   missing → agent not ready, continue waiting or respawn
#   found   → agent ready, proceed with task assignment
LEAD_INBOX="$(lead_inbox_path "$GROUP_NAME")"
if [[ ! -f "$LEAD_INBOX" ]]; then
  echo "ready_event=waiting"
  echo "lead inbox not found: $LEAD_INBOX" >&2
  exit 0
fi

jq -r \
  --arg agent "$AGENT_NAME" \
  '
  map(select(.from == $agent))
  | map(select(.text | startswith("【agent_ready】")))
  | sort_by(.timestamp)
  | if length == 0 then
      "ready_event=missing"
    else
      .[-1] as $msg
      | [
          "ready_event=found",
          ("from=" + $msg.from),
          ("timestamp=" + $msg.timestamp),
          ("text=" + ($msg.text | gsub("\n"; "\\n")))
        ]
      | join("\n")
    end
' "$LEAD_INBOX"
