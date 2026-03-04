#!/usr/bin/env zsh
# Manual Provider Adapter - 人工降级兜底 adapter

ADAPTER_NAME="manual"
ADAPTER_VERSION="1.0.0"
ADAPTER_DESCRIPTION="Manual fallback provider for human intervention"

# provider_route(task) -> bool
provider_route() {
  local task="$1"
  echo "true"
  return 0
}

# provider_start(task, context) -> provider_ref
provider_start() {
  local task="$1"
  local context="$2"
  
  local task_id
  task_id=$(echo "$task" | jq -r '.id // "unknown"')
  local timestamp
  timestamp=$(date +%s)
  
  local provider_ref="manual:${task_id}_${timestamp}"
  
  local state_file="/tmp/vibe-manual-${provider_ref//:/_}.json"
  
  cat > "$state_file" <<EOFSTATE
{
  "provider": "manual",
  "task_id": "$task_id",
  "ref": "$provider_ref",
  "state": "in_progress",
  "started_at": "$(date -Iseconds)",
  "task": $task,
  "context": $context
}
EOFSTATE
  
  echo "$provider_ref"
  return 0
}

# provider_status(provider_ref) -> {state, metadata}
provider_status() {
  local provider_ref="$1"
  
  local state_file="/tmp/vibe-manual-${provider_ref//:/_}.json"
  
  if [[ ! -f "$state_file" ]]; then
    echo '{"state": "failed", "metadata": {"error": "state file not found"}}'
    return 1
  fi
  
  local state
  state=$(jq -r '.state' "$state_file")
  
  echo "{\"state\": \"$state\", \"metadata\": {\"ref\": \"$provider_ref\"}}"
  return 0
}

# provider_complete(provider_ref) -> {result, artifacts}
provider_complete() {
  local provider_ref="$1"
  
  local state_file="/tmp/vibe-manual-${provider_ref//:/_}.json"
  
  if [[ ! -f "$state_file" ]]; then
    echo '{"result": "failed", "artifacts": [], "error": "state file not found"}'
    return 1
  fi
  
  local timestamp
  timestamp=$(date -Iseconds)
  
  local updated_json
  updated_json=$(jq ".state = \"done\" | .completed_at = \"$timestamp\"" "$state_file")
  echo "$updated_json" > "$state_file"
  
  echo '{"result": "success", "artifacts": [], "message": "Manual task completed"}'
  return 0
}

# Adapter 入口
provider_adapter() {
  local action="$1"
  shift

  case "$action" in
    route)
      provider_route "$@"
      ;;
    start)
      provider_start "$@"
      ;;
    status)
      provider_status "$@"
      ;;
    complete)
      provider_complete "$@"
      ;;
    *)
      echo "{\"error\": \"Unknown action: $action\"}"
      return 1
      ;;
  esac
}

# 测试入口
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  echo "Manual Provider Adapter v$ADAPTER_VERSION"
fi
