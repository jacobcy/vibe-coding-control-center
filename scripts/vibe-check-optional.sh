#!/usr/bin/env zsh
# scripts/vibe-check-optional.sh - 可选依赖检查（配置驱动）
# 从 config/dependencies.toml 读取配置，动态检查所有依赖

set -euo pipefail

VIBE_ROOT="$(cd "$(dirname "${(%):-%x}")/.." && pwd)"
[[ -f "$VIBE_ROOT/lib/utils.sh" ]] && source "$VIBE_ROOT/lib/utils.sh"
[[ -f "$VIBE_ROOT/lib/config.sh" ]] && source "$VIBE_ROOT/lib/config.sh"

# ── Helper Functions ─────────────────────────────────────
_read_config() {
    uv run python "$VIBE_ROOT/scripts/vibe-read-dependencies.py" --format shell
}

_check_tool_from_config() {
    local line="$1"
    # 解析格式：name|check|install|description
    local name="${line%%|*}"
    local rest="${line#*|}"
    local check="${rest%%|*}"
    local rest2="${rest#*|}"
    local install="${rest2%%|*}"
    local description="${rest2#*|}"

    if command -v "$name" >/dev/null 2>&1 || eval "$check" >/dev/null 2>&1; then
        local version="$(eval "$check" 2>&1 | head -1 | sed 's/^[^0-9]*//')"
        printf "  ${GREEN}✓${NC} %-15s %s\n" "$name" "${version:-installed}"
        return 0
    else
        printf "  ${YELLOW}!${NC} %-15s %s\n" "$name" "未安装"
        echo "      $description"
        echo "      安装: $install"
        return 1
    fi
}

_check_key_from_config() {
    local line="$1"
    # 解析格式：name|env_var|description|get_from
    local name="${line%%|*}"
    local rest="${line#*|}"
    local env_var="${rest%%|*}"
    local rest2="${rest#*|}"
    local description="${rest2%%|*}"
    local get_from="${rest2#*|}"

    if [[ -n "${(P)env_var:-}" ]]; then
        printf "  ${GREEN}✓${NC} %-15s configured\n" "$name"
        return 0
    else
        printf "  ${YELLOW}!${NC} %-15s 未配置\n" "$name"
        echo "      $description"
        echo "      获取: $get_from"
        return 1
    fi
}

# ── Dynamic Checking from Config ────────────────────────
check_optional_tools() {
    echo "${BOLD}可选工具（按需安装）:${NC}"
    echo ""

    local config_output="$(_read_config)"
    local in_optional_tools=false

    while IFS= read -r line; do
        if [[ "$line" == "# OPTIONAL_TOOLS" ]]; then
            in_optional_tools=true
            continue
        elif [[ "$line" =~ "^#" ]]; then
            in_optional_tools=false
            continue
        fi

        if $in_optional_tools && [[ -n "$line" ]]; then
            _check_tool_from_config "$line"
        fi
    done <<< "$config_output"

    echo ""
}

check_optional_keys() {
    echo "${BOLD}可选密钥（按需配置）:${NC}"
    echo ""

    local config_output="$(_read_config)"
    local in_optional_keys=false

    while IFS= read -r line; do
        if [[ "$line" == "# OPTIONAL_KEYS" ]]; then
            in_optional_keys=true
            continue
        elif [[ "$line" =~ "^#" ]]; then
            in_optional_keys=false
            continue
        fi

        if $in_optional_keys && [[ -n "$line" ]]; then
            _check_key_from_config "$line"
        fi
    done <<< "$config_output"

    echo ""
}

# ── Main Function ───────────────────────────────────────
vibe_check_optional() {
    local category="${1:-all}"

    case "$category" in
        tools)
            check_optional_tools
            ;;
        keys)
            check_optional_keys
            ;;
        all|"")
            check_optional_tools
            check_optional_keys
            ;;
        *)
            echo "用法: vibe-check-optional [tools|keys|all]"
            return 1
            ;;
    esac

    echo "${BOLD}提示:${NC} 这些都是可选组件，不影响Vibe核心功能。"
    echo "根据你的开发需求选择性安装即可。"
    echo ""
    echo "安装引导：${CYAN}/vibe-onboard${NC}"
}

# ── Entry Point ────────────────────────────────────────
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo "${BOLD}Vibe可选依赖检查工具（配置驱动）${NC}"
    echo ""
    echo "Usage: ${CYAN}vibe-check-optional${NC} [category]"
    echo ""
    echo "Categories:"
    echo "  tools    可选工具检查（rtk、gemini、tailscale等）"
    echo "  keys     可选密钥检查（ANTHROPIC_AUTH_TOKEN、OPENAI_API_KEY等）"
    echo "  all      检查所有可选组件（默认）"
    echo ""
    echo "配置来源：${CYAN}config/dependencies.toml${NC}"
    echo "安装引导：${CYAN}/vibe-onboard${NC}"
else
    vibe_check_optional "${1:-all}"
fi