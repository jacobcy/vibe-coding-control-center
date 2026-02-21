#!/usr/bin/env zsh
# lib/chat_router.sh
# Natural language intent routing for vibe chat

# Resolve script directory for sourcing dependencies
_chat_router_dir="$(cd "$(dirname "${(%):-%x}")" && pwd)"

# Source dependencies
if [[ -f "${_chat_router_dir}/utils.sh" ]]; then
    source "${_chat_router_dir}/utils.sh"
fi
if [[ -f "${_chat_router_dir}/keys_manager.sh" ]]; then
    source "${_chat_router_dir}/keys_manager.sh"
fi
if [[ -f "${_chat_router_dir}/tool_manager.sh" ]]; then
    source "${_chat_router_dir}/tool_manager.sh"
fi
if [[ -f "${_chat_router_dir}/mcp_manager.sh" ]]; then
    source "${_chat_router_dir}/mcp_manager.sh"
fi
if [[ -f "${_chat_router_dir}/env_manager.sh" ]]; then
    source "${_chat_router_dir}/env_manager.sh"
fi

# Intent patterns (Chinese and English)
# Format: "intent_name"="pattern1|pattern2|..."
typeset -gA VIBE_INTENT_PATTERNS
VIBE_INTENT_PATTERNS=(
    # Keys intents
    ["keys_use"]="切换到|切换|使用|改成|换到|switch to|use|change to"
    ["keys_set"]="设置.*key|设置.*密钥|key.*设置|set.*key|set.*token"
    ["keys_list"]="列出.*密钥|密钥.*列表|list.*keys|show.*keys"
    ["keys_current"]="当前.*密钥|当前.*key|current.*key"

    # Tool intents
    ["tool_install"]="安装|装一下|装个|install"
    ["tool_uninstall"]="卸载|删除|remove|uninstall"
    ["tool_enable"]="启用|开启|enable|turn on"
    ["tool_disable"]="禁用|关闭|disable|turn off"
    ["tool_list"]="列出.*工具|工具.*列表|list.*tools|show.*tools"

    # MCP intents
    ["mcp_add"]="加.*mcp|添加.*mcp|配置.*mcp|添加.*服务|add.*mcp"
    ["mcp_remove"]="移除.*mcp|删除.*mcp|remove.*mcp"
    ["mcp_list"]="列出.*mcp|mcp.*列表|list.*mcp|show.*mcp"

    # Skill intents
    ["skill_add"]="加.*skill|添加.*skill|添加.*技能|add.*skill"
    ["skill_list"]="列出.*skill|skill.*列表|list.*skills"

    # Environment intents
    ["init"]="初始化|开始|设置环境|init|setup"
    ["export"]="导出|备份|export|backup"
    ["status"]="状态|状态怎么样|how.*status|show.*status"
    ["check"]="检查|诊断|check|doctor|diagnose"
)

# Route intent from message
# Usage: route_intent "message"
# Returns: intent name, or "chat" if no match
route_intent() {
    local message="$1"

    # Convert to lowercase for matching
    local lower_message="${message:l}"

    # Check each intent pattern
    for intent in "${(@k)VIBE_INTENT_PATTERNS}"; do
        local pattern="${VIBE_INTENT_PATTERNS[$intent]}"

        # Check if any pattern matches
        if [[ "$lower_message" =~ $pattern ]]; then
            echo "$intent"
            return 0
        fi
    done

    # No match - default to chat
    echo "chat"
    return 1
}

