#!/usr/bin/env zsh
# OpenSpec Provider Adapter - spec-driven 变更管理 adapter

ADAPTER_NAME="openspec"
ADAPTER_VERSION="1.0.0"
ADAPTER_DESCRIPTION="OpenSpec adapter for spec-driven change management"

# provider_route(task) -> bool
# 接受 spec-driven 类型的任务
provider_route() {
  local task="$1"
  
  local task_type
  task_type=$(echo "$task" | jq -r '.type // "unknown"')
  
  # 只接受 spec-driven 任务
  if [[ "$task_type" == "spec-driven" ]]; then
    echo "true"
    return 0
  fi
  
  echo "false"
  return 0
}

# provider_start(task, context) -> provider_ref
# 调用 openspec 命令启动执行
provider_start() {
  local task="$1"
  local context="$2"
  
  local task_id change_name
  task_id=$(echo "$task" | jq -r '.id // "unknown"')
  change_name=$(echo "$task" | jq -r '.change_name // "unknown"')
  
  local timestamp
  timestamp=$(date +%s)
  local provider_ref="openspec:${task_id}_${timestamp}"
  
  # 创建状态文件
  local state_file="/tmp/vibe-openspec-${provider_ref//:/_}.json"
  
  cat > "$state_file" <<EOFSTATE
{
  "provider": "openspec",
  "task_id": "$task_id",
  "change_name": "$change_name",
  "ref": "$provider_ref",
  "state": "in_progress",
  "started_at": "$(date -Iseconds)",
  "task": $task,
  "context": $context
}
EOFSTATE
  
  # TODO: 实际调用 openspec 命令
  # 当前版本只是模拟，后续集成真实的 openspec CLI
  # openspec apply --change "$change_name"
  
  echo "$provider_ref"
  return 0
}

# provider_status(provider_ref) -> {state, metadata}
# 查询 openspec 状态
provider_status() {
  local provider_ref="$1"
  
  local state_file="/tmp/vibe-openspec-${provider_ref//:/_}.json"
  
  if [[ ! -f "$state_file" ]]; then
    echo '{"state": "failed", "metadata": {"error": "state file not found"}}'
    return 1
  fi
  
  local state
  state=$(jq -r '.state' "$state_file")
  
  # TODO: 查询真实的 openspec 状态
  # 当前版本返回文件中保存的状态
  
  echo "{\"state\": \"$state\", \"metadata\": {\"ref\": \"$provider_ref\", \"provider\": \"openspec\"}}"
  return 0
}

# provider_complete(provider_ref) -> {result, artifacts}
# 完成 openspec 执行
provider_complete() {
  local provider_ref="$1"
  
  local state_file="/tmp/vibe-openspec-${provider_ref//:/_}.json"
  
  if [[ ! -f "$state_file" ]]; then
    echo '{"result": "failed", "artifacts": [], "error": "state file not found"}'
    return 1
  fi
  
  # 更新状态为 done
  local timestamp
  timestamp=$(date -Iseconds)
  
  local updated_json
  updated_json=$(jq ".state = \"done\" | .completed_at = \"$timestamp\"" "$state_file")
  echo "$updated_json" > "$state_file"
  
  # TODO: 清理 openspec 资源
  # 当前版本只是更新状态文件
  
  echo '{"result": "success", "artifacts": [], "message": "OpenSpec task completed"}'
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
  echo "OpenSpec Provider Adapter v$ADAPTER_VERSION"
fi
