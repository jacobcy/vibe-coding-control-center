#!/usr/bin/env zsh
# Provider Fallback Mechanism - Provider 降级机制

# 降级路径：Supervisor → OpenSpec → Kiro → Manual
FALLBACK_PATH=("supervisor" "openspec" "kiro" "manual")

# 降级历史记录
FALLBACK_HISTORY_DIR="${FALLBACK_HISTORY_DIR:-/tmp/vibe-fallback-history}"

# pp_fallback_find_available(failed_provider) -> provider_name
# 找到下一个可用的 provider
pp_fallback_find_available() {
  local failed_provider="$1"
  
  # 找到 failed_provider 在降级路径中的位置
  local start_index=-1
  for i in "${!FALLBACK_PATH[@]}"; do
    if [[ "${FALLBACK_PATH[$i]}" == "$failed_provider" ]]; then
      start_index=$((i + 1))
      break
    fi
  done
  
  # 如果未找到，从第一个开始
  if [[ $start_index -eq -1 ]]; then
    start_index=0
  fi
  
  # 从下一个位置开始查找可用的 provider
  for i in "${!FALLBACK_PATH[@]}"; do
    if [[ $i -lt $start_index ]]; then
      continue
    fi
    
    local candidate="${FALLBACK_PATH[$i]}"
    
    # 检查是否可用
    if pp_adapter_exists "$candidate" && pp_adapter_validate "$candidate"; then
      echo "$candidate"
      return 0
    fi
  done
  
  # 最终降级到 manual
  echo "manual"
  return 0
}

# pp_fallback_notify(provider_from, provider_to, reason, task_id?) -> void
# 通知用户降级事件
pp_fallback_notify() {
  local provider_from="$1"
  local provider_to="$2"
  local reason="$3"
  local task_id="${4:-unknown}"  # 可选的 task_id

  local message="Provider fallback: $provider_from → $provider_to (reason: $reason)"

  # 记录到日志
  echo "[FALLBACK] $message" >&2

  # 写入降级历史
  pp_fallback_record "$provider_from" "$provider_to" "$reason" "$task_id"
}

# pp_fallback_record(provider_from, provider_to, reason, task_id?) -> void
# 记录降级历史
pp_fallback_record() {
  local provider_from="$1"
  local provider_to="$2"
  local reason="$3"
  local task_id="${4:-unknown}"  # 可选的 task_id

  mkdir -p "$FALLBACK_HISTORY_DIR"

  # 使用纳秒确保唯一性，避免同一秒内覆盖
  local timestamp
  timestamp=$(date +%Y%m%d_%H%M%S_%N)

  # 如果不支持 %N（纳秒），添加随机数作为后备
  if [[ "$timestamp" == *"%N"* ]]; then
    timestamp="$(date +%Y%m%d_%H%M%S)_$RANDOM"
  fi

  local record_file="$FALLBACK_HISTORY_DIR/fallback_${timestamp}.json"

  cat > "$record_file" <<EOF
{
  "timestamp": "$(date -Iseconds)",
  "from": "$provider_from",
  "to": "$provider_to",
  "reason": "$reason",
  "task_id": "$task_id"
}
EOF

  echo "Fallback recorded: $record_file" >&2
}

