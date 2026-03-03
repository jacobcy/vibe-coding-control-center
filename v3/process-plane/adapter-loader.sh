#!/usr/bin/env zsh
# Adapter Loader - 动态加载和验证 provider adapters

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
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
pp_adapter_validate() {
  local provider_name="$1"
  local adapter_script="$ADAPTERS_DIR/$provider_name/adapter.sh"
  
  # 检查 adapter 脚本是否存在且可执行
  if [[ ! -f "$adapter_script" || ! -x "$adapter_script" ]]; then
    return 1
  fi
  
  # 验证必需的接口
  if ! grep -q "provider_adapter" "$adapter_script" 2>/dev/null; then
    return 1
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
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  echo "Adapter Loader - Registered adapters:"
  pp_adapter_list
fi
