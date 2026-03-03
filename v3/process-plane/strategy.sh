#!/usr/bin/env zsh
# Routing Strategy Engine - 智能路由策略引擎

# pp_strategy_evaluate(task) -> {provider, reason}
# 评估任务并返回推荐的 provider
pp_strategy_evaluate() {
  local task="$1"
  
  # 提取任务属性
  local task_type task_risk ai_resources
  
  task_type=$(echo "$task" | jq -r '.type // "unknown"')
  task_risk=$(echo "$task" | jq -r '.risk // "medium"')
  ai_resources=$(echo "$task" | jq -r '.resources.ai // "unknown"')
  
  # 应用路由规则
  local provider reason
  
  # 规则 1: spec-driven + 低风险 → OpenSpec
  if [[ "$task_type" == "spec-driven" && "$task_risk" == "low" ]]; then
    provider="openspec"
    reason="spec-driven task with low risk"
  
  # 规则 2: spec-driven + 高风险 → Supervisor
  elif [[ "$task_type" == "spec-driven" && "$task_risk" == "high" ]]; then
    provider="supervisor"
    reason="spec-driven task with high risk requires thorough review"
  
  # 规则 3: spec-driven + 资源不足 → Manual
  elif [[ "$task_type" == "spec-driven" && "$ai_resources" == "insufficient" ]]; then
    provider="manual"
    reason="insufficient AI resources, fallback to manual"
  
  # 规则 4: ad-hoc + 低风险 + AI 充足 → Kiro
  elif [[ "$task_type" == "ad-hoc" && "$task_risk" == "low" && "$ai_resources" == "sufficient" ]]; then
    provider="kiro"
    reason="ad-hoc task with sufficient AI resources"
  
  # 规则 5: ad-hoc + 高风险 → Supervisor
  elif [[ "$task_type" == "ad-hoc" && "$task_risk" == "high" ]]; then
    provider="supervisor"
    reason="ad-hoc task with high risk requires supervision"
  
  # 默认: Manual
  else
    provider="manual"
    reason="default fallback to manual mode"
  fi
  
  # 记录路由决策（透明度）
  pp_strategy_log_decision "$task_type" "$task_risk" "$ai_resources" "$provider" "$reason"
  
  echo "{\"provider\": \"$provider\", \"reason\": \"$reason\"}"
  return 0
}

# pp_strategy_log_decision(task_type, risk, resources, provider, reason) -> void
# 记录路由决策（透明度）
pp_strategy_log_decision() {
  local task_type="$1"
  local risk="$2"
  local resources="$3"
  local provider="$4"
  local reason="$5"
  
  local log_file="${PP_STRATEGY_LOG:-/tmp/vibe-strategy.log}"
  local timestamp
  timestamp=$(date -Iseconds)
  
  echo "{\"timestamp\": \"$timestamp\", \"task_type\": \"$task_type\", \"risk\": \"$risk\", \"resources\": \"$resources\", \"provider\": \"$provider\", \"reason\": \"$reason\"}" >> "$log_file"
}

# pp_strategy_dry_run(task) -> {provider, reason, dry_run: true}
# Dry-run 模式：预览路由决策但不执行
pp_strategy_dry_run() {
  local task="$1"
  
  local result
  result=$(pp_strategy_evaluate "$task")
  
  # 添加 dry_run 标记
  echo "$result" | jq '. + {dry_run: true}'
}

# pp_strategy_test(task) -> {provider, reason, valid: bool}
# 测试路由策略
pp_strategy_test() {
  local task="$1"
  
  local result
  result=$(pp_strategy_evaluate "$task")
  
  local provider
  provider=$(echo "$result" | jq -r '.provider')
  
  # 验证 provider 是否可用
  local valid="false"
  if pp_adapter_exists "$provider" 2>/dev/null; then
    valid="true"
  fi
  
  echo "$result" | jq ". + {valid: $valid}"
}

# pp_strategy_validate_rules() -> {valid: bool, issues: []}
# 验证路由规则是否覆盖所有场景
pp_strategy_validate_rules() {
  local issues=()
  
  # 测试各种组合
  local test_cases=(
    '{"type":"spec-driven","risk":"low"}'
    '{"type":"spec-driven","risk":"high"}'
    '{"type":"ad-hoc","risk":"low"}'
    '{"type":"unknown"}'
  )
  
  for test_case in "${test_cases[@]}"; do
    local result
    result=$(pp_strategy_evaluate "$test_case")
    
    local provider
    provider=$(echo "$result" | jq -r '.provider')
    
    if [[ -z "$provider" || "$provider" == "null" ]]; then
      issues+=("No provider for: $test_case")
    fi
  done
  
  if [[ ${#issues[@]} -eq 0 ]]; then
    echo '{"valid": true, "issues": []}'
  else
    local issues_json
    issues_json=$(printf '%s\n' "${issues[@]}" | jq -R . | jq -s .)
    echo "{\"valid\": false, \"issues\": $issues_json}"
  fi
}

# 自定义路由规则支持（未实现）
# TODO: 实现用户自定义路由规则覆盖默认策略
pp_strategy_add_rule() {
  echo '{"error": "Custom rules not yet implemented", "status": "not_implemented"}' >&2
  return 2  # 返回 2 表示"未实现"
}

# Provider 优先级配置（未实现）
# TODO: 实现基于用户配置的 provider 优先级
pp_strategy_set_priority() {
  echo '{"error": "Priority configuration not yet implemented", "status": "not_implemented"}' >&2
  return 2  # 返回 2 表示"未实现"
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
fi && {
  echo "Routing Strategy Engine - Testing..."
  pp_strategy_validate_rules
}
