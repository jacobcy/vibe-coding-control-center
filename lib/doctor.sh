#!/usr/bin/env zsh
# lib/doctor.sh - Environment Diagnostics for Vibe 2.0
# 目标：成为唯一环境诊断入口，从配置驱动生成检查结果
# 职责：检查工具与 Claude plugins，不检查密钥（密钥检查交给 vibe keys check）

# ── 配置读取 ─────────────────────────────────────────────
_doctor_read_config() {
    python3 "$VIBE_ROOT/scripts/vibe-read-dependencies.py" --format shell
}

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

_doctor_trim() {
    local value="$1"
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"
    printf "%s" "$value"
}

_doctor_plugin_install_hint() {
    local plugin_name="$1"
    printf "claude plugin install %s" "$plugin_name"
}

_doctor_plugin_scope_hint() {
    local plugin_name="$1"
    local expected_scope="$2"
    local install_hint
    install_hint="$(_doctor_plugin_install_hint "$plugin_name")"

    if [[ -n "$expected_scope" ]]; then
        printf "%s --scope %s" "$install_hint" "$expected_scope"
    else
        printf "%s" "$install_hint"
    fi
}

_doctor_collect_installed_plugins() {
    typeset -gA DOCTOR_PLUGIN_VERSION
    typeset -gA DOCTOR_PLUGIN_SCOPE
    typeset -gA DOCTOR_PLUGIN_STATUS

    DOCTOR_PLUGIN_VERSION=()
    DOCTOR_PLUGIN_SCOPE=()
    DOCTOR_PLUGIN_STATUS=()

    local plugin_output=""
    if ! plugin_output="$(claude plugin list 2>&1)"; then
        DOCTOR_PLUGIN_LIST_ERROR="$plugin_output"
        return 1
    fi

    DOCTOR_PLUGIN_LIST_ERROR=""

    local current_plugin=""
    local line=""
    local trimmed=""
    local plugin_status_text=""
    while IFS= read -r line; do
        trimmed="$(_doctor_trim "$line")"
        [[ -z "$trimmed" || "$trimmed" == "Installed plugins:" ]] && continue

        if [[ "$trimmed" == "❯ "* ]]; then
            current_plugin="${trimmed#❯ }"
            DOCTOR_PLUGIN_STATUS[$current_plugin]="unknown"
            continue
        fi

        [[ -z "$current_plugin" ]] && continue

        if [[ "$trimmed" == Version:* ]]; then
            DOCTOR_PLUGIN_VERSION[$current_plugin]="$(_doctor_trim "${trimmed#Version:}")"
        elif [[ "$trimmed" == Scope:* ]]; then
            DOCTOR_PLUGIN_SCOPE[$current_plugin]="$(_doctor_trim "${trimmed#Scope:}")"
        elif [[ "$trimmed" == Status:* ]]; then
            plugin_status_text="$(_doctor_trim "${trimmed#Status:}")"
            plugin_status_text="${plugin_status_text#✔ }"
            plugin_status_text="${plugin_status_text#✘ }"
            DOCTOR_PLUGIN_STATUS[$current_plugin]="$(_doctor_trim "$plugin_status_text")"
        fi
    done <<< "$plugin_output"

    return 0
}

_doctor_print_plugin_status() {
    local plugin_name="$1"
    local expected_scope="$2"
    local description="$3"
    local severity="${4:-optional}"
    local plugin_status="${DOCTOR_PLUGIN_STATUS[$plugin_name]-}"
    local scope="${DOCTOR_PLUGIN_SCOPE[$plugin_name]-}"
    local version="${DOCTOR_PLUGIN_VERSION[$plugin_name]-}"
    local details=()
    local missing_return=2

    case "$severity" in
        required) missing_return=1 ;;
        recommended) missing_return=3 ;;
        optional) missing_return=2 ;;
    esac

    [[ -n "$description" ]] && echo "      $description"

    if [[ -z "$plugin_status" ]]; then
        printf "  ${YELLOW}!${NC} %-36s 未安装\n" "$plugin_name"
        echo "      安装建议: $(_doctor_plugin_scope_hint "$plugin_name" "$expected_scope")"
        return "$missing_return"
    fi

    [[ -n "$scope" ]] && details+=("$scope")
    [[ -n "$plugin_status" ]] && details+=("$plugin_status")
    [[ -n "$version" && "$version" != "unknown" ]] && details+=("$version")

    local detail_text="installed"
    if (( ${#details[@]} > 0 )); then
        detail_text="${(j:, :)details}"
    fi

    if [[ -n "$expected_scope" && "$scope" != "$expected_scope" ]]; then
        printf "  ${YELLOW}!${NC} %-36s scope 不符合预期\n" "$plugin_name"
        echo "      当前状态: ${detail_text}"
        echo "      期望 scope: ${expected_scope}"
        echo "      安装建议: $(_doctor_plugin_scope_hint "$plugin_name" "$expected_scope")"
        return "$missing_return"
    fi

    if [[ "$plugin_status" == "enabled" ]]; then
        printf "  ${GREEN}✓${NC} %-36s %s\n" "$plugin_name" "$detail_text"
        return 0
    fi

    printf "  ${YELLOW}!${NC} %-36s 已安装但未启用\n" "$plugin_name"
    echo "      当前状态: ${detail_text}"
    echo "      建议：先在 Claude CLI 中启用该 plugin"
    return "$missing_return"
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
    local config_output="$1"
    local required_missing=0
    local recommended_missing=0
    local optional_missing=0
    local line=""
    local name=""
    local expected_scope=""
    local description=""

    DOCTOR_PLUGIN_REQUIRED_MISSING=0
    DOCTOR_PLUGIN_RECOMMENDED_MISSING=0
    DOCTOR_PLUGIN_OPTIONAL_MISSING=0

    echo "${BOLD}Claude Plugins:${NC}"
    echo ""

    if ! _doctor_collect_installed_plugins; then
        log_warn "无法获取 plugin 列表（claude plugin list 失败）"
        echo "  建议：确保 Claude CLI 正确安装并配置"
        [[ -n "$DOCTOR_PLUGIN_LIST_ERROR" ]] && echo "  详情: $DOCTOR_PLUGIN_LIST_ERROR"
        return 1
    fi

    echo "  ${CYAN}必要 plugins:${NC}"
    local in_required=false
    while IFS= read -r line; do
        if [[ "$line" == "# REQUIRED_PLUGINS" ]]; then
            in_required=true
            continue
        fi
        if [[ "$line" =~ "^#" ]]; then
            in_required=false
            continue
        fi
        if $in_required && [[ -n "$line" ]]; then
            IFS='|' read -r name expected_scope description <<< "$line"
            _doctor_print_plugin_status "$name" "$expected_scope" "$description" required
            case $? in
                1) ((required_missing+=1)) ;;
            esac
        fi
    done <<< "$config_output"

    echo ""
    echo "  ${CYAN}建议 plugins:${NC}"
    local in_recommended=false
    while IFS= read -r line; do
        if [[ "$line" == "# RECOMMENDED_PLUGINS" ]]; then
            in_recommended=true
            continue
        fi
        if [[ "$line" =~ "^#" ]]; then
            in_recommended=false
            continue
        fi
        if $in_recommended && [[ -n "$line" ]]; then
            IFS='|' read -r name expected_scope description <<< "$line"
            _doctor_print_plugin_status "$name" "$expected_scope" "$description" recommended
            case $? in
                3) ((recommended_missing+=1)) ;;
            esac
        fi
    done <<< "$config_output"

    echo ""
    echo "  ${CYAN}可选 plugins:${NC}"
    local in_optional=false
    while IFS= read -r line; do
        if [[ "$line" == "# OPTIONAL_PLUGINS" ]]; then
            in_optional=true
            continue
        fi
        if [[ "$line" =~ "^#" ]]; then
            in_optional=false
            continue
        fi
        if $in_optional && [[ -n "$line" ]]; then
            IFS='|' read -r name expected_scope description <<< "$line"
            _doctor_print_plugin_status "$name" "$expected_scope" "$description" optional
            case $? in
                2) ((optional_missing+=1)) ;;
            esac
        fi
    done <<< "$config_output"

    echo ""
    if (( required_missing == 0 )); then
        log_success "必要 plugins 已满足"
    else
        log_warn "必要 plugins 缺失 $required_missing 个"
    fi

    if (( recommended_missing > 0 )); then
        log_warn "建议 plugins 缺失 $recommended_missing 个（推荐补齐）"
    fi

    if (( optional_missing > 0 )); then
        log_warn "可选 plugins 缺失 $optional_missing 个（按需安装）"
    fi

    DOCTOR_PLUGIN_REQUIRED_MISSING=$required_missing
    DOCTOR_PLUGIN_RECOMMENDED_MISSING=$recommended_missing
    DOCTOR_PLUGIN_OPTIONAL_MISSING=$optional_missing

    (( required_missing == 0 ))
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
    _doctor_check_plugins "$config_output" || true
    plugin_missing=$DOCTOR_PLUGIN_REQUIRED_MISSING
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
