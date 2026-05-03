#!/usr/bin/env zsh
# lib/doctor.sh - Environment Diagnostics for Vibe 2.0
# 目标：成为唯一环境诊断入口，从配置驱动生成检查结果
# 职责：检查工具与 Claude plugins，不检查密钥（密钥检查交给 vibe keys check）

# ── 配置读取 ─────────────────────────────────────────────
_doctor_read_config() {
    uv run python "$VIBE_ROOT/scripts/vibe-read-dependencies.py" --format shell
}

if [[ "${VIBE_DOCTOR_PLUGINS_LOADED:-}" != "$VIBE_LIB/doctor_plugins.sh" ]]; then
    source "$VIBE_LIB/doctor_plugins.sh"
    VIBE_DOCTOR_PLUGINS_LOADED="$VIBE_LIB/doctor_plugins.sh"
fi

# ── 工具检查函数 ─────────────────────────────────────────
_doctor_check_tool() {
    local name="$1" check="$2"
    local install="$3" description="$4"
    local output=""
    local exit_status=0

    output="$(zsh -c "$check" 2>&1)"
    exit_status=$?

    if [[ $exit_status -eq 0 ]]; then
        local first_line="${output%%$'\n'*}"
        printf "  ${GREEN}✓${NC} %-15s %s\n" "$name" "${first_line:-installed}"
        return 0
    fi

    printf "  ${YELLOW}!${NC} %-15s 未安装\n" "$name"
    echo "      $description"
    echo "      安装建议: $install"
    return 1
}

# ── Essential Check ──────────────────────────────────────
vibe_doctor_essential() {
    local missing=0
    local config_output

    config_output="$(_doctor_read_config)"

    echo "${BOLD}必要依赖检查${NC}"
    echo "$(printf '%.0s─' {1..50})"
    echo ""

    # 检查 REQUIRED_TOOLS
    local in_required=false
    while IFS= read -r line; do
        if [[ "$line" == "# REQUIRED_TOOLS" ]]; then
            in_required=true
            continue
        fi
        if [[ "$line" =~ "^#" ]]; then
            in_required=false
            continue
        fi
        if $in_required && [[ -n "$line" ]]; then
            IFS='|' read -r name check install description <<< "$line"
            _doctor_check_tool "$name" "$check" "$install" "$description" || ((missing+=1))
        fi
    done <<< "$config_output"

    echo ""

    if ((missing == 0)); then
        log_success "所有必要依赖已满足"
        echo ""
        echo "下一步："
        echo "  检查可选工具：${CYAN}vibe doctor${NC}"
        echo "  检查密钥状态：${CYAN}vibe keys check${NC}"
        return 0
    else
        log_error "缺少必要依赖，请先安装"
        return 1
    fi
}

# ── Plugin Check ────────────────────────────────────────
_doctor_check_plugins() {
    echo "${BOLD}Claude Plugins:${NC}"
    echo ""

    local plugin_output
    plugin_output="$(claude plugin list 2>&1)"

    if [[ $? -ne 0 ]]; then
        log_warn "无法获取 plugin 列表（claude plugin list 失败）"
        echo "  建议：确保 Claude CLI 正确安装并配置"
        return 1
    fi

    if [[ -z "$plugin_output" || "$plugin_output" == "No plugins installed" ]]; then
        log_warn "未安装任何 Claude plugins"
        echo "  建议：根据项目需求安装相应 plugin"
        echo "  安装命令：claude plugin install <plugin@marketplace>"
        return 0
    fi

    # 显示已安装的 plugins
    echo "$plugin_output" | while IFS= read -r line; do
        if [[ -n "$line" && "$line" != "No plugins installed" ]]; then
            printf "  ${GREEN}✓${NC} %s\n" "$line"
        fi
    done

    return 0
}

