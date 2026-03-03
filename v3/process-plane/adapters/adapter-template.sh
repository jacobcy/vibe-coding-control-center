#!/usr/bin/env zsh
# Provider Adapter Template
# 所有 provider adapter 必须实现此接口

# Adapter 元数据
ADAPTER_NAME="<provider-name>"
ADAPTER_VERSION="1.0.0"
ADAPTER_DESCRIPTION="<provider description>"

# Provider Adapter 接口实现
# 每个方法必须返回标准格式

# route(task) -> bool
# 决定是否处理该任务
# 输入: task - 任务上下文 (JSON)
# 输出: "true" 或 "false"
provider_route() {
  local task="$1"
  # 子类实现：判断是否接受该任务
  echo "false"
}

# start(task, context) -> provider_ref
# 启动 provider 执行
# 输入: task - 任务上下文 (JSON)
#       context - 执行上下文 (JSON)
# 输出: provider_ref (格式: <provider>:<task_id>)
provider_start() {
  local task="$1"
  local context="$2"
  # 子类实现：启动执行
  echo "${ADAPTER_NAME}:error:not_implemented"
}

# status(provider_ref) -> {state, metadata}
# 查询 provider 执行状态
# 输入: provider_ref - provider 引用
# 输出: JSON {state: "in_progress"|"done"|"failed", metadata: {...}}
provider_status() {
  local provider_ref="$1"
  # 子类实现：查询状态
  echo '{"state": "failed", "metadata": {"error": "not implemented"}}'
}

# complete(provider_ref) -> {result, artifacts}
# 完成 provider 执行并清理资源
# 输入: provider_ref - provider 引用
# 输出: JSON {result: "success"|"failed", artifacts: [...]}
provider_complete() {
  local provider_ref="$1"
  # 子类实现：完成清理
  echo '{"result": "failed", "artifacts": [], "error": "not implemented"}'
}

# Adapter 入口（路由器调用）
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

# 如果直接执行此脚本，显示用法
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  echo "Provider Adapter Template"
  echo "Usage: source this file and override provider_* functions"
  echo ""
  echo "Required methods:"
  echo "  provider_route(task) -> bool"
  echo "  provider_start(task, context) -> provider_ref"
  echo "  provider_status(provider_ref) -> {state, metadata}"
  echo "  provider_complete(provider_ref) -> {result, artifacts}"
fi
