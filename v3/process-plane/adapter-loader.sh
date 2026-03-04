#!/usr/bin/env zsh
# Adapter Loader - 动态加载和验证 provider adapters

# 兼容 zsh 和 bash 的脚本目录定位
if [[ -n "${BASH_SOURCE[0]:-}" ]]; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
elif [[ -n "${ZSH_VERSION:-}" ]]; then
  # zsh 方式：使用 %x 获取当前脚本路径（即使被 source）
  SCRIPT_DIR="${${(%):-%x}:A:h}"
else
  # 最后的兜底
  SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
fi

ADAPTERS_DIR="$SCRIPT_DIR/adapters"

# 使用文件存储注册的 adapters（兼容 bash/zsh）
REGISTERED_ADAPTERS_FILE="/tmp/vibe-registered-adapters.txt"

# pp_adapter_register_all() -> void
# 扫描并注册所有可用的 adapter
pp_adapter_register_all() {
  if [[ ! -d "$ADAPTERS_DIR" ]]; then
    echo "Error: Adapters directory not found: $ADAPTERS_DIR" >&2
    return 1
  fi
  
  # 清空注册列表
  > "$REGISTERED_ADAPTERS_FILE"
  
  # 扫描 adapters 目录
  for adapter_dir in "$ADAPTERS_DIR"/*; do
    if [[ -d "$adapter_dir" ]]; then
      local adapter_name
      adapter_name=$(basename "$adapter_dir")
      
      # 验证并注册
      if pp_adapter_validate "$adapter_name" 2>/dev/null; then
        echo "$adapter_name" >> "$REGISTERED_ADAPTERS_FILE"
        echo "Registered adapter: $adapter_name" >&2
      fi
    fi
  done
}

# pp_adapter_validate(provider_name) -> bool
# 验证 adapter 是否实现了必需的接口
pp_adapter_validate() {
  local provider_name="$1"
  local adapter_script="$ADAPTERS_DIR/$provider_name/adapter.sh"

  # 检查 adapter 脚本是否存在且可执行
  if [[ ! -f "$adapter_script" || ! -x "$adapter_script" ]]; then
    echo "Error: Adapter script not found or not executable: $adapter_script" >&2
    return 1
  fi

  # 验证必需的接口函数
  if ! grep -q "provider_adapter" "$adapter_script" 2>/dev/null; then
    echo "Error: provider_adapter function not found in $adapter_script" >&2
    return 1
  fi

  # 验证是否包含必需的 action 处理
  local required_actions=("route" "start" "status" "complete")
  local missing_actions=()

  for action in "${required_actions[@]}"; do
    if ! grep -q "\"$action\"" "$adapter_script" 2>/dev/null && \
       ! grep -q "'$action'" "$adapter_script" 2>/dev/null && \
       ! grep -q "\b$action\b" "$adapter_script" 2>/dev/null; then
      missing_actions+=("$action")
    fi
  done

  if [[ ${#missing_actions[@]} -gt 0 ]]; then
    echo "Warning: Adapter $provider_name may be missing actions: ${missing_actions[*]}" >&2
    # 不返回错误，只警告（因为可能是通过 case 语句实现的）
  fi

  return 0
}

# pp_adapter_call(provider_name, action, ...args) -> output
pp_adapter_call() {
  local provider_name="$1"
  local action="$2"
  shift 2
  
  local adapter_script="$ADAPTERS_DIR/$provider_name/adapter.sh"
  
  if [[ ! -f "$adapter_script" ]]; then
    echo "{\"error\": \"Adapter not found: $provider_name\"}"
    return 1
  fi
  
  # 调用 adapter（使用 subshell）
  (
    source "$adapter_script"
    provider_adapter "$action" "$@"
  )
}

# pp_adapter_list() -> [provider_names]
pp_adapter_list() {
  if [[ -f "$REGISTERED_ADAPTERS_FILE" ]]; then
    cat "$REGISTERED_ADAPTERS_FILE"
  fi
}

# pp_adapter_exists(provider_name) -> bool
pp_adapter_exists() {
  local provider_name="$1"
  
  if [[ -f "$REGISTERED_ADAPTERS_FILE" ]]; then
    grep -q "^${provider_name}$" "$REGISTERED_ADAPTERS_FILE"
    return $?
  fi
  
  return 1
}

# 初始化：自动注册所有 adapter（只执行一次）
if [[ ! -f "$REGISTERED_ADAPTERS_FILE" ]] || [[ ! -s "$REGISTERED_ADAPTERS_FILE" ]]; then
  pp_adapter_register_all 2>&1 | grep -v "^$" >&2
fi

# 入口点
# 只在直接执行时运行，被 source 时不执行
_is_main_script() {
  if [[ -n "${BASH_SOURCE[0]:-}" ]]; then
    # bash: BASH_SOURCE 在被 source 时与 $0 不同
    [[ "${BASH_SOURCE[0]}" == "${0}" ]]
  elif [[ -n "${ZSH_VERSION:-}" ]]; then
    # zsh: 检查 zsh_eval_context
    [[ "${ZSH_EVAL_CONTEXT:-}" == "toplevel" ]]
  else
    false
  fi
}

if _is_main_script; then
  echo "Adapter Loader - Registered adapters:"
  pp_adapter_list
fi
