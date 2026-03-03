#!/usr/bin/env zsh
# Provider Router - 统一的 provider 路由器

# Provider Router 核心接口

# route(task) -> provider_name
# 根据任务上下文选择合适的 provider
# 输入: task - 任务上下文 (JSON)
# 输出: provider_name (如 "openspec", "supervisor", "kiro", "manual")
pp_route() {
  local task="$1"
  
  # 1. 加载路由策略
  local strategy_result
  strategy_result=$(pp_strategy_evaluate "$task")
  
  if [[ $? -ne 0 ]]; then
    echo "manual"  # 降级到 manual
    return 0
  fi
  
  # 2. 获取推荐的 provider
  local provider_name
  provider_name=$(echo "$strategy_result" | jq -r '.provider')
  
  # 3. 验证 provider 是否可用
  if ! pp_adapter_validate "$provider_name"; then
    # 4. 降级处理
    provider_name=$(pp_fallback_find_available "$provider_name")
  fi
  
  echo "$provider_name"
  return 0
}

# start(task, context) -> provider_ref
# 启动 provider 执行并返回 provider_ref
# 输入: task - 任务上下文 (JSON)
#       context - 执行上下文 (JSON)
# 输出: provider_ref (格式: <provider>:<task_id>)
pp_start() {
  local task="$1"
  local context="$2"
  
  # 1. 路由到合适的 provider
  local provider_name
  provider_name=$(pp_route "$task")
  
  if [[ -z "$provider_name" ]]; then
    echo "error:no_provider:$(date +%s)"
    return 1
  fi
  
  # 2. 调用 provider adapter 的 start 方法
  local provider_ref
  provider_ref=$(pp_adapter_call "$provider_name" start "$task" "$context")
  
  if [[ $? -ne 0 ]]; then
    echo "error:start_failed:$(date +%s)"
    return 1
  fi
  
  # 3. 记录执行状态
  pp_state_save "$provider_ref" "in_progress" "$provider_name"
  
  echo "$provider_ref"
  return 0
}

# status(provider_ref) -> {state, metadata}
# 查询 provider 执行状态
# 输入: provider_ref - provider 引用
# 输出: JSON {state: "in_progress"|"done"|"failed", metadata: {...}}
pp_status() {
  local provider_ref="$1"
  
  # 1. 解析 provider_ref
  local provider_name task_id
  IFS=':' read -r provider_name task_id <<< "$provider_ref"
  
  # 2. 调用 provider adapter 的 status 方法
  local status_json
  status_json=$(pp_adapter_call "$provider_name" status "$provider_ref")
  
  if [[ $? -ne 0 ]]; then
    echo '{"state": "failed", "metadata": {"error": "status query failed"}}'
    return 1
  fi
  
  # 3. 聚合状态（不暴露 provider 内部步骤）
  local aggregated_status
  aggregated_status=$(pp_aggregate_status "$status_json")
  
  echo "$aggregated_status"
  return 0
}

# complete(provider_ref) -> {result, artifacts}
# 完成 provider 执行并清理资源
# 输入: provider_ref - provider 引用
# 输出: JSON {result: "success"|"failed", artifacts: [...]}
pp_complete() {
  local provider_ref="$1"
  
  # 1. 解析 provider_ref
  local provider_name task_id
  IFS=':' read -r provider_name task_id <<< "$provider_ref"
  
  # 2. 调用 provider adapter 的 complete 方法
  local complete_json
  complete_json=$(pp_adapter_call "$provider_name" complete "$provider_ref")
  
  if [[ $? -ne 0 ]]; then
    echo '{"result": "failed", "artifacts": [], "error": "complete failed"}'
    return 1
  fi
  
  # 3. 清理状态
  pp_state_delete "$provider_ref"
  
  echo "$complete_json"
  return 0
}

# Helper: 聚合 provider 状态
# 将 provider 内部状态聚合为 in_progress/done
pp_aggregate_status() {
  local status_json="$1"
  
  local state
  state=$(echo "$status_json" | jq -r '.state')
  
  # 简单聚合：in_progress/done/failed
  # 不暴露 provider 内部步骤（如 Supervisor 的 Scoping/Design 等）
  case "$state" in
    in_progress|pending|running|intake|scoping|design|plan|execution)
      echo '{"state": "in_progress", "metadata": {}}'
      ;;
    done|completed|closed)
      echo '{"state": "done", "metadata": {}}'
      ;;
    failed|error)
      echo '{"state": "failed", "metadata": {}}'
      ;;
    *)
      echo '{"state": "in_progress", "metadata": {}}'
      ;;
  esac
}

# 加载依赖模块
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source 策略引擎（如果存在）
if [[ -f "$SCRIPT_DIR/strategy.sh" ]]; then
  source "$SCRIPT_DIR/strategy.sh"
else
  # 临时实现（后续会被 strategy.sh 替换）
  pp_strategy_evaluate() {
    local task="$1"
    # 默认策略：spec-driven → openspec, 其他 → manual
    local task_type
    task_type=$(echo "$task" | jq -r '.type // "unknown"')
    
    case "$task_type" in
      spec-driven)
        echo '{"provider": "openspec"}'
        ;;
      *)
        echo '{"provider": "manual"}'
        ;;
    esac
  }
fi

# Source 降级机制（如果存在）
if [[ -f "$SCRIPT_DIR/fallback.sh" ]]; then
  source "$SCRIPT_DIR/fallback.sh"
else
  # 临时实现（后续会被 fallback.sh 替换）
  pp_fallback_find_available() {
    local failed_provider="$1"
    # 简单降级：openspec → manual
    case "$failed_provider" in
      openspec|supervisor|kiro)
        echo "manual"
        ;;
      *)
        echo "manual"
        ;;
    esac
  }
fi

# Adapter 辅助函数（临时实现，后续会被 adapter 加载机制替换）
pp_adapter_validate() {
  local provider_name="$1"
  # 检查 adapter 目录是否存在
  [[ -d "$SCRIPT_DIR/adapters/$provider_name" ]]
}

pp_adapter_call() {
  local provider_name="$1"
  local action="$2"
  shift 2
  
  # 调用 adapter 脚本
  local adapter_script="$SCRIPT_DIR/adapters/$provider_name/adapter.sh"
  
  if [[ ! -f "$adapter_script" ]]; then
    return 1
  fi
  
  source "$adapter_script"
  provider_adapter "$action" "$@"
}

# 状态管理（临时实现，使用文件存储）
PP_STATE_DIR="${PP_STATE_DIR:-/tmp/vibe-process-plane-state}"

pp_state_save() {
  local provider_ref="$1"
  local state="$2"
  local provider="$3"
  
  mkdir -p "$PP_STATE_DIR"
  echo "{\"provider\": \"$provider\", \"state\": \"$state\", \"ref\": \"$provider_ref\"}" > "$PP_STATE_DIR/${provider_ref//:/_}.json"
}

pp_state_delete() {
  local provider_ref="$1"
  rm -f "$PP_STATE_DIR/${provider_ref//:/_}.json"
}

# 入口点
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  echo "Provider Router - Use pp_route/pp_start/pp_status/pp_complete functions"
fi