# Handle intent with full message
# Usage: handle_intent "intent" "original_message"
# Returns: 0 if handled, 1 if should fall through to chat
handle_intent() {
    local intent="$1"
    local message="$2"

    case "$intent" in
        keys_use)
            # Extract provider name
            local provider
            provider=$(echo "$message" | grep -oE 'anthropic|openai|deepseek|google|azure' | head -1)
            provider=$(echo "$provider" | tr '[:upper:]' '[:lower:]')

            if [[ -n "$provider" ]]; then
                vibe_keys_use "$provider"
            else
                log_error "无法识别密钥提供商"
                echo "支持的提供商: anthropic, openai, deepseek"
            fi
            ;;

        keys_set)
            # Extract KEY=value
            local key_value
            key_value=$(echo "$message" | grep -oE '[A-Z_][A-Z0-9_]*=[^ ]+')
            if [[ -n "$key_value" ]]; then
                vibe_keys_set "$key_value"
            else
                log_error "无法识别密钥设置"
                echo "示例: 设置 ANTHROPIC_AUTH_TOKEN=your-key"
            fi
            ;;

        keys_list)
            vibe_keys_list
            ;;

        keys_current)
            vibe_keys_current
            ;;

        tool_install)
            # Extract tool name
            local tool
            tool=$(echo "$message" | grep -oE 'claude|opencode|codex' | head -1)
            tool=$(echo "$tool" | tr '[:upper:]' '[:lower:]')

            if [[ -n "$tool" ]]; then
                vibe_tool_install "$tool"
                vibe_tool_enable "$tool"
            else
                log_error "无法识别工具"
                echo "支持的工具: claude, opencode, codex"
            fi
            ;;

        tool_uninstall)
            local tool
            tool=$(echo "$message" | grep -oE 'claude|opencode|codex' | head -1)
            tool=$(echo "$tool" | tr '[:upper:]' '[:lower:]')

            if [[ -n "$tool" ]]; then
                vibe_tool_uninstall "$tool"
            else
                log_error "无法识别工具"
            fi
            ;;

        tool_enable)
            local tool
            tool=$(echo "$message" | grep -oE 'claude|opencode|codex' | head -1)
            tool=$(echo "$tool" | tr '[:upper:]' '[:lower:]')

            if [[ -n "$tool" ]]; then
                vibe_tool_enable "$tool"
            else
                log_error "无法识别工具"
            fi
            ;;

        tool_disable)
            local tool
            tool=$(echo "$message" | grep -oE 'claude|opencode|codex' | head -1)
            tool=$(echo "$tool" | tr '[:upper:]' '[:lower:]')

            if [[ -n "$tool" ]]; then
                vibe_tool_disable "$tool"
            else
                log_error "无法识别工具"
            fi
            ;;

        tool_list)
            vibe_tool_list
            ;;

        mcp_add)
            local mcp_name
            mcp_name=$(echo "$message" | grep -oE 'github|brave-search|filesystem|memory|notion' | head -1)

            # Check for --for flag
            local tool=""
            if [[ "$message" =~ --for[[:space:]]+([a-z]+) ]]; then
                tool="${match[1]}"
            fi

            if [[ -n "$mcp_name" ]]; then
                if [[ -n "$tool" ]]; then
                    vibe_mcp_add "$mcp_name" --for "$tool"
                else
                    vibe_mcp_add "$mcp_name"
                fi
            else
                log_error "无法识别 MCP 服务"
                echo "支持的 MCP: github, brave-search, filesystem, memory, notion"
            fi
            ;;

        mcp_remove)
            local mcp_name
            mcp_name=$(echo "$message" | grep -oE 'github|brave-search|filesystem|memory|notion' | head -1)

            if [[ -n "$mcp_name" ]]; then
                vibe_mcp_remove "$mcp_name"
            else
                log_error "无法识别 MCP 服务"
            fi
            ;;

        mcp_list)
            vibe_mcp_list
            ;;

        skill_add)
            log_info "添加技能需要文件路径或 URL"
            echo "示例: vibe skill add ./my-skill.yaml"
            ;;

        skill_list)
            vibe_skill_list
            ;;

        init)
            vibe_env_init
            ;;

        export)
            vibe_env_export
            ;;

        status)
            vibe_env_status
            ;;

        check)
            # Run environment check
            if type do_check_env >/dev/null 2>&1; then
                do_check_env
            else
                vibe_env_status
            fi
            ;;

        chat|*)
            # Cannot handle - pass to AI
            return 1
            ;;
    esac
}

# Main chat routing entry point
# Usage: vibe_chat_route "message"
# Returns: 0 if handled, 1 if should use AI
vibe_chat_route() {
    local message="$1"

    if [[ -z "$message" ]]; then
        echo "请输入消息"
        return 1
    fi

    # Try to route intent
    local intent
    if intent=$(route_intent "$message"); then
        log_info "识别意图: $intent"

        if handle_intent "$intent" "$message"; then
            # Intent handled successfully
            return 0
        fi
    fi

    # Cannot route - use AI
    return 1
}