# ── Full Check (Default) ────────────────────────────────
vibe_doctor() {
    if [[ "$1" == "-h" || "$1" == "--help" ]]; then
        echo "${BOLD}Vibe 环境诊断${NC}"
        echo ""
        echo "Usage: ${CYAN}vibe doctor${NC} [options]"
        echo ""
        echo "Options:"
        echo "  --essential    只检查必要工具（git、uv、gh、tmux、lazygit、至少一个 AI 工具）"
        echo "  --help         显示此帮助信息"
        echo ""
        echo "职责：检查开发环境工具与 Claude plugins 状态（不检查密钥）"
        echo "密钥检查：请使用 ${CYAN}vibe keys check${NC}"
        return 0
    fi

    if [[ "$1" == "--essential" ]]; then
        vibe_doctor_essential
        return $?
    fi

    local missing=0
    local optional_missing=0
    local plugin_missing=0
    local config_output

    config_output="$(_doctor_read_config)"

    echo "${BOLD}Vibe Coding Control Center${NC} — 环境诊断"
    echo "$(printf '%.0s─' {1..50})"
    echo ""

    # Vibe version
    echo "${CYAN}Vibe Version:${NC} $(get_vibe_version)"
    echo "${CYAN}VIBE_ROOT:${NC}    $VIBE_ROOT"
    echo ""

    # 必要工具
    echo "${BOLD}必要工具:${NC}"
    local in_required=false
    while IFS= read -r line; do
        if [[ "$line" == "# REQUIRED_TOOLS" ]]; then
            in_required=true
            continue
        fi
        if [[ "$line" =~ "^#" ]]; then
            in_required=false
            continue
        fi
        if $in_required && [[ -n "$line" ]]; then
            IFS='|' read -r name check install description <<< "$line"
            _doctor_check_tool "$name" "$check" "$install" "$description" || ((missing+=1))
        fi
    done <<< "$config_output"
    echo ""

    # 可选工具
    echo "${BOLD}可选工具:${NC}"
    local in_optional=false
    while IFS= read -r line; do
        if [[ "$line" == "# OPTIONAL_TOOLS" ]]; then
            in_optional=true
            continue
        fi
        if [[ "$line" =~ "^#" ]]; then
            in_optional=false
            continue
        fi
        if $in_optional && [[ -n "$line" ]]; then
            IFS='|' read -r name check install description <<< "$line"
            _doctor_check_tool "$name" "$check" "$install" "$description" || ((optional_missing+=1))
        fi
    done <<< "$config_output"
    echo ""

    # Claude Plugins
    _doctor_check_plugins "$config_output"
    echo ""

    # OpenSpec Check (Optional)
    echo "${BOLD}Optional Tools (Non-blocking):${NC}"
    if command -v openspec &> /dev/null; then
        local openspec_version
        openspec_version=$(openspec --version 2>/dev/null | head -1)
        printf "  ${GREEN}✓${NC} %-15s %s\n" "openspec" "${openspec_version:-installed}"
    else
        printf "  ${CYAN}○${NC} %-15s 未安装（可选）\n" "openspec"
        echo "      用途：OpenAPI 规范管理与 Gate 产物生成"
        echo "      安装：pnpm add -g @openspec/tools"
    fi
    echo ""

    # Manager Token Check (Optional)
    echo "${BOLD}Role-Specific Tokens:${NC}"
    if [ -n "$VIBE_MANAGER_GITHUB_TOKEN" ]; then
        # Validate token format (basic check)
        if [[ ! "$VIBE_MANAGER_GITHUB_TOKEN" =~ ^ghp_ && ! "$VIBE_MANAGER_GITHUB_TOKEN" =~ ^github_pat_ ]]; then
            printf "  ${YELLOW}!${NC} %-15s Invalid token format (should start with ghp_ or github_pat_)\n" "Manager Token"
            echo "      建议：检查 VIBE_MANAGER_GITHUB_TOKEN 是否配置正确"
        else
            local manager_username
            manager_username=$(GH_TOKEN="$VIBE_MANAGER_GITHUB_TOKEN" timeout 5 gh api user 2>/dev/null | jq -r '.login' 2>/dev/null)

            if [ -n "$manager_username" ] && [ "$manager_username" != "null" ]; then
                # Cross-check with settings.yaml manager_usernames
                local expected_usernames
                expected_usernames=$(grep -A 10 "manager_usernames:" "$VIBE_ROOT/config/v3/settings.yaml" 2>/dev/null | grep -E '^\s*-\s+"' | sed 's/.*"\([^"]*\)".*/\1/' | tr '\n' ' ')

                if [ -z "$expected_usernames" ]; then
                    # Bug 6: Warn if token is set but whitelist is empty
                    printf "  ${YELLOW}!${NC} %-15s Token set but manager_usernames is empty\n" "Manager Token"
                    echo "      建议：在 settings.yaml 的 manager_usernames 中加入 '$manager_username'"
                elif [[ ! " $expected_usernames " =~ " $manager_username " ]]; then
                    printf "  ${YELLOW}!${NC} %-15s Identity mismatch (expected: %s, got: %s)\n" \
                        "Manager Token" "$(echo $expected_usernames | tr ' ' ',')" "$manager_username"
                    echo "      建议：检查 VIBE_MANAGER_GITHUB_TOKEN 是否配置了正确的 Bot 账号"
                else
                    printf "  ${GREEN}✓${NC} %-15s Configured (user: %s)\n" "Manager Token" "$manager_username"
                fi
            else
                printf "  ${YELLOW}!${NC} %-15s Token validation failed (invalid or insufficient permissions)\n" "Manager Token"
                echo "      建议：运行 'vibe keys check' 检查 token 状态"
            fi
        fi
    else
        # Bug 5: Warn that fallback to user token occurs
        printf "  ${CYAN}○${NC} %-15s Not configured (using user fallback)\n" "Manager Token"
        echo "      ${YELLOW}⚠${NC} 警告：Manager 将使用人类身份发评论，双层防护降级为单层（仅靠 marker 过滤）"
        echo "      建议：配置专用 Bot 账号以实现物理隔离：vibe keys set VIBE_MANAGER_GITHUB_TOKEN"
    fi
    echo ""

    # 总结
    if ((missing == 0 && plugin_missing == 0)); then
        log_success "必要工具已满足"
        if ((optional_missing > 0)); then
            log_warn "可选工具缺失 $optional_missing 个（不影响核心功能）"
        fi
        echo ""
        echo "密钥检查：${CYAN}vibe keys check${NC}"
    else
        local required_missing=$((missing + plugin_missing))
        log_error "必要环境项缺失 $required_missing 个，请先处理建议项"
        echo ""
        echo "查看必要依赖安装提示："
        echo "  ${CYAN}vibe doctor --essential${NC}"
    fi
}
