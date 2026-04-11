#!/usr/bin/env zsh
# scripts/vibe-install-tools.sh - AI开发工具安装脚本
# 安装 claude、opencode、codex 等AI工具

set -euo pipefail

VIBE_ROOT="$(cd "$(dirname "${(%):-%x}")/.." && pwd)"
[[ -f "$VIBE_ROOT/lib/utils.sh" ]] && source "$VIBE_ROOT/lib/utils.sh"
[[ -f "$VIBE_ROOT/lib/config.sh" ]] && source "$VIBE_ROOT/lib/config.sh"

# ── Installation Functions ───────────────────────────────────────
_install_claude() {
    echo "${BOLD}Installing Claude Code...${NC}"
    echo ""

    if vibe_has "claude"; then
        log_info "Claude Code already installed"
        local ver="$(claude --version 2>&1 | head -1)"
        echo "  当前版本: $ver"
        echo ""
        echo "如需重新安装，请先卸载旧版本或手动更新"
        return 0
    fi

    echo "Claude Code 是 Anthropic 官方 CLI 工具，功能强大"
    echo ""
    echo "安装方式："
    echo "  1. 访问 ${CYAN}claude.ai${NC} 下载安装"
    echo "  2. 或使用 Homebrew: ${CYAN}brew install claude${NC} (如果可用)"
    echo ""
    echo "配置要求："
    echo "  - ANTHROPIC_AUTH_TOKEN (API密钥)"
    echo "  - ANTHROPIC_BASE_URL (可选，中国用户可使用 https://api.bghunt.cn)"
    echo ""
    log_warn "Claude Code 需要付费订阅，请确保有有效的 Anthropic 账户"

    # 检查密钥配置
    if [[ -z "$ANTHROPIC_AUTH_TOKEN" ]]; then
        log_error "ANTHROPIC_AUTH_TOKEN 未配置"
        echo "请先在 ~/.vibe/keys.env 中配置密钥"
        return 1
    fi

    log_info "密钥已配置，安装完成后即可使用"
    return 0
}

_install_opencode() {
    echo "${BOLD}Installing OpenCode...${NC}"
    echo ""

    if vibe_has "opencode"; then
        log_info "OpenCode already installed"
        local ver="$(opencode --version 2>&1 | head -1)"
        echo "  当前版本: $ver"
        return 0
    fi

    echo "OpenCode 是免费开源的AI编码助手"
    echo ""

    # 检查 npm
    if ! vibe_has "npm"; then
        log_error "npm 未安装，需要先安装 Node.js"
        echo ""
        echo "安装 Node.js："
        echo "  ${CYAN}brew install node${NC}"
        return 1
    fi

    echo "安装方式：${CYAN}npm install -g opencode${NC}"
    echo ""
    read -p "是否立即安装？ (y/n) " -n 1 -r
    echo ""

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        npm install -g opencode
        log_success "OpenCode installed successfully"

        # 配置默认模型
        echo ""
        echo "OpenCode 支持多种免费模型："
        echo "  - opencode/kimi-k2.5-free (Moonshot Kimi)"
        echo "  - opencode/deepseek-chat (DeepSeek)"
        echo ""
        if [[ -n "$VIBE_OPENCODE_MODEL" ]]; then
            log_info "已配置默认模型: $VIBE_OPENCODE_MODEL"
        else
            log_warn "VIBE_OPENCODE_MODEL 未配置，建议在 keys.env 中设置"
        fi
    else
        log_info "跳过安装，稍后可手动执行: npm install -g opencode"
    fi
}

_install_codex() {
    echo "${BOLD}Installing Codex (Legacy)...${NC}"
    echo ""

    if vibe_has "codex"; then
        log_info "Codex already installed"
        local ver="$(codex --version 2>&1 | head -1)"
        echo "  当前版本: $ver"
        return 0
    fi

    log_warn "Codex 是旧版工具，建议使用 claude 或 opencode 代替"
    echo ""
    echo "如果仍需安装 codex，请参考项目文档"
    return 1
}

