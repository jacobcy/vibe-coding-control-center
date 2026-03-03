#!/usr/bin/env zsh
# Supervisor Provider Adapter - 六层流程模型 adapter

ADAPTER_NAME="supervisor"
ADAPTER_VERSION="1.0.0"
ADAPTER_DESCRIPTION="Supervisor adapter with six-layer flow model"

# 六层流程阶段
SUPERVISOR_PHASES=("intake" "scoping" "design" "plan" "execution" "audit")

# provider_route(task) -> bool
# 接受高风险任务
provider_route() {
  local task="$1"
  
  local task_type task_risk
  task_type=$(echo "$task" | jq -r '.type // "unknown"')
  task_risk=$(echo "$task" | jq -r '.risk // "medium"')
  
  # 接受高风险任务或明确指定 supervisor 的任务
  if [[ "$task_risk" == "high" || "$task_type" == "supervised" ]]; then
    echo "true"
    return 0
  fi
  
  echo "false"
  return 0
}

# provider_start(task, context) -> provider_ref
# 启动六层流程
provider_start() {
  local task="$1"
  local context="$2"
  
  local task_id
  task_id=$(echo "$task" | jq -r '.id // "unknown"')
  
  local timestamp
  timestamp=$(date +%s)
  local provider_ref="supervisor:${task_id}_${timestamp}"
  
  # 初始化六层流程状态
  local state_file="/tmp/vibe-supervisor-${provider_ref//:/_}.json"
  
  cat > "$state_file" <<EOFSTATE
{
  "provider": "supervisor",
  "task_id": "$task_id",
  "ref": "$provider_ref",
  "state": "in_progress",
  "phase": "intake",
  "phase_index": 0,
  "started_at": "$(date -Iseconds)",
  "task": $task,
  "context": $context,
  "phases": {
    "intake": {"status": "in_progress", "completed_at": null},
    "scoping": {"status": "pending", "completed_at": null},
    "design": {"status": "pending", "completed_at": null},
    "plan": {"status": "pending", "completed_at": null},
    "execution": {"status": "pending", "completed_at": null},
    "audit": {"status": "pending", "completed_at": null}
  }
}
EOFSTATE
  
  echo "$provider_ref"
  return 0
}

# provider_status(provider_ref) -> {state, metadata}
# 查询六层流程状态
provider_status() {
  local provider_ref="$1"
  
  local state_file="/tmp/vibe-supervisor-${provider_ref//:/_}.json"
  
  if [[ ! -f "$state_file" ]]; then
    echo '{"state": "failed", "metadata": {"error": "state file not found"}}'
    return 1
  fi
  
  local state phase
  state=$(jq -r '.state' "$state_file")
  phase=$(jq -r '.phase' "$state_file")
  
  # 返回聚合状态（不暴露具体阶段）
  echo "{\"state\": \"$state\", \"metadata\": {\"ref\": \"$provider_ref\", \"provider\": \"supervisor\", \"current_phase\": \"$phase\"}}"
  return 0
}

# provider_complete(provider_ref) -> {result, artifacts}
# 完成六层流程
provider_complete() {
  local provider_ref="$1"
  
  local state_file="/tmp/vibe-supervisor-${provider_ref//:/_}.json"
  
  if [[ ! -f "$state_file" ]]; then
    echo '{"result": "failed", "artifacts": [], "error": "state file not found"}'
    return 1
  fi
  
  # 更新状态为 done
  local timestamp
  timestamp=$(date -Iseconds)
  
  local updated_json
  updated_json=$(jq ".state = \"done\" | .completed_at = \"$timestamp\" | .phase = \"completed\"" "$state_file")
  echo "$updated_json" > "$state_file"
  
  echo '{"result": "success", "artifacts": [], "message": "Supervisor six-layer flow completed"}'
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
  echo "Supervisor Provider Adapter v$ADAPTER_VERSION"
  echo "Six-layer phases: ${SUPERVISOR_PHASES[*]}"
fi