# pp_fallback_history() -> [records]
# 查询降级历史
pp_fallback_history() {
  local limit="${1:-10}"
  
  if [[ ! -d "$FALLBACK_HISTORY_DIR" ]]; then
    echo "[]"
    return 0
  fi
  
  # 获取最近的记录
  local files
  files=$(ls -t "$FALLBACK_HISTORY_DIR"/*.json 2>/dev/null | head -n "$limit")
  
  if [[ -z "$files" ]]; then
    echo "[]"
    return 0
  fi
  
  # 合并为 JSON 数组
  local records="["
  local first=true
  
  while IFS= read -r file; do
    if [[ -n "$file" ]]; then
      if [[ "$first" == "true" ]]; then
        first=false
      else
        records+=","
      fi
      records+=$(cat "$file")
    fi
  done <<< "$files"
  
  records+="]"
  
  echo "$records"
}

# pp_fallback_recover(provider_ref, target_provider) -> {success: bool, new_ref: string}
# 手动恢复到高级 provider
pp_fallback_recover() {
  local provider_ref="$1"
  local target_provider="$2"
  
  # 解析当前 provider_ref
  local current_provider task_id
  IFS=':' read -r current_provider task_id <<< "$provider_ref"
  
  # 检查目标 provider 是否可用
  if ! pp_adapter_exists "$target_provider"; then
    echo "{\"success\": false, \"error\": \"Target provider not available: $target_provider\"}"
    return 1
  fi
  
  # 检查目标 provider 是否优先级更高
  local current_index=-1
  local target_index=-1
  
  for i in "${!FALLBACK_PATH[@]}"; do
    if [[ "${FALLBACK_PATH[$i]}" == "$current_provider" ]]; then
      current_index=$i
    fi
    if [[ "${FALLBACK_PATH[$i]}" == "$target_provider" ]]; then
      target_index=$i
    fi
  done
  
  if [[ $target_index -ge $current_index ]]; then
    echo "{\"success\": false, \"error\": \"Target provider is not higher priority\"}"
    return 1
  fi
  
  # TODO: 实现状态迁移（保留已完成的进度）
  # 当前版本只返回新的 provider_ref
  
  local new_ref="${target_provider}:${task_id}"
  
  echo "{\"success\": true, \"new_ref\": \"$new_ref\"}"
  return 0
}

# pp_fallback_detect_loop(provider_ref) -> bool
# 检测降级循环
pp_fallback_detect_loop() {
  local provider_ref="$1"
  
  # 解析 provider_ref
  local provider task_id
  IFS=':' read -r provider task_id <<< "$provider_ref"
  
  # 检查历史记录中是否有循环
  local history
  history=$(pp_fallback_history 20)
  
  local recent_providers
  recent_providers=$(echo "$history" | jq -r '.[].from' | grep -c "^$provider$" || echo "0")
  
  # 如果同一个 provider 出现多次，可能存在循环
  if [[ $recent_providers -ge 3 ]]; then
    echo "true"
    return 0
  fi
  
  echo "false"
  return 0
}

# pp_fallback_limit_attempts(task_id, max_attempts) -> bool
# 限制特定任务的降级尝试次数
pp_fallback_limit_attempts() {
  local task_id="$1"
  local max_attempts="${2:-3}"

  # 检查该任务的降级历史
  local history
  history=$(pp_fallback_history 100)

  # 统计该 task_id 的降级次数
  local attempt_count
  attempt_count=$(echo "$history" | jq -r --arg task "$task_id" '[.[] | select(.task_id == $task)] | length')

  if [[ $attempt_count -ge $max_attempts ]]; then
    echo "true"  # 已达上限
    return 0
  fi

  echo "false"  # 未达上限
  return 0
}

# 加载依赖
# 兼容 zsh 和 bash 的脚本目录定位
if [[ -n "${BASH_SOURCE[0]:-}" ]]; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
elif [[ -n "${(%):-%N}" ]]; then
  # zsh 方式
  SCRIPT_DIR="${0:A:h}"
else
  # 最后的兜底
  SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
fi

if [[ -f "$SCRIPT_DIR/adapter-loader.sh" ]]; then
  source "$SCRIPT_DIR/adapter-loader.sh"
fi

# 入口点
# 兼容 zsh 和 bash 的入口检测
if [[ -n "${BASH_SOURCE[0]:-}" ]]; then
  [[ "${BASH_SOURCE[0]}" == "${0}" ]]
elif [[ -n "${ZSH_VERSION:-}" ]]; then
  [[ "${(%):-%N}" == "${0}" ]]
else
  false
fi && echo "Provider Fallback Mechanism" && echo "Fallback path: ${FALLBACK_PATH[*]}"