# ── Interactive Installation ────────────────────────────────────
vibe_install_tools_interactive() {
    echo "${BOLD}AI开发工具安装引导${NC}"
    echo ""
    echo "Vibe 需要至少一个AI工具才能正常运行："
    echo "  1. ${CYAN}claude${NC}  - Anthropic 官方工具（付费，功能强大）"
    echo "  2. ${CYAN}opencode${NC} - 开源免费工具（推荐尝鲜）"
    echo "  3. ${CYAN}codex${NC}    - 旧版工具（已过时）"
    echo ""

    local tools=("claude" "opencode" "codex")
    local installed=()

    # 检查已安装的工具
    for tool in "${tools[@]}"; do
        if vibe_has "$tool"; then
            installed+=("$tool")
        fi
    done

    if [[ ${#installed[@]} -gt 0 ]]; then
        log_success "已安装的工具: ${installed[*]}"
        echo ""
        read -p "是否继续安装其他工具？ (y/n) " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "现有工具已满足使用要求"
            return 0
        fi
    fi

    # 选择要安装的工具
    echo ""
    echo "请选择要安装的工具："
    echo ""

    for i in {1..2}; do  # 只推荐前两个，codex不推荐
        local tool="${tools[$i]}"
        if vibe_has "$tool"; then
            printf "  ${GREEN}✓${NC} %d. %s (已安装)\n" "$i" "$tool"
        else
            printf "  ${YELLOW}○${NC} %d. %s\n" "$i" "$tool"
        fi
    done

    echo ""
    read -p "输入编号选择工具 (1-2，多个用空格分隔): " -r choices

    for choice in $choices; do
        case "$choice" in
            1) _install_claude ;;
            2) _install_opencode ;;
            *) log_warn "无效的选择: $choice" ;;
        esac
        echo ""
    done

    # 最终检查
    echo ""
    echo "${BOLD}安装结果检查${NC}"
    local final_count=0
    for tool in "${tools[@]}"; do
        if vibe_has "$tool"; then
            printf "  ${GREEN}✓${NC} %-12s installed\n" "$tool"
            ((final_count+=1))
        else
            printf "  ${RED}✗${NC} %-12s not installed\n" "$tool"
        fi
    done

    echo ""
    if ((final_count > 0)); then
        log_success "$final_count 个AI工具可用，Vibe 可以正常使用"
        echo ""
        echo "后续检查状态：${CYAN}vibe tools${NC}"
        echo "查看配置详情：${CYAN}vibe doctor${NC}"
    else
        log_error "未安装任何AI工具，Vibe 无法正常工作"
        echo ""
        echo "请至少安装一个工具后再使用 Vibe"
        return 1
    fi
}

# ── Command Line Mode ────────────────────────────────────────────
vibe_install_tools() {
    local target="${1:-interactive}"

    case "$target" in
        claude)
            _install_claude
            ;;
        opencode)
            _install_opencode
            ;;
        codex)
            _install_codex
            ;;
        interactive|"")
            vibe_install_tools_interactive
            ;;
        help|-h|--help)
            echo "${BOLD}vibe-install-tools - AI开发工具安装${NC}"
            echo ""
            echo "Usage: ${CYAN}vibe-install-tools${NC} [tool]"
            echo ""
            echo "Tools:"
            echo "  claude      安装 Claude Code (Anthropic官方工具)"
            echo "  opencode    安装 OpenCode (免费开源工具)"
            echo "  codex       安装 Codex (旧版，不推荐)"
            echo ""
            echo "交互式安装（推荐）："
            echo "  ${CYAN}vibe-install-tools${NC}             # 无参数，交互式选择"
            echo "  ${CYAN}/vibe-onboard${NC}                  # 通过skill引导安装"
            echo ""
            echo "安装后检查状态："
            echo "  ${CYAN}vibe tools${NC}                    # 查看安装状态"
            ;;
        *)
            log_error "未知工具: $target"
            echo ""
            echo "支持的工具: claude, opencode, codex"
            echo "查看帮助: vibe-install-tools --help"
            return 1
            ;;
    esac
}

# ── Entry Point ────────────────────────────────────────────────────
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    vibe_install_tools "help"
else
    vibe_install_tools "${1:-interactive}"
fi